"""Uji deploy.sh (pembaruan kode dari GitHub lewat web panel) tanpa systemd/pip sungguhan.

Repo git asli dipakai: origin bare + clone sebagai direktori bot. systemctl,
runuser, dan venv/bin/{pip,python} diganti tiruan yang mencatat panggilan.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, 'deploy.sh')
UNIT = os.path.join(ROOT, 'discord-music-deploy.service')
GIT_ENV = {
    'GIT_AUTHOR_NAME': 'uji', 'GIT_AUTHOR_EMAIL': 'uji@example.com',
    'GIT_COMMITTER_NAME': 'uji', 'GIT_COMMITTER_EMAIL': 'uji@example.com',
    'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
}


def read(path):
    if not os.path.exists(path):
        return ''
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def write(path, text, mode=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    if mode:
        os.chmod(path, mode)


@unittest.skipUnless(shutil.which('git') and shutil.which('flock'), 'butuh git dan flock')
class DeployScriptTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self.origin = os.path.join(self.tmp, 'origin.git')
        self.seed = os.path.join(self.tmp, 'seed')
        self.app = os.path.join(self.tmp, 'app')
        self.calls = os.path.join(self.tmp, 'calls')
        self.systemd_dir = os.path.join(self.tmp, 'systemd')
        os.makedirs(self.calls)
        os.makedirs(self.systemd_dir)
        self.git('init', '--bare', '--initial-branch=main', self.origin, cwd=self.tmp)
        self.git('clone', self.origin, self.seed, cwd=self.tmp)
        write(os.path.join(self.seed, 'bot.py'), 'print("v1")\n')
        write(os.path.join(self.seed, 'panel.py'), 'print("panel v1")\n')
        write(os.path.join(self.seed, 'requirements.txt'), 'yt-dlp==1\n')
        write(os.path.join(self.seed, 'discord-music.service'), '[Service]\nExecStart=/bin/true\n')
        write(os.path.join(self.seed, '.gitignore'), 'venv/\nlast_deploy.log\n.deploy.lock\n')
        self.commit('awal')
        self.git('push', '-q', 'origin', 'HEAD:main', cwd=self.seed)
        self.git('clone', '-q', '--branch', 'main', self.origin, self.app, cwd=self.tmp)
        self._fake_tools()
        self.listeners(0)

    # ---- helper -------------------------------------------------------
    def git(self, *args, cwd):
        env = dict(os.environ, **GIT_ENV)
        return subprocess.run(['git', *args], cwd=cwd, env=env, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git('add', '-A', cwd=self.seed)
        self.git('commit', '-q', '-m', message, cwd=self.seed)

    def upstream(self, path, text, message):
        write(os.path.join(self.seed, path), text)
        self.commit(message)
        self.git('push', '-q', 'origin', 'HEAD:main', cwd=self.seed)

    def head(self):
        return self.git('rev-parse', 'HEAD', cwd=self.app)

    def listeners(self, count, age=0.0):
        write(os.path.join(self.tmp, 'run', 'listeners.json'),
              json.dumps({'total_listeners': count, 'updated_at': time.time() - age}))

    def _fake_tools(self):
        fakebin = os.path.join(self.tmp, 'fakebin')
        write(os.path.join(fakebin, 'systemctl'),
              '#!/bin/bash\necho "$@" >> "$CALLS/systemctl"\n'
              'if [[ "$1" == is-active ]]; then exit "${FAKE_BOT_INACTIVE:-0}"; fi\nexit 0\n', 0o755)
        write(os.path.join(fakebin, 'runuser'),
              '#!/bin/bash\necho "$@" >> "$CALLS/runuser"\n'
              'while [[ "$1" != "--" ]]; do shift; done; shift\nexec "$@"\n', 0o755)
        venv = os.path.join(self.app, 'venv', 'bin')
        write(os.path.join(venv, 'pip'), '#!/bin/bash\necho "$@" >> "$CALLS/pip"\nexit "${FAKE_PIP_RC:-0}"\n', 0o755)
        write(os.path.join(venv, 'python'),
              '#!/bin/bash\necho "$@" >> "$CALLS/tests"\necho "Ran 3 tests"\nexit "${FAKE_TESTS_RC:-0}"\n', 0o755)
        self.fakebin = fakebin

    def run_deploy(self, mode, **env_extra):
        env = dict(os.environ, **GIT_ENV)
        env.update(BOT_DIR=self.app, SYSTEMD_DIR=self.systemd_dir, CALLS=self.calls,
                   BOT_STATE_FILE=os.path.join(self.tmp, 'run', 'state.json'),
                   UPDATER_USER='nobody', PATH=self.fakebin + os.pathsep + os.environ['PATH'],
                   TMPDIR=self.tmp)
        env.update({k: str(v) for k, v in env_extra.items()})
        return subprocess.run(['bash', SCRIPT, mode], env=env, capture_output=True, text=True, timeout=60)

    def calls_of(self, name):
        return read(os.path.join(self.calls, name))

    def deploy_log(self):
        return read(os.path.join(self.app, 'last_deploy.log'))

    # ---- statis --------------------------------------------------------
    def test_script_and_unit_are_sane(self):
        self.assertEqual(subprocess.run(['bash', '-n', SCRIPT]).returncode, 0)
        self.assertTrue(os.access(SCRIPT, os.X_OK), 'deploy.sh harus executable di git')
        src = read(SCRIPT)
        self.assertIn('set -euo pipefail', src)
        self.assertIn('--ff-only', src)
        self.assertIn('flock', src)
        self.assertIn('--require-hashes', src)
        unit = read(UNIT)
        self.assertIn('Type=oneshot', unit)
        self.assertIn('ExecStart=/opt/discord-music-bot/deploy.sh apply', unit)
        sections = [line.strip() for line in unit.splitlines() if line.strip().startswith('[')]
        self.assertNotIn('[Install]', sections, 'deploy tidak boleh jalan otomatis saat boot')
        self.assertFalse(any(line.startswith('User=') for line in unit.splitlines()),
                         'deploy harus root (memperbarui checkout & unit milik root)')

    # ---- check ---------------------------------------------------------
    def test_check_lists_new_commits_without_changing_anything(self):
        before = self.head()
        self.upstream('bot.py', 'print("v2")\n', 'fitur baru di bot')
        self.upstream('panel.py', 'print("panel v2")\n', 'perbaiki panel')
        proc = self.run_deploy('check')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('2 commit baru siap diterapkan', proc.stdout)
        self.assertIn('fitur baru di bot', proc.stdout)
        self.assertIn('perbaiki panel', proc.stdout)
        self.assertIn('bot.py', proc.stdout)
        self.assertIn('restart bot', proc.stdout)
        self.assertIn('restart panel', proc.stdout)
        self.assertEqual(self.head(), before)
        self.assertEqual(self.calls_of('systemctl'), '')

    def test_check_up_to_date(self):
        proc = self.run_deploy('check')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('sudah versi terbaru', proc.stdout)

    # ---- apply ---------------------------------------------------------
    def test_apply_fast_forwards_tests_and_restarts_bot(self):
        self.upstream('bot.py', 'print("v2")\n', 'bot v2')
        target = self.git('rev-parse', 'HEAD', cwd=self.seed)
        proc = self.run_deploy('apply')
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertEqual(self.head(), target)
        self.assertIn('unittest discover', self.calls_of('tests'))
        self.assertIn('-u nobody', self.calls_of('runuser'), 'tes harus jalan sebagai user updater')
        self.assertIn('restart discord-music.service', self.calls_of('systemctl'))
        self.assertNotIn('discord-music-panel.service', self.calls_of('systemctl'))
        self.assertEqual(self.calls_of('pip'), '', 'pip tidak perlu bila requirements.txt tidak berubah')
        self.assertIn('Status: Sukses', self.deploy_log())

    def test_apply_defers_bot_restart_when_listeners_present(self):
        self.listeners(2)
        self.upstream('bot.py', 'print("v2")\n', 'bot v2')
        proc = self.run_deploy('apply')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('restart discord-music.service', self.calls_of('systemctl'))
        self.assertIn('ditunda', self.deploy_log())

    def test_stale_listener_state_does_not_block_restart(self):
        self.listeners(5, age=300)
        self.upstream('bot.py', 'print("v2")\n', 'bot v2')
        self.assertEqual(self.run_deploy('apply').returncode, 0)
        self.assertIn('restart discord-music.service', self.calls_of('systemctl'))

    def test_failed_tests_roll_back_and_keep_old_code(self):
        before = self.head()
        self.upstream('bot.py', 'print("rusak")\n', 'bot rusak')
        proc = self.run_deploy('apply', FAKE_TESTS_RC=1)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.head(), before, 'kode harus dikembalikan bila tes gagal')
        self.assertEqual(read(os.path.join(self.app, 'bot.py')), 'print("v1")\n')
        self.assertNotIn('restart', self.calls_of('systemctl'))
        self.assertIn('dikembalikan', self.deploy_log())

    def test_requirements_change_installs_deps_as_updater(self):
        self.upstream('requirements.txt', 'yt-dlp==2\n', 'bump yt-dlp')
        proc = self.run_deploy('apply')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('--require-hashes', self.calls_of('pip'))
        self.assertIn('requirements.txt', self.calls_of('pip'))
        self.assertIn('restart discord-music.service', self.calls_of('systemctl'))

    def test_failed_pip_rolls_back(self):
        before = self.head()
        self.upstream('requirements.txt', 'yt-dlp==2\n', 'bump yt-dlp')
        proc = self.run_deploy('apply', FAKE_PIP_RC=1)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.head(), before)
        self.assertEqual(self.calls_of('tests'), '', 'tes tidak perlu jalan bila pip gagal')

    def test_unit_and_panel_changes(self):
        self.upstream('discord-music.service', '[Service]\nExecStart=/bin/false\n', 'ubah unit bot')
        self.upstream('panel.py', 'print("panel v2")\n', 'panel v2')
        proc = self.run_deploy('apply')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('ExecStart=/bin/false', read(os.path.join(self.systemd_dir, 'discord-music.service')))
        systemctl = self.calls_of('systemctl')
        self.assertIn('daemon-reload', systemctl)
        self.assertIn('restart --no-block discord-music-panel.service', systemctl)
        self.assertIn('restart discord-music.service', systemctl)

    def test_dirty_tree_is_refused(self):
        before = self.head()
        write(os.path.join(self.app, 'bot.py'), 'print("edit lokal")\n')
        self.upstream('bot.py', 'print("v2")\n', 'bot v2')
        proc = self.run_deploy('apply')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.head(), before)
        self.assertEqual(read(os.path.join(self.app, 'bot.py')), 'print("edit lokal")\n', 'edit lokal tidak boleh hilang')
        self.assertIn('perubahan lokal', self.deploy_log())

    def test_diverged_history_is_refused(self):
        write(os.path.join(self.app, 'lokal.txt'), 'x\n')
        self.git('add', 'lokal.txt', cwd=self.app)
        self.git('commit', '-q', '-m', 'commit lokal', cwd=self.app)
        before = self.head()
        self.upstream('bot.py', 'print("v2")\n', 'bot v2')
        proc = self.run_deploy('apply')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.head(), before)
        self.assertIn('bukan fast-forward', self.deploy_log())

    def test_up_to_date_apply_does_nothing(self):
        proc = self.run_deploy('apply')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('Sudah versi terbaru', self.deploy_log())
        self.assertEqual(self.calls_of('systemctl'), '')
        self.assertEqual(self.calls_of('tests'), '')

    def test_not_a_git_checkout_explains_bootstrap(self):
        shutil.rmtree(os.path.join(self.app, '.git'))
        proc = self.run_deploy('check')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('bukan checkout git', proc.stdout)

    def test_bot_inactive_is_not_started(self):
        self.upstream('bot.py', 'print("v2")\n', 'bot v2')
        proc = self.run_deploy('apply', FAKE_BOT_INACTIVE=3)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('restart discord-music.service', self.calls_of('systemctl'))
        self.assertIn('Bot tidak aktif', self.deploy_log())


if __name__ == '__main__':
    unittest.main()
