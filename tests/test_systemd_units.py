"""Uji hardening unit systemd tanpa menyentuh systemd sungguhan.

P5: panel mengendalikan systemctl sebagai root. Unit harus memakai sandbox
systemd seluas mungkin; menambah directive baru mudah, menghapusnya juga —
test ini menahan agar tidak ada yang hilang tanpa sengaja.
"""
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_unit(name: str) -> str:
    with open(os.path.join(ROOT, name), encoding='utf-8') as handle:
        return handle.read()


class PanelUnitHardeningTests(unittest.TestCase):
    def setUp(self):
        self.unit = read_unit('discord-music-panel.service')

    def test_required_sandbox_directives(self):
        """Directive yang wajib ada agar panel tidak bisa kabur dari sandbox."""
        required = [
            'NoNewPrivileges=true',
            'PrivateTmp=true',
            'ProtectSystem=strict',
            'ProtectHome=true',
            'PrivateDevices=true',
            'ProtectKernelTunables=true',
            'ProtectKernelModules=true',
            'ProtectKernelLogs=true',
            'ProtectControlGroups=true',
            'ProtectClock=true',
            'RestrictNamespaces=true',
            'RestrictRealtime=true',
            'RestrictSUIDSGID=true',
            'LockPersonality=true',
            'RemoveIPC=true',
            'UMask=0077',
        ]
        for directive in required:
            self.assertIn(directive, self.unit,
                          f'{directive} hilang dari unit panel')

    def test_readwrite_paths_still_present(self):
        """Tanpa ReadWritePaths, ProtectSystem=strict mematahkan /save (EROFS)."""
        self.assertIn('ReadWritePaths=/opt/discord-music-bot', self.unit,
                      'ReadWritePaths hilang: simpan konfigurasi akan EROFS')

    def test_address_families_restricted(self):
        """Panel cuma butuh unix/inet/inet6/netlink."""
        directive = self._directive('RestrictAddressFamilies')
        self.assertIsNotNone(directive, 'RestrictAddressFamilies hilang')
        for family in ('AF_UNIX', 'AF_INET', 'AF_INET6', 'AF_NETLINK'):
            self.assertIn(family, directive)
        self.assertNotIn('AF_PACKET', directive,
                         'AF_PACKET (raw socket) tidak diperlukan panel')

    def _directive(self, key: str):
        """Ambil nilai directive dari unit, mengabaikan komentar."""
        for line in self.unit.splitlines():
            stripped = line.strip()
            if stripped.startswith('#') or '=' not in stripped:
                continue
            name, _, value = stripped.partition('=')
            if name.strip() == key:
                return value.strip()
        return None

    def test_umask_is_restrictive(self):
        self.assertIn('UMask=0077', self.unit,
                      'UMask harus 0077 agar berkas panel tidak world-readable')

    def test_memory_and_task_limits(self):
        self.assertIn('MemoryMax=', self.unit)
        self.assertIn('TasksMax=', self.unit)

    def test_unit_is_valid(self):
        """systemd-analyze verify harus menerima unit (tanpa error)."""
        path = os.path.join(ROOT, 'discord-music-panel.service')
        proc = subprocess.run(['systemd-analyze', 'verify', path],
                              capture_output=True, text=True, timeout=60)
        # systemd-analyze verify mengembalikan 0 walau ada warning; hanya
        # kegagalan parsing yang kita anggap fatal.
        output = proc.stdout + proc.stderr
        self.assertNotIn('Failed to parse', output)
        self.assertNotIn('Unknown key', output)


class BotUnitHardeningTests(unittest.TestCase):
    def setUp(self):
        self.unit = read_unit('discord-music.service')

    def test_bot_has_resource_limits(self):
        self.assertIn('MemoryMax=', self.unit)
        self.assertIn('TasksMax=', self.unit)

    def test_bot_runs_as_dynamic_user(self):
        """Bot tidak boleh jalan sebagai root."""
        self.assertIn('DynamicUser=yes', self.unit,
                      'bot harus DynamicUser=yes, bukan root')

    def test_bot_sandbox(self):
        for directive in ('NoNewPrivileges=true', 'ProtectSystem=strict',
                          'ProtectHome=true', 'PrivateTmp=true'):
            self.assertIn(directive, self.unit,
                          f'{directive} hilang dari unit bot')

    def test_bot_writes_only_runtime_dir(self):
        """Bot hanya perlu tulis ke RuntimeDirectory (state exporter)."""
        self.assertIn('RuntimeDirectory=discord-music', self.unit)

    def test_bot_umask_is_restrictive(self):
        """L3: state.json memuat nama guild/lagu/pendengar — jangan world-readable."""
        self.assertIn('UMask=', self.unit,
                      'bot harus menetapkan UMask agar berkas runtime tidak world-readable')
        directive = self._directive('UMask')
        self.assertIsNotNone(directive)
        # UMask=0027 -> bit group/other tidak boleh longgar (nilai harus <= 0027).
        self.assertLessEqual(int(directive, 8), 0o027,
                             f'UMask {directive} terlalu longgar untuk berkas runtime bot')

    def _directive(self, key: str):
        for line in self.unit.splitlines():
            stripped = line.strip()
            if stripped.startswith('#') or '=' not in stripped:
                continue
            name, _, value = stripped.partition('=')
            if name.strip() == key:
                return value.strip()
        return None


if __name__ == '__main__':
    unittest.main()
