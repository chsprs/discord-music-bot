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

    def test_pip_install_uses_upgrade(self):
        """Tanpa --upgrade, pip memasang pin yang sama -> tidak pernah naik."""
        installs = re.findall(r'pip["\s]*install[^\n|;]*', self.src)
        installs += re.findall(r'VENV_PIP"?\)?\s+install[^\n]*', self.src)
        joined = ' '.join(installs)
        self.assertTrue(installs, 'tidak menemukan pemanggilan pip install di update.sh')
        self.assertIn('--upgrade', joined,
                      'pip install di update.sh harus memakai --upgrade, '
                      'kalau tidak yt-dlp tidak pernah diperbarui')

    def test_pip_target_is_unpinned(self):
        """Target pip tidak boleh `yt-dlp[default]==<versi>` (pin = no-op)."""
        match = re.search(r'pip[^\n]*install[^\n]*', self.src)
        self.assertIsNotNone(match)
        line = match.group(0)
        self.assertNotRegex(line, r'yt-dlp(\[default\])?==',
                            'target pip di update.sh tidak boleh di-pin dengan ==')

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

    def test_requirements_pin_is_synced(self):
        """Versi baru harus ditulis kembali ke requirements.txt."""
        self.assertIn('requirements.txt', self.src)
        self.assertRegex(self.src, r'sed -i.*yt-dlp',
                         'versi baru harus disinkronkan ke requirements.txt')

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
            handle.write('#!/bin/bash\necho "$@" >> "$BOT_DIR/pip_calls.txt"\nexit 0\n')
        os.chmod(pip, 0o755)
        real_py = os.path.realpath(sys.executable)
        py = os.path.join(bot_dir, 'venv', 'bin', 'python')
        with open(py, 'w', encoding='utf-8') as handle:
            handle.write(
                '#!/bin/bash\n'
                'if [[ "$1" == "-c" ]]; then echo "2026.9.9"; exit 0; fi\n'
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
        with open(os.path.join(bot_dir, 'state.json'), 'w', encoding='utf-8') as handle:
            json.dump(state, handle)
        return bot_dir

    def _run(self, bot_dir: str, extra_env: dict) -> subprocess.CompletedProcess:
        env = dict(os.environ, BOT_DIR=bot_dir, BOT_STATE_FILE=os.path.join(bot_dir, 'state.json'))
        env.update(extra_env)
        # systemctl palsu: selalu "active" agar jalur restart teruji.
        fake_bin = os.path.join(bot_dir, 'fakebin')
        os.makedirs(fake_bin, exist_ok=True)
        sc = os.path.join(fake_bin, 'systemctl')
        with open(sc, 'w', encoding='utf-8') as handle:
            handle.write('#!/bin/bash\necho "$@" >> "$BOT_DIR/systemctl_calls.txt"\n'
                         'if [[ "$1" == "is-active" ]]; then exit 0; fi\nexit 0\n')
        os.chmod(sc, 0o755)
        env['PATH'] = fake_bin + os.pathsep + env.get('PATH', '')
        return subprocess.run(['bash', SCRIPT], capture_output=True, text=True, env=env, timeout=60)

    def test_upgrade_flag_reaches_pip(self):
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'pip_calls.txt'))
            self.assertIn('--upgrade', calls,
                          'pip dipanggil tanpa --upgrade: yt-dlp tidak akan pernah naik')
            self.assertIn('yt-dlp', calls)

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
            os.remove(os.path.join(bot_dir, 'state.json'))
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'systemctl_calls.txt'))
            self.assertIn('restart', calls,
                          'tanpa state.json restart harus tetap jalan')

    def test_corrupt_state_file_allows_restart(self):
        """state.json rusak tidak boleh membuat update gagal permanen."""
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            with open(os.path.join(bot_dir, 'state.json'), 'w', encoding='utf-8') as handle:
                handle.write('{bukan json')
            proc = self._run(bot_dir, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = read_text(os.path.join(bot_dir, 'systemctl_calls.txt'))
            self.assertIn('restart', calls)

    def test_requirements_pin_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            bot_dir = self._make_fake_venv(tmp, listeners=0)
            self._run(bot_dir, {})
            pins = read_text(os.path.join(bot_dir, 'requirements.txt'))
            self.assertIn('yt-dlp[default]==2026.9.9', pins,
                          'requirements.txt tidak disinkronkan ke versi baru')
            self.assertIn('discord.py[voice]==2.7.1', pins,
                          'baris dependensi lain tidak boleh hilang')


if __name__ == '__main__':
    unittest.main()
