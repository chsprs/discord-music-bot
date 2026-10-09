"""Uji update.sh tanpa menyentuh pip/systemd sungguhan.

Bahaya yang dijaga:
- P1: update.sh harus memakai `pip install --upgrade`, bukan `pip install` pin.
  Tanpa --upgrade, "pembaruan" mingguan memasang versi yang sudah terpasang
  dan cipher extractor YouTube tidak pernah dimutakhirkan (lalu lagu gagal).
- P2: update.sh tidak boleh me-restart bot saat ada pendengar aktif.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'update.sh')


def read_text(path: str) -> str:
    """Baca berkas dengan context manager (hindari ResourceWarning)."""
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def read_script() -> str:
    with open(SCRIPT, encoding='utf-8') as handle:
        return handle.read()


class UpdateScriptStaticTests(unittest.TestCase):
    """Periksa isi skrip: murah dan menangkap regresi yang paling penting."""

    def setUp(self):
        self.src = read_script()

    def test_syntax_is_valid(self):
        proc = subprocess.run(['bash', '-n', SCRIPT], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_pip_install_uses_require_hashes(self):
        """Pembaruan harus memakai --require-hashes untuk hardening supply chain."""
        installs = re.findall(r'pip["\s]*install[^\n|;]*', self.src)
        installs += re.findall(r'VENV_PIP"?\)?\s+install[^\n]*', self.src)
        joined = ' '.join(installs)
        self.assertTrue(installs, 'tidak menemukan pemanggilan pip install di update.sh')
        self.assertIn('--require-hashes', joined,
                      'pip install di update.sh harus memakai --require-hashes')

    def test_restart_is_guarded_by_listener_check(self):
        """Restart harus lewat pengecekan penonton, bukan langsung."""
        self.assertIn('listeners_active', self.src,
                      'update.sh harus memakai listeners_active() sebelum restart')
        restart_idx = self.src.find('systemctl restart discord-music.service')
        guard_idx = self.src.find('if listeners_active')
        self.assertNotEqual(restart_idx, -1)
        self.assertNotEqual(guard_idx, -1,
                            'tidak ada penjaga listeners_active sebelum restart')
        self.assertLess(guard_idx, restart_idx,
                        'pengecekan listeners_active harus mendahului restart')

    def test_cache_is_cleared_after_update(self):
        """Cache lama harus dibuang agar extractor baru tidak pakai data basi."""
        self.assertRegex(self.src, r'rm -rf.*yt-dlp|yt-dlp.*rm -rf|for cache in',
                         'cache yt-dlp harus dibersihkan setelah pembaruan')

    def test_lock_prevents_concurrent_runs(self):
        self.assertIn('flock', self.src,
                      'update.sh harus memakai flock agar dua pembaruan tidak tumpang tindih')

    def test_uses_venv_python_not_system(self):
        """Versi yt-dlp harus dibaca dari venv, bukan python sistem."""
        self.assertIn('VENV_PY', self.src)
        self.assertNotRegex(self.src, r'^\s*python3?\s+-c.*yt_dlp',
                            'jangan pakai python sistem untuk membaca versi yt-dlp')

    def test_home_variable_has_default_for_set_u(self):
        """HOME tidak boleh dipanggil mentah tanpa default di bawah set -u."""
        self.assertIn('${HOME:-/root}', self.src,
                      'HOME harus memiliki default ${HOME:-/root} agar tidak crash di timer systemd')
        self.assertNotIn('$HOME/.cache', self.src,
                         'ditemukan $HOME/.cache tanpa default fallback')


class UpdateScriptBehaviourTests(unittest.TestCase):
    """Jalankan skrip dengan venv tiruan agar perilaku nyata teruji."""

    def _make_fake_venv(self, tmp: str, listeners: int, active: bool = True,
                        state_age: float = 0.0) -> str:
        """Bangun direktori tiruan berisi venv/pip & venv/python palsu.

        pip palsu mencatat argumen; python palsu menjawab versi yt-dlp untuk
        `-c`, tetapi mendelegasikan sisa panggilan (parsing state.json) ke
        python asli agar logika listeners_active benar-benar teruji.
        """
        bot_dir = os.path.join(tmp, 'bot')
        os.makedirs(os.path.join(bot_dir, 'venv', 'bin'), exist_ok=True)
        pip = os.path.join(bot_dir, 'venv', 'bin', 'pip')
        with open(pip, 'w', encoding='utf-8') as handle:
            handle.write('#!/bin/bash\necho "$@" >> "$BOT_DIR/pip_calls.txt"\ntouch "$BOT_DIR/pip_ran"\nexit 0\n')
        os.chmod(pip, 0o755)
        real_py = os.path.realpath(sys.executable)
        py = os.path.join(bot_dir, 'venv', 'bin', 'python')
        with open(py, 'w', encoding='utf-8') as handle:
            handle.write(
                '#!/bin/bash\n'
                'if [[ "$1" == "-c" ]]; then\n'
                '    if [ -f "$BOT_DIR/pip_ran" ]; then\n'
                '        echo "2026.9.9"\n'
                '    else\n'
                '        echo "2026.9.8"\n'
                '    fi\n'
                '    exit 0\n'
                'fi\n'
                f'exec {real_py} "$@"\n'
            )
        os.chmod(py, 0o755)
        with open(os.path.join(bot_dir, 'requirements.txt'), 'w', encoding='utf-8') as handle:
            handle.write('discord.py[voice]==2.7.1\nyt-dlp[default]==2026.8.19\n')
        # State exporter tiruan: dipakai listeners_active().
        state = {
            'updated_at': time.time() - state_age,
            'total_listeners': listeners,
            'active_voice_count': 1 if listeners else 0,
        }
        with open(os.path.join(bot_dir, 'listeners.json'), 'w', encoding='utf-8') as handle:
            json.dump(state, handle)
        return bot_dir

    def _run(self, bot_dir: str, extra_env: dict, unset_env: list | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ, BOT_DIR=bot_dir, BOT_STATE_FILE=os.path.join(bot_dir, 'listeners.json'))
        env.update(extra_env)
        for key in (unset_env or []):
            env.pop(key, None)
        # systemctl palsu: selalu "active" agar jalur restart teruji.
        fake_bin = os.path.join(bot_dir, 'fakebin')
        os.makedirs(fake_bin, exist_ok=True)
        sc = os.path.join(fake_bin, 'systemctl')
        with open(sc, 'w', encoding='utf-8') as handle:
            handle.write('#!/bin/bash\necho "$@" >> "$BOT_DIR/systemctl_calls.txt"\n'
                         'if [[ "$1" == "is-active" ]]; then exit 0; fi\nexit 0\n')
        os.chmod(sc, 0o755)
        sudo = os.path.join(fake_bin, 'sudo')
        with open(sudo, 'w', encoding='utf-8') as handle:
            handle.write('#!/bin/bash\nif [[ "$1" == "systemctl" ]]; then shift; exec systemctl "$@"; fi\nexec "$@"\n')
        os.chmod(sudo, 0o755)
        env['PATH'] = fake_bin + os.pathsep + env.get('PATH', '')
        return subprocess.run(['bash', SCRIPT], capture_output=True, text=True, env=env, timeout=60)

    def test_home_unset_runs_without_unbound_error(self):
        """Timer systemd sering mengeksekusi skrip tanpa $HOME saat set -u aktif."""
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            proc = self._run(bot_dir, {}, unset_env=['HOME', 'XDG_CACHE_HOME'])
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_require_hashes_flag_reaches_pip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'pip_calls.txt'))
            self.assertIn('--require-hashes', calls,
                          'pip dipanggil tanpa --require-hashes: supply chain rentan')
            self.assertIn('requirements.txt', calls)

    def test_restart_deferred_when_listeners_present(self):
        """Ada pendengar -> bot TIDAK boleh di-restart."""
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=3)
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls_path = os.path.join(bot_dir, 'systemctl_calls.txt')
            calls = read_text(calls_path) if os.path.exists(calls_path) else ''
            self.assertNotIn('restart', calls,
                             'bot di-restart padahal ada pendengar aktif '
                             '(musik orang terputus)')
            log = read_text(os.path.join(bot_dir, 'last_update.log'))
            self.assertIn('ditunda', log)

    def test_restart_happens_when_idle(self):
        """Tidak ada pendengar -> bot boleh di-restart."""
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'systemctl_calls.txt'))
            self.assertIn('restart', calls,
                          'bot tidak di-restart padahal tidak ada pendengar')

    def test_stale_state_does_not_block_restart(self):
        """State basi (>60 dtk) berarti exporter mati: jangan dipercaya."""
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=5, state_age=300)
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'systemctl_calls.txt'))
            self.assertIn('restart', calls,
                          'state basi tidak boleh menahan restart selamanya')

    def test_missing_state_file_allows_restart(self):
        """Tanpa state.json (exporter belum jalan), restart boleh lanjut."""
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            os.remove(os.path.join(bot_dir, 'listeners.json'))
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'systemctl_calls.txt'))
            self.assertIn('restart', calls,
                          'tanpa state.json restart harus tetap jalan')

    def test_corrupt_state_file_allows_restart(self):
        """state.json rusak tidak boleh membuat update gagal permanen."""
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            with open(os.path.join(bot_dir, 'listeners.json'), 'w', encoding='utf-8') as handle:
                handle.write('{bukan json')
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'systemctl_calls.txt'))
            self.assertIn('restart', calls)



if __name__ == '__main__':
    unittest.main()


INSTALL = os.path.join(ROOT, 'install.sh')


class InstallScriptHardeningTests(unittest.TestCase):
    """L7: jangan pipe `curl | bash` mentah. L6: salin tools/ & docs/."""

    def setUp(self):
        with open(INSTALL, encoding='utf-8') as handle:
            self.src = handle.read()

    def test_syntax_is_valid(self):
        proc = subprocess.run(['bash', '-n', INSTALL], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_no_raw_curl_pipe_to_bash(self):
        # `curl ... | bash` mengeksekusi teks separuh bila unduhan terpotong/MITM.
        # Abaikan baris komentar (yang boleh menyebut pola ini sebagai dokumentasi).
        code = '\n'.join(line for line in self.src.splitlines()
                         if not line.lstrip().startswith('#'))
        self.assertNotRegex(
            code, r'curl[^\n|]*\|\s*bash',
            'install.sh tidak boleh pipe curl langsung ke bash (unduh ke berkas dulu)')

    def test_nodesource_downloaded_to_file_then_verified(self):
        self.assertIn('setup_20.x', self.src)
        self.assertRegex(self.src, r'curl[^\n]*-o\s+"?\$NODESOURCE_SETUP',
                         'skrip NodeSource harus diunduh ke berkas, bukan dieksekusi langsung')
        # Verifikasi bentuk minimal sebelum dieksekusi.
        self.assertRegex(self.src, r'head -n1[^\n]*\^#!|grep[^\n]*\^#!',
                         'skrip NodeSource harus diverifikasi berupa skrip shell (shebang)')

    def test_copies_tools_and_docs(self):
        self.assertRegex(self.src, r'for d in tools docs',
                         'install.sh harus menyalin tools/ dan docs/ (L6)')
