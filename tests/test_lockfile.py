"""Lockfile hash-locked harus bisa dipasang di semua Python yang didukung.

requirements.txt lama di-compile dengan pip-compile di Python 3.11, sehingga
dependensi bermarker hilang: `pip install --require-hashes` gagal di Python
3.13 (audioop-lts tidak ter-pin) dan Python 3.10 (async-timeout tidak ter-pin,
websockets 17 butuh >=3.11). install.sh menerima Python >= 3.10, jadi lockfile
wajib universal.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_pins() -> dict[str, list[str]]:
    """Nama paket -> daftar marker (string kosong bila tanpa marker)."""
    pins: dict[str, list[str]] = {}
    with open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8') as handle:
        for line in handle:
            match = re.match(r'^([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?==[^\s;\\]+\s*(?:;\s*([^\\]+?))?\s*\\?$', line.rstrip())
            if match:
                pins.setdefault(match.group(1).lower(), []).append((match.group(2) or '').strip())
    return pins


class LockfileTests(unittest.TestCase):
    def test_lockfile_is_universal(self):
        with open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8') as handle:
            header = ''.join(handle.readline() for _ in range(3))
        self.assertIn('--universal', header, 'requirements.txt harus di-compile dengan --universal')

    def test_python_313_deps_are_pinned(self):
        """discord.py butuh audioop-lts di Python >= 3.13 (audioop dihapus dari stdlib)."""
        markers = read_pins().get('audioop-lts')
        self.assertIsNotNone(markers, 'audioop-lts tidak ter-pin: install gagal di Python 3.13+')
        self.assertTrue(all('3.13' in m for m in markers), markers)

    def test_python_310_deps_are_pinned(self):
        """aiohttp butuh async-timeout di Python < 3.11."""
        markers = read_pins().get('async-timeout')
        self.assertIsNotNone(markers, 'async-timeout tidak ter-pin: install gagal di Python 3.10')
        self.assertTrue(all('3.11' in m for m in markers), markers)

    def test_direct_dependencies_pinned(self):
        pins = read_pins()
        for name in ('discord-py', 'yt-dlp', 'pynacl', 'davey'):
            self.assertIn(name, pins, f'{name} hilang dari requirements.txt')

    def test_every_pin_has_hash(self):
        with open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8') as handle:
            text = handle.read()
        blocks = re.split(r'\n(?=[A-Za-z0-9])', text)
        for block in blocks:
            if '==' in block.splitlines()[0]:
                self.assertIn('--hash=sha256:', block, block.splitlines()[0])


if __name__ == '__main__':
    unittest.main()
