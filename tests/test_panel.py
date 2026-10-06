import http.client
import json
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

import panel


def _no_systemd(action):
    """Pengganti systemctl untuk unit test.

    Tanpa ini, POST /start|/restart|/stop dari suite benar-benar menjalankan
    `systemctl <action> discord-music.service` dan MEMATIKAN bot produksi.
    """
    return True, ''


def _no_update():
    """Pengganti update.sh untuk unit test.

    Tanpa ini, POST /update dari suite menjalankan update.sh sungguhan:
    pip install -U yt-dlp lalu `systemctl restart discord-music.service`.
    """
    return True, '[uji] pembaruan dilewati'


# Pasang sekali di tingkat modul, sebelum test apa pun berjalan. Kedua hook ini
# adalah jaring pengaman: suite harus bisa dijalankan di server produksi tanpa
# menyentuh systemd atau memasang paket.
panel.SERVICE_RUNNER = _no_systemd
panel.UPDATE_RUNNER = _no_update


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        self.cfg = panel.ConfigStore(self.env)
        panel.STORE = self.cfg
        panel.PASSWORD = 'rahasia-uji'
        # M7: cegah kebocoran state antar-test (flash/pesan sesi/token/cache log).
        panel._flash_msg = ''
        panel._sessions.clear()
        panel._form_tokens.clear()
        panel._log_cache.clear()
        self.server = panel.build_server('127.0.0.1', 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.tmp.cleanup)

    def req(self, method, path, body=None, headers=None, cookie=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        hdrs = dict(headers or {})
        if cookie:
            hdrs['Cookie'] = cookie
        if body is not None:
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
            if 'Origin' not in hdrs:
                hdrs['Origin'] = f'http://127.0.0.1:{self.port}'
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload, res.getheader('Set-Cookie')

    def login(self):
        status, _, cookie = self.req('POST', '/login', 'password=rahasia-uji')
        self.assertEqual(status, 303)
        return cookie.split(';')[0]

    def test_unauthenticated_api_returns_401(self):
        status, _, _ = self.req('GET', '/api/status')
        self.assertEqual(status, 401)

    def test_unauthenticated_page_redirects_to_login(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/')
        res = conn.getresponse()
        res.read()
        location = res.getheader('Location') or ''
        conn.close()
        self.assertEqual(res.status, 303)
        self.assertIn('/login', location)

    def test_wrong_password_is_rejected(self):
        status, _, _ = self.req('POST', '/login', 'password=salah')
        self.assertEqual(status, 403)

    def test_save_requires_authentication(self):
        status, _, _ = self.req('POST', '/save', 'token=a&guild=1')
        self.assertIn(status, (401, 403))

    def test_cross_site_post_is_rejected(self):
        cookie = self.login()
        status, _, _ = self.req('POST', '/save', 'token=a&guild=1',
                                headers={'Origin': 'http://evil.example'}, cookie=cookie)
        self.assertEqual(status, 403)

    def test_missing_origin_post_is_rejected(self):
        cookie = self.login()
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('POST', '/save', body='token=a&guild=1',
                     headers={'Content-Type': 'application/x-www-form-urlencoded', 'Cookie': cookie})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 403)

    def test_unsupported_method_returns_405(self):
        status, _, _ = self.req('PUT', '/')
        self.assertEqual(status, 405)

    def test_security_headers_present(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/login')
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.getheader('X-Frame-Options'), 'DENY')
        self.assertEqual(res.getheader('X-Content-Type-Options'), 'nosniff')
        self.assertIn('Content-Security-Policy', res.headers)

    def test_save_persists_and_never_echoes_token(self):
        cookie = self.login()
        valid_token = 'MTAwMDAwMDAwMDAwMDAwMDAw.G12345.abcdefghijklmnopqrstuvwxyz0123456789'
        valid_guild = '123456789012345678'
        status, body, _ = self.req('POST', '/save', f'token={valid_token}&guild={valid_guild}', cookie=cookie)
        self.assertEqual(status, 303)
        self.assertNotIn(valid_token, body)
        saved = self.cfg.read()
        self.assertEqual(saved['token'], valid_token)
        self.assertEqual(saved['guild'], valid_guild)
        if os.name == 'posix':
            mode = stat.S_IMODE(os.stat(self.env).st_mode)
            self.assertEqual(mode, 0o600)

    def test_status_masks_token(self):
        self.cfg.write({'token': 'abcdefghijklmnop', 'guild': '42'})
        cookie = self.login()
        status, body, _ = self.req('GET', '/api/status', cookie=cookie)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertNotIn('abcdefghijklmnop', body)
        self.assertTrue(data['token_set'])
        self.assertEqual(data['guild'], '42')
        self.assertIn(data['bot'], ('unknown', 'active', 'inactive'))
        self.assertIn('total_guilds', data)
        self.assertIn('active_voice_count', data)
        self.assertIn('total_listeners', data)
        # Endpoint status tidak lagi mengirim roster listener / potongan token.
        self.assertNotIn('token_hint', data)
        self.assertNotIn('guilds', data)
        self.assertIsInstance(data['guild_count'], int)

    def test_format_guilds_html_connected_and_standby(self):
        info = {
            'status': 'online',
            'total_guilds': 2,
            'active_voice_count': 1,
            'total_listeners': 2,
            'guilds': [
                {
                    'id': '101',
                    'name': 'Komunitas Musik',
                    'member_count': 50,
                    'connected': True,
                    'channel_name': 'Stage 1',
                    'listeners': ['budi', 'ani'],
                    'listener_count': 2,
                    'is_playing': True,
                    'is_paused': False,
                    'current_track': 'Lagu Asik',
                    'queue_len': 3,
                },
                {
                    'id': '102',
                    'name': 'Tongkrongan Santai',
                    'member_count': 12,
                    'connected': False,
                    'channel_name': None,
                    'listeners': [],
                    'listener_count': 0,
                    'is_playing': False,
                    'is_paused': False,
                    'current_track': None,
                    'queue_len': 0,
                },
            ]
        }
        html_out = panel.format_guilds_html(info)
        self.assertIn('Komunitas Musik', html_out)
        self.assertIn('Stage 1', html_out)
        self.assertIn('Lagu Asik', html_out)
        self.assertIn('2 user', html_out)
        self.assertIn('budi, ani', html_out)
        self.assertIn('Tongkrongan Santai', html_out)
        self.assertIn('Standby', html_out)

    def test_start_requires_authentication(self):
        status, _, _ = self.req('POST', '/start')
        self.assertIn(status, (401, 403))

    def test_incomplete_config_cannot_start(self):
        self.cfg.write({'token': '', 'guild': ''})
        cookie = self.login()
        status, body, _ = self.req('POST', '/start', '', cookie=cookie)
        self.assertEqual(status, 400)
        self.assertIn('Token Discord belum diisi', body)

    def test_update_requires_authentication(self):
        status, _, _ = self.req('POST', '/update')
        self.assertIn(status, (401, 403))

    def test_update_executes_and_displays_log(self):
        cookie = self.login()
        panel.UPDATE_RUNNER = lambda: (True, '[Mock] yt-dlp updated successfully v2026.09.01')
        self.addCleanup(setattr, panel, 'UPDATE_RUNNER', _no_update)
        status, body, _ = self.req('POST', '/update', '', cookie=cookie)
        # PRG: POST redirect 303, pesan via flash di GET berikutnya.
        self.assertEqual(status, 303)
        status, body, _ = self.req('GET', '/', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Pembaruan yt-dlp berhasil dijalankan', body)
        self.assertIn('yt-dlp updated successfully', body)

    def test_api_logs_requires_authentication(self):
        status, _, _ = self.req('GET', '/api/logs')
        self.assertEqual(status, 401)

    def test_api_logs_returns_payload(self):
        cookie = self.login()
        status, body, _ = self.req('GET', '/api/logs', cookie=cookie)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn('bot_logs', data)
        self.assertIn('update_log', data)
        self.assertIn('ytdlp_version', data)


class ConfigStoreTests(unittest.TestCase):
    def test_read_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = panel.ConfigStore(os.path.join(tmp, 'none.env'))
            self.assertEqual(store.read(), {'token': '', 'guild': ''})

    def test_write_then_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = panel.ConfigStore(os.path.join(tmp, '.env'))
            store.write({'token': 't', 'guild': 'g'})
            self.assertEqual(store.read(), {'token': 't', 'guild': 'g'})

    def test_write_rejects_newline_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = panel.ConfigStore(os.path.join(tmp, '.env'))
            with self.assertRaises(ValueError):
                store.write({'token': 'a\nEVIL=x', 'guild': ''})

    def test_write_preserves_unmanaged_keys(self):
        """Key lain di .env (mis. BOT_STATE_FILE) tidak boleh terhapus saat save."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, '.env')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('DISCORD_TOKEN=old\n'
                             'BOT_STATE_FILE=/run/x/state.json\n'
                             'DISCORD_GUILD_ID=1\n'
                             'YOUTUBE_API_KEY=rahasia\n')
            store = panel.ConfigStore(path)
            store.write({'token': 'new', 'guild': '2'})
            with open(path, encoding='utf-8') as handle:
                body = handle.read()
            self.assertIn('DISCORD_TOKEN=new', body)
            self.assertIn('DISCORD_GUILD_ID=2', body)
            self.assertIn('BOT_STATE_FILE=/run/x/state.json', body)
            self.assertIn('YOUTUBE_API_KEY=rahasia', body)
            self.assertNotIn('DISCORD_TOKEN=old', body)
            self.assertEqual(store.read(), {'token': 'new', 'guild': '2'})

    def test_write_preserves_foreign_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, '.env')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('# komentar operator\n'
                             'DISCORD_TOKEN=old\n'
                             'BOT_STATE_FILE=/run/x/state.json\n')
            store = panel.ConfigStore(path)
            store.write({'token': 'new', 'guild': '2'})
            with open(path, encoding='utf-8') as handle:
                body = handle.read()
            self.assertIn('# komentar operator', body)
            self.assertIn('BOT_STATE_FILE=/run/x/state.json', body)

    def test_write_is_atomic_no_partial_file_on_success(self):
        """Tidak ada berkas .tmp yang tertinggal dan isi lama tetap utuh sampai sukses."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, '.env')
            store = panel.ConfigStore(path)
            store.write({'token': 'first', 'guild': '1'})
            store.write({'token': 'second', 'guild': '2'})
            leftovers = [f for f in os.listdir(tmp) if f.endswith('.tmp')]
            self.assertEqual(leftovers, [])
            self.assertEqual(store.read()['token'], 'second')

    def test_write_concurrent_calls_never_corrupt(self):
        """Dua /save bersamaan tidak boleh meninggalkan .env rusak.

        Di POSIX (target produksi) rename bersifat atomik sehingga tidak boleh
        ada error sama sekali. Di Windows, `os.replace` bisa gagal sementara
        bila berkas sedang dibaca proses lain — itu keterbatasan OS, bukan bug
        panel, jadi toleransi diberikan di sana.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, '.env')
            store = panel.ConfigStore(path)
            store.write({'token': 'seed', 'guild': '1'})
            errors = []

            def worker(n):
                try:
                    for _ in range(25):
                        store.write({'token': f'tok{n}', 'guild': str(n)})
                        store.read()
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            if os.name == 'posix':
                self.assertEqual(errors, [], f'error saat write bersamaan: {errors}')
            data = store.read()
            self.assertTrue(data['token'].startswith('tok'))
            self.assertTrue(data['guild'].isdigit())
            self.assertEqual([f for f in os.listdir(tmp) if f.endswith('.tmp')], [])

    def test_write_strips_export_prefix_so_saved_token_wins(self):
        """'export DISCORD_TOKEN=old' tidak boleh menimpa token yang baru disimpan."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, '.env')
            with open(path, 'w', encoding='utf-8') as handle:
                handle.write('export DISCORD_TOKEN=old\n'
                             'export DISCORD_GUILD_ID=1\n'
                             'export BOT_STATE_FILE=/run/x/state.json\n')
            store = panel.ConfigStore(path)
            store.write({'token': 'new', 'guild': '2'})
            self.assertEqual(store.read(), {'token': 'new', 'guild': '2'})
            with open(path, encoding='utf-8') as handle:
                body = handle.read()
            self.assertEqual(body.count('DISCORD_TOKEN='), 1)
            self.assertIn('export BOT_STATE_FILE=/run/x/state.json', body)


class RateLimitTests(unittest.TestCase):
    """Rate limit login harus atomik (bukan check-then-act)."""

    def setUp(self):
        self._saved = dict(panel._attempts)
        panel._attempts.clear()
        self.addCleanup(self._restore)

    def _restore(self):
        panel._attempts.clear()
        panel._attempts.update(self._saved)

    def test_reserve_blocks_after_eight_attempts(self):
        for i in range(8):
            allowed, _ = panel.reserve_login_attempt('10.0.0.1')
            self.assertTrue(allowed, f'percobaan {i + 1} seharusnya boleh')
        allowed, retry = panel.reserve_login_attempt('10.0.0.1')
        self.assertFalse(allowed)
        self.assertEqual(retry, 300)

    def test_reserve_is_atomic_under_concurrency(self):
        """Tanpa reservasi atomik, N thread bisa lolos bersamaan."""
        allowed_count = []
        lock = threading.Lock()

        def worker():
            ok, _ = panel.reserve_login_attempt('10.0.0.2')
            with lock:
                allowed_count.append(ok)

        threads = [threading.Thread(target=worker) for _ in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(1 for a in allowed_count if a), 8,
                         'jumlah percobaan yang lolos harus tepat 8')

    def test_separate_peers_have_separate_budgets(self):
        for _ in range(8):
            panel.reserve_login_attempt('10.0.0.3')
        allowed, _ = panel.reserve_login_attempt('10.0.0.4')
        self.assertTrue(allowed)


class SessionTableTests(unittest.TestCase):
    """Sesi server-side harus kedaluwarsa dan tidak tumbuh tanpa batas."""

    def setUp(self):
        self._saved = dict(panel._sessions)
        panel._sessions.clear()
        self.addCleanup(self._restore)

    def _restore(self):
        panel._sessions.clear()
        panel._sessions.update(self._saved)

    def test_session_valid_then_expires(self):
        token = panel._mint_session()
        self.assertTrue(panel._session_valid(token))
        panel._sessions[token] = time.monotonic() - 1
        self.assertFalse(panel._session_valid(token))
        self.assertNotIn(token, panel._sessions)

    def test_session_table_is_bounded(self):
        saved_max = panel.MAX_SESSIONS
        panel.MAX_SESSIONS = 16
        try:
            for _ in range(64):
                panel._mint_session()
            self.assertLessEqual(len(panel._sessions), 16)
        finally:
            panel.MAX_SESSIONS = saved_max

    def test_unknown_token_rejected(self):
        self.assertFalse(panel._session_valid('tidak-ada'))
        self.assertFalse(panel._session_valid(''))


class SystemctlCacheTests(unittest.TestCase):
    """Cache systemctl tidak boleh menyimpan timestamp sebelum subprocess."""

    def setUp(self):
        self._saved_cache = dict(panel._state_cache)
        panel._state_cache.clear()
        self.addCleanup(self._restore)

    def _restore(self):
        panel._state_cache.clear()
        panel._state_cache.update(self._saved_cache)

    def test_cache_entry_is_fresh_after_slow_subprocess(self):
        """Subprocess lambat tidak boleh membuat entri langsung kedaluwarsa."""
        calls = []

        def slow_run(*args, **kwargs):
            time.sleep(0.3)
            calls.append(1)
            return unittest.mock.MagicMock(stdout='active\n')

        with unittest.mock.patch.object(panel.subprocess, 'run', side_effect=slow_run):
            first = panel._cached_systemctl('bot', panel.SERVICE, 3, 'unknown')
            second = panel._cached_systemctl('bot', panel.SERVICE, 3, 'unknown')
        self.assertEqual(first, 'active')
        self.assertEqual(second, 'active')
        self.assertEqual(len(calls), 1, 'panggilan kedua harus memakai cache')

    def test_failure_falls_back(self):
        with unittest.mock.patch.object(panel.subprocess, 'run',
                                        side_effect=OSError('systemctl hilang')):
            value = panel._cached_systemctl('bot', panel.SERVICE, 3, 'unknown')
        self.assertEqual(value, 'unknown')


class HostAllowlistTests(unittest.TestCase):
    """Host allowlist mencegah DNS-rebinding (S7)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        panel.STORE = panel.ConfigStore(os.path.join(self.tmp.name, '.env'))
        panel.PASSWORD = 'host-test'
        self.valid_token = 'MTAwMDAwMDAwMDAwMDAwMDAw.G12345.abcdefghijklmnopqrstuvwxyz0123456789'
        self.valid_guild = '123456789012345678'
        self.session_token = panel._mint_session()
        self.cookie = f'{panel.COOKIE}={self.session_token}'
        self._saved_hosts = set(panel.ALLOWED_HOSTS)
        self.server = panel.build_server('127.0.0.1', 0)
        self.port = self.server.server_address[1]
        panel.ALLOWED_HOSTS = {f'127.0.0.1:{self.port}'}
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(setattr, panel, 'ALLOWED_HOSTS', self._saved_hosts)

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        hdrs = dict(headers or {})
        if 'Cookie' not in hdrs and getattr(self, 'cookie', None):
            hdrs['Cookie'] = self.cookie
        if body is not None:
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload

    def test_foreign_host_with_matching_origin_is_rejected(self):
        """DNS-rebinding: Host & Origin palsu yang konsisten tetap ditolak."""
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}',
                             headers={'Host': 'evil.example:9130',
                                      'Origin': 'http://evil.example:9130'})
        self.assertEqual(status, 403)
        self.assertEqual(panel.ConfigStore(panel.STORE.path).read()['token'], '')

    def test_allowed_host_passes_origin_check(self):
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}',
                             headers={'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 303)

    def test_foreign_host_rejected_on_get(self):
        """DNS-rebinding juga harus diblokir untuk GET (halaman/status/log). (M2)"""
        for path in ('/', '/api/status', '/api/logs'):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
            conn.request('GET', path, headers={'Host': 'evil.example:9130'})
            res = conn.getresponse()
            res.read()
            conn.close()
            self.assertEqual(res.status, 403, f'{path} tidak menolak Host asing')

    def test_allowed_host_get_passes(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/', headers={'Host': f'127.0.0.1:{self.port}', 'Cookie': self.cookie})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 200)

    def test_loopback_host_variants_accepted(self):
        """IP loopback apa pun (127.0.0.0/8) tetap diterima."""
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/', headers={'Host': '127.0.0.5:9130', 'Cookie': self.cookie})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 200)


class DefaultAllowlistTests(unittest.TestCase):
    """Fix H2: allowlist default harus memuat alamat LAN yang dipakai installer.

    install.sh mencetak `http://${LAN_IP}:${PANEL_PORT}` dan mengisi
    PANEL_ALLOWED_HOSTS dari `hostname -I`. Kalau deteksi default melewatkan
    alamat itu, panel menolak 403 untuk URL yang justru dipromosikan sendiri.
    """

    def test_default_allowlist_includes_loopback_and_hostname_addresses(self):
        hosts = panel._default_allowed_hosts('0.0.0.0', 9130)
        self.assertIn('127.0.0.1:9130', hosts)
        self.assertIn('localhost:9130', hosts)
        self.assertIn('[::1]:9130', hosts)

    def test_default_allowlist_includes_every_local_address(self):
        """Setiap alamat yang dilaporkan _local_addresses harus diterima.

        Di-mock agar deterministik: hasil nyata bergantung NIC/DHCP mesin uji.
        """
        port = 9130
        fake = {'192.168.1.50', '10.0.0.7', 'fe80::1'}
        with unittest.mock.patch.object(panel, '_local_addresses', return_value=fake):
            hosts = panel._default_allowed_hosts('0.0.0.0', port)
        self.assertIn('192.168.1.50:9130', hosts)
        self.assertIn('10.0.0.7:9130', hosts)
        self.assertIn('[fe80::1]:9130', hosts)

    def test_lan_address_from_installer_is_accepted(self):
        """Simulasi alur install.sh: LAN_IP:PORT dari `hostname -I` harus lolos."""
        port = 9130
        lan_ip = '192.168.1.50'
        saved = panel.ALLOWED_HOSTS
        with unittest.mock.patch.object(panel, '_local_addresses', return_value={lan_ip}):
            panel.ALLOWED_HOSTS = panel._default_allowed_hosts('0.0.0.0', port)
        try:
            handler = panel.Handler.__new__(panel.Handler)
            self.assertTrue(handler._host_ok(f'{lan_ip}:{port}'),
                            'Host dari hostname -I ditolak -> panel 403 di URL installer')
        finally:
            panel.ALLOWED_HOSTS = saved

    def test_real_local_addresses_are_accepted(self):
        """Tanpa mock: alamat nyata mesin ini juga harus diterima (bila ada)."""
        port = 9130
        local = panel._local_addresses()
        if not local:
            self.skipTest('mesin uji tidak melaporkan alamat lokal')
        saved = panel.ALLOWED_HOSTS
        panel.ALLOWED_HOSTS = panel._default_allowed_hosts('0.0.0.0', port)
        try:
            handler = panel.Handler.__new__(panel.Handler)
            for addr in local:
                host_header = f'[{addr}]:{port}' if ':' in addr else f'{addr}:{port}'
                self.assertTrue(handler._host_ok(host_header),
                                f'Host {host_header} (dari hostname -I) ditolak')
        finally:
            panel.ALLOWED_HOSTS = saved

    def test_explicit_allowed_host_env_is_honoured(self):
        """PANEL_ALLOWED_HOSTS eksplisit tidak boleh ditimpa oleh autodetect."""
        saved = panel.ALLOWED_HOSTS
        panel.ALLOWED_HOSTS = {'panel.local:9130'}
        try:
            handler = panel.Handler.__new__(panel.Handler)
            self.assertTrue(handler._host_ok('panel.local:9130'))
            self.assertFalse(handler._host_ok('evil.example:9130'))
        finally:
            panel.ALLOWED_HOSTS = saved

    def test_ipv6_bracket_host_matching(self):
        saved = panel.ALLOWED_HOSTS
        panel.ALLOWED_HOSTS = {'[::1]:9130'}
        try:
            handler = panel.Handler.__new__(panel.Handler)
            self.assertTrue(handler._host_ok('[::1]:9130'))
        finally:
            panel.ALLOWED_HOSTS = saved

    def test_default_port_omits_port_in_host(self):
        """Pada port 80/443 browser mengirim Host tanpa port."""
        hosts = panel._default_allowed_hosts('0.0.0.0', 80)
        self.assertIn('127.0.0.1', hosts)
        handler = panel.Handler.__new__(panel.Handler)
        saved = panel.ALLOWED_HOSTS
        panel.ALLOWED_HOSTS = hosts
        try:
            self.assertTrue(handler._host_ok('127.0.0.1'))
        finally:
            panel.ALLOWED_HOSTS = saved


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        panel.STORE = panel.ConfigStore(self.env)
        panel.PASSWORD = 'robust-test'
        self.session_token = panel._mint_session()
        self.cookie = f'{panel.COOKIE}={self.session_token}'
        self.server = panel.build_server('127.0.0.1', 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.tmp.cleanup)

    def test_non_ascii_cookie_returns_http_error_not_crash(self):
        """Cookie non-ASCII tidak boleh mematikan koneksi tanpa respons (S6)."""
        panel.PASSWORD = 'rahasia'
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/', headers={'Cookie': 'music_session=caf\u00e9'})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertIn(res.status, (200, 303, 401, 403, 500))

    def test_oversized_body_is_rejected_413(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        payload = 'a' * 70000
        conn.request('POST', '/save', body=payload,
                     headers={'Content-Type': 'application/x-www-form-urlencoded',
                              'Host': f'127.0.0.1:{self.port}',
                              'Origin': f'http://127.0.0.1:{self.port}',
                              'Cookie': self.cookie})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 413)

    def test_oversized_body_does_not_execute_action(self):
        """413 harus membatalkan aksi; .env tidak boleh berubah (M1)."""
        valid_tok = 'MTAwMDAwMDAwMDAwMDAwMDAw.G12345.abcdefghijklmnopqrstuvwxyz0123456789'
        valid_g = '123456789012345678'
        panel.ConfigStore(self.env).write({'token': valid_tok, 'guild': valid_g})
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('POST', '/save', body='token=HIJACK&guild=1' + 'x' * 70000,
                     headers={'Content-Type': 'application/x-www-form-urlencoded',
                              'Host': f'127.0.0.1:{self.port}',
                              'Origin': f'http://127.0.0.1:{self.port}',
                              'Cookie': self.cookie})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 413)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], valid_tok)

    def test_login_outside_allowlisted_host_is_rejected(self):
        """POST /login juga harus melewati cek origin (S4)."""
        panel.PASSWORD = 'rahasia'
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('POST', '/login', body='password=rahasia',
                     headers={'Content-Type': 'application/x-www-form-urlencoded',
                              'Origin': 'http://evil.example'})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 403)

    def test_stop_allowed_without_token(self):
        """Operator harus tetap bisa mematikan bot walau token kosong (S12)."""
        panel.ConfigStore(self.env).write({'token': '', 'guild': ''})
        origin = f'http://127.0.0.1:{self.port}'
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        conn.request('POST', '/stop', body='',
                     headers={'Content-Type': 'application/x-www-form-urlencoded',
                              'Origin': origin,
                              'Cookie': self.cookie})
        res = conn.getresponse()
        body = res.read().decode('utf-8', 'replace')
        conn.close()
        self.assertNotEqual(res.status, 400)
        self.assertNotIn('Token Discord belum diisi', body)


class PasswordlessTests(unittest.TestCase):
    """PANEL_PASSWORD kosong: mode baca-saja, semua aksi modifikasi (POST) ditolak (403)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        panel.STORE = panel.ConfigStore(self.env)
        panel.PASSWORD = ''
        # M7: flash/sesi/token dari test sebelumnya tidak boleh bocor ke sini.
        panel._flash_msg = ''
        panel._sessions.clear()
        panel._form_tokens.clear()
        panel._log_cache.clear()
        self.server = panel.build_server('127.0.0.1', 0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.tmp.cleanup)

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        hdrs = dict(headers or {})
        if body is not None:
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
            if 'Origin' not in hdrs:
                hdrs['Origin'] = f'http://127.0.0.1:{self.port}'
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload

    def test_page_opens_without_login(self):
        status, body = self.req('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('Panel Bot Musik', body)
        self.assertIn('mode baca-saja', body)

    def test_api_status_opens_without_login(self):
        status, body = self.req('GET', '/api/status')
        self.assertEqual(status, 200)
        self.assertIn('token_set', body)

    def test_cross_site_post_still_rejected(self):
        status, _ = self.req('POST', '/save', 'token=a&guild=1',
                             headers={'Origin': 'http://evil.example'})
        self.assertEqual(status, 403)

    def test_same_origin_save_rejected_when_passwordless(self):
        status, body = self.req('POST', '/save', 'token=abc&guild=7')
        self.assertEqual(status, 403)
        self.assertIn('Akses modifikasi ditolak', body)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], '')

    def test_start_rejected_when_passwordless(self):
        status, body = self.req('POST', '/start', '')
        self.assertEqual(status, 403)
        self.assertIn('Akses modifikasi ditolak', body)

    def test_update_rejected_when_passwordless(self):
        status, body = self.req('POST', '/update', '')
        self.assertEqual(status, 403)
        self.assertIn('Akses modifikasi ditolak', body)

    def test_login_post_rejected_when_passwordless(self):
        status, _ = self.req('POST', '/login', 'password=apapun')
        self.assertEqual(status, 403)

    def test_login_page_redirects_home_when_passwordless(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/login')
        res = conn.getresponse()
        res.read()
        location = res.getheader('Location') or ''
        conn.close()
        self.assertEqual(res.status, 303)
        self.assertEqual(location, '/')


class CsrfAndNonceTests(unittest.TestCase):
    """Pengujian proteksi CSRF, nonce form, dan PRG (Post-Redirect-Get)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        self.cfg = panel.ConfigStore(self.env)
        panel.STORE = self.cfg
        panel.PASSWORD = 'rahasia-csrf'
        self.valid_token = 'MTAwMDAwMDAwMDAwMDAwMDAw.G12345.abcdefghijklmnopqrstuvwxyz0123456789'
        self.valid_guild = '123456789012345678'
        self.server = panel.build_server('127.0.0.1', 0)
        self.port = self.server.server_address[1]
        self.cookie = f'{panel.COOKIE}={panel._mint_session()}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.tmp.cleanup)

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        hdrs = dict(headers or {})
        if 'Cookie' not in hdrs:
            hdrs['Cookie'] = self.cookie
        if body is not None:
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload

    def test_post_redirect_get_no_resubmit_on_refresh(self):
        origin = f'http://127.0.0.1:{self.port}'
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}', headers={'Origin': origin})
        self.assertEqual(status, 303)
        status, body = self.req('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('Konfigurasi disimpan.', body)
        status, body = self.req('GET', '/')
        self.assertEqual(status, 200)
        self.assertNotIn('Konfigurasi disimpan.', body)

    def test_browser_form_without_origin_uses_page_nonce(self):
        status, page = self.req('GET', '/')
        self.assertEqual(status, 200)
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}&form_token={token}')
        self.assertEqual(status, 303)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], self.valid_token)

    def test_no_origin_start_with_page_nonce_reaches_validation(self):
        self.cfg.write({'token': '', 'guild': ''})
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        status, body = self.req('POST', '/start', f'form_token={match.group(1)}')
        self.assertEqual(status, 400)
        self.assertIn('Token Discord belum diisi', body)

    def test_no_origin_without_page_nonce_stays_rejected(self):
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}')
        self.assertEqual(status, 403)

    def test_origin_null_with_page_nonce_is_accepted(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}&form_token={token}',
                             headers={'Origin': 'null'})
        self.assertEqual(status, 303)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], self.valid_token)

    def test_origin_null_without_nonce_is_rejected(self):
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}',
                             headers={'Origin': 'null'})
        self.assertEqual(status, 403)

    def test_cross_site_fetch_site_with_page_nonce_is_rejected(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}&form_token={token}',
                             headers={'Sec-Fetch-Site': 'cross-site'})
        self.assertEqual(status, 403)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], '')

    def test_foreign_origin_rejected_even_with_nonce(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}&form_token={token}',
                             headers={'Origin': 'http://evil.example'})
        self.assertEqual(status, 403)


class ShutdownTests(unittest.TestCase):
    """SIGTERM harus menghentikan panel dengan cepat.

    Regresi: handler memanggil server.shutdown() dari thread yang sama dengan
    serve_forever(). BaseServer.shutdown() menunggu loop berhenti, tetapi loop
    tidak bisa lanjut karena kita masih di dalam handler -> deadlock. systemd
    menunggu TimeoutStopSec (90 dtk) lalu SIGKILL, sehingga setiap restart
    panel lambat dan service tercatat "Failed with result 'timeout'".
    """

    def _start_panel(self):
        port_sock = socket.socket()
        port_sock.bind(('127.0.0.1', 0))
        port = port_sock.getsockname()[1]
        port_sock.close()

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = dict(os.environ,
                   PANEL_HOST='127.0.0.1',
                   PANEL_PORT=str(port),
                   PANEL_PASSWORD='uji',
                   BOT_CONFIG=os.path.join(tmp.name, '.env'))
        root = os.path.dirname(os.path.abspath(panel.__file__))
        proc = subprocess.Popen(
            [sys.executable, os.path.join(root, 'panel.py')],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.3):
                    return proc
            except OSError:
                if proc.poll() is not None:
                    out = proc.stdout.read() if proc.stdout else ''
                    self.fail(f'panel keluar sebelum siap: rc={proc.returncode}\n{out}')
                time.sleep(0.05)
        self.fail('panel tidak pernah membuka port')

    def test_sigterm_shuts_down_quickly(self):
        proc = self._start_panel()
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            self.fail('SIGTERM tidak menghentikan panel dalam 15 dtk (deadlock)')
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 5.0,
                        f'panel butuh {elapsed:.1f} dtk untuk berhenti (systemd '
                        'akan timeout 90 dtk lalu SIGKILL)')
        self.assertEqual(proc.returncode, 0,
                         f'kode keluar tidak bersih: {proc.returncode}')


class NoRealSystemdTests(unittest.TestCase):
    """Suite tidak boleh menyentuh systemd sungguhan.

    Regresi: POST /start|/restart|/stop dari unit test benar-benar menjalankan
    `systemctl <action> discord-music.service`. Menjalankan suite di server
    produksi mematikan bot yang sedang melayani pengguna (terbukti di journal:
    bot mati dua kali saat suite dijalankan).
    """

    def test_suite_installs_service_runner_hook(self):
        self.assertIsNotNone(
            panel.SERVICE_RUNNER,
            'panel.SERVICE_RUNNER belum dipasang: suite akan memanggil '
            'systemctl sungguhan dan mematikan bot produksi')
        self.assertTrue(callable(panel.SERVICE_RUNNER))

    def test_suite_installs_update_runner_hook(self):
        """UPDATE_RUNNER juga wajib ada: tanpa itu /update memasang paket
        sungguhan lewat update.sh dan me-restart bot."""
        self.assertIsNotNone(
            panel.UPDATE_RUNNER,
            'panel.UPDATE_RUNNER belum dipasang: suite akan menjalankan '
            'update.sh sungguhan (pip install + systemctl restart)')
        self.assertTrue(callable(panel.UPDATE_RUNNER))

    def test_service_runner_prevents_real_subprocess(self):
        """_service() harus memakai hook, bukan subprocess.run."""
        calls = []
        original = panel.SERVICE_RUNNER
        panel.SERVICE_RUNNER = lambda action: (calls.append(action), (True, ''))[1]
        self.addCleanup(setattr, panel, 'SERVICE_RUNNER', original)

        with unittest.mock.patch('panel.subprocess.run') as mock_run:
            mock_run.side_effect = AssertionError('systemctl sungguhan dipanggil!')
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            env = os.path.join(tmp.name, '.env')
            panel.STORE = panel.ConfigStore(env)
            panel.ConfigStore(env).write({'token': 'tok', 'guild': '1'})
            panel.PASSWORD = 'no-real-test'
            cookie = f'{panel.COOKIE}={panel._mint_session()}'
            saved_hosts = set(panel.ALLOWED_HOSTS)
            self.addCleanup(setattr, panel, 'ALLOWED_HOSTS', saved_hosts)

            server = panel.build_server('127.0.0.1', 0)
            port = server.server_address[1]
            panel.ALLOWED_HOSTS = {f'127.0.0.1:{port}'}
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.shutdown)
            self.addCleanup(server.server_close)

            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            conn.request('POST', '/stop', body='',
                         headers={'Content-Type': 'application/x-www-form-urlencoded',
                                  'Origin': f'http://127.0.0.1:{port}',
                                  'Cookie': cookie})
            res = conn.getresponse()
            res.read()
            conn.close()
        self.assertEqual(calls, ['stop'], 'hook SERVICE_RUNNER tidak dipakai')
        self.assertEqual(res.status, 303)


class SecurityAuditValidationTests(unittest.TestCase):
    """Unit test untuk temuan audit t_824f34ce:
    1. DoS large POST body (>64KB -> 413, socket drain bersih).
    2. Validasi Guild ID (regex ^\d{17,20}$, batas 64-bit int, proteksi DoS digit integer).
    3. Validasi Token Discord (regex format, cegah string rusak tersimpan).
    4. Host header check (parsing port secara benar, tolak 127.0.0.1:evil.com).
    5. Empty PANEL_PASSWORD (tolak seluruh aksi modifikasi POST dengan 403).
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        self.cfg = panel.ConfigStore(self.env)
        panel.STORE = self.cfg
        panel.PASSWORD = 'audit-pass'
        self.server = panel.build_server('127.0.0.1', 0)
        self.port = self.server.server_address[1]
        self.session_token = panel._mint_session()
        self.cookie = f'{panel.COOKIE}={self.session_token}'
        self.valid_token = 'MTAwMDAwMDAwMDAwMDAwMDAw.G12345.abcdefghijklmnopqrstuvwxyz0123456789'
        self.valid_guild = '123456789012345678'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.tmp.cleanup)

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        hdrs = dict(headers or {})
        if 'Cookie' not in hdrs:
            hdrs['Cookie'] = self.cookie
        if body is not None:
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
            if 'Origin' not in hdrs:
                hdrs['Origin'] = f'http://127.0.0.1:{self.port}'
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload

    # 1. DoS large POST body
    def test_body_over_64kb_rejected_with_413(self):
        payload = 'a' * 65537
        status, _ = self.req('POST', '/save', body=payload)
        self.assertEqual(status, 413)

    def test_body_under_64kb_not_rejected_with_413(self):
        payload = f'token={self.valid_token}&guild={self.valid_guild}'
        status, _ = self.req('POST', '/save', body=payload)
        self.assertEqual(status, 303)

    # 2. Validasi Guild ID
    def test_guild_id_rejects_non_numeric(self):
        status, body = self.req('POST', '/save', f'token={self.valid_token}&guild=notanumber')
        self.assertEqual(status, 400)
        self.assertIn('Guild ID harus berupa 17-20 digit angka', body)

    def test_guild_id_rejects_under_17_digits(self):
        status, body = self.req('POST', '/save', f'token={self.valid_token}&guild=1234567890123456')
        self.assertEqual(status, 400)
        self.assertIn('Guild ID harus berupa 17-20 digit angka', body)

    def test_guild_id_rejects_over_20_digits(self):
        status, body = self.req('POST', '/save', f'token={self.valid_token}&guild=123456789012345678901')
        self.assertEqual(status, 400)
        self.assertIn('Guild ID harus berupa 17-20 digit angka', body)

    def test_guild_id_cve_2020_10735_large_digits_blocked_by_regex(self):
        huge_guild = '9' * 4500
        status, body = self.req('POST', '/save', f'token={self.valid_token}&guild={huge_guild}')
        self.assertEqual(status, 400)
        self.assertIn('Guild ID harus berupa 17-20 digit angka', body)

    def test_guild_id_rejects_out_of_64bit_range(self):
        huge_snowflake = '99999999999999999999'
        status, body = self.req('POST', '/save', f'token={self.valid_token}&guild={huge_snowflake}')
        self.assertEqual(status, 400)
        self.assertIn('Guild ID di luar batas integer', body)

    def test_guild_id_valid_snowflakes_accepted(self):
        for snowflake in ('12345678901234567', '123456789012345678', '18446744073709551615'):
            status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild={snowflake}')
            self.assertEqual(status, 303)
            self.assertEqual(self.cfg.read()['guild'], snowflake)

    def test_guild_id_empty_allowed(self):
        status, _ = self.req('POST', '/save', f'token={self.valid_token}&guild=')
        self.assertEqual(status, 303)
        self.assertEqual(self.cfg.read()['guild'], '')

    # 3. Validasi Token Discord
    def test_discord_token_rejects_arbitrary_string(self):
        status, body = self.req('POST', '/save', f'token=not_a_discord_token&guild={self.valid_guild}')
        self.assertEqual(status, 400)
        self.assertIn('Format Token Discord tidak valid', body)

    def test_discord_token_rejects_missing_dots(self):
        status, body = self.req('POST', '/save', f'token=MTAwMDAwMDAwMDAwMDAwMDAwG12345abcdefghijklmnopqrstuvwxyz0123456789&guild={self.valid_guild}')
        self.assertEqual(status, 400)
        self.assertIn('Format Token Discord tidak valid', body)

    def test_discord_token_rejects_invalid_characters(self):
        bad_token = 'MTAwMDAwMDAwMDAwMDAwMDAw.G12345.abc!@#$%^&*()_+'
        status, body = self.req('POST', '/save', f'token={bad_token}&guild={self.valid_guild}')
        self.assertEqual(status, 400)
        self.assertIn('Format Token Discord tidak valid', body)

    def test_discord_token_preserves_current_when_empty_in_form(self):
        self.cfg.write({'token': self.valid_token, 'guild': self.valid_guild})
        new_guild = '987654321098765432'
        status, _ = self.req('POST', '/save', f'token=&guild={new_guild}')
        self.assertEqual(status, 303)
        saved = self.cfg.read()
        self.assertEqual(saved['token'], self.valid_token)
        self.assertEqual(saved['guild'], new_guild)

    # 4. Host header check
    def test_host_header_rejects_malformed_port(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/', headers={'Host': '127.0.0.1:evil.com'})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 403)

    def test_host_header_rejects_port_out_of_range(self):
        for bad_port in ('0', '70000', 'abc'):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
            conn.request('GET', '/', headers={'Host': f'127.0.0.1:{bad_port}'})
            res = conn.getresponse()
            res.read()
            conn.close()
            self.assertEqual(res.status, 403)

    def test_host_header_rejects_multiple_colons(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/', headers={'Host': '127.0.0.1:9130:extra'})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 403)

    # 5. Empty PANEL_PASSWORD privilege escalation prevention
    def test_empty_password_blocks_modifications(self):
        panel.PASSWORD = ''
        try:
            origin = f'http://127.0.0.1:{self.port}'
            endpoints = [
                ('POST', '/save', f'token={self.valid_token}&guild={self.valid_guild}'),
                ('POST', '/start', ''),
                ('POST', '/restart', ''),
                ('POST', '/stop', ''),
                ('POST', '/update', ''),
            ]
            for method, endpoint, body in endpoints:
                status, resp = self.req(method, endpoint, body=body, headers={'Origin': origin})
                self.assertEqual(status, 403, f'{method} {endpoint} harus ditolak 403 saat PASSWORD kosong')
                self.assertIn('Akses modifikasi ditolak', resp)
        finally:
            panel.PASSWORD = 'audit-pass'


if __name__ == '__main__':
    unittest.main()


class PanelBugReportFixesTests(unittest.TestCase):
    """Regression untuk temuan laporan bug: M1, M3, M6, L4."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        self.cfg = panel.ConfigStore(self.env)
        panel.STORE = self.cfg
        panel.PASSWORD = 'rahasia-fix'
        panel._form_tokens.clear()
        panel._log_cache.clear()
        panel._sessions.clear()
        panel._flash_msg = ''
        self.valid_token = 'MTAwMDAwMDAwMDAwMDAwMDAw.G12345.abcdefghijklmnopqrstuvwxyz0123456789'
        self.valid_guild = '123456789012345678'
        self.server = panel.build_server('127.0.0.1', 0)
        self.port = self.server.server_address[1]
        self.cookie = f'{panel.COOKIE}={panel._mint_session()}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(panel._log_cache.clear)

    def req(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        hdrs = dict(headers or {})
        if 'Cookie' not in hdrs:
            hdrs['Cookie'] = self.cookie
        if body is not None:
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload

    def _form_token(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        self.assertIsNotNone(match, 'form_token tidak muncul di panel')
        return match.group(1)

    # --- M6: ConfigStore.read membuang kutip ---
    def test_read_strips_matching_quotes(self):
        with open(self.env, 'w', encoding='utf-8') as fh:
            fh.write('DISCORD_TOKEN="abc.def.ghi"\nDISCORD_GUILD_ID=\'123\'\n')
        data = panel.ConfigStore(self.env).read()
        self.assertEqual(data['token'], 'abc.def.ghi')
        self.assertEqual(data['guild'], '123')

    def test_read_keeps_unquoted_and_unbalanced(self):
        with open(self.env, 'w', encoding='utf-8') as fh:
            fh.write('DISCORD_TOKEN=plain.token\nDISCORD_GUILD_ID="123\n')
        data = panel.ConfigStore(self.env).read()
        self.assertEqual(data['token'], 'plain.token')
        self.assertEqual(data['guild'], '"123', 'kutip tak berpasangan tidak dibuang')

    # --- M3: cache log ---
    def test_read_bot_logs_cached_uses_cache(self):
        panel._log_cache['35'] = (time.monotonic(), 'SENTINEL')
        with unittest.mock.patch('panel.read_bot_logs', side_effect=AssertionError('dipanggil')):
            self.assertEqual(panel.read_bot_logs_cached(35), 'SENTINEL')

    def test_read_bot_logs_cached_refreshes_when_stale(self):
        panel._log_cache['35'] = (time.monotonic() - panel.LOG_CACHE_TTL - 1, 'OLD')
        with unittest.mock.patch('panel.read_bot_logs', return_value='NEW') as m:
            self.assertEqual(panel.read_bot_logs_cached(35), 'NEW')
            m.assert_called_once()

    def test_read_bot_logs_cached_fresh_bypasses_cache(self):
        panel._log_cache['35'] = (time.monotonic(), 'OLD')
        with unittest.mock.patch('panel.read_bot_logs', return_value='NEW'):
            self.assertEqual(panel.read_bot_logs_cached(35, fresh=True), 'NEW')

    # --- L4: form token sekali pakai ---
    def test_form_token_is_single_use(self):
        token = self._form_token()
        # Origin: null memaksa validasi lewat jalur nonce (step 3), bukan jalur
        # Origin-cocok (step 2) — jadi token benar-benar yang mengotorisasi.
        headers = {'Origin': 'null'}
        status, _ = self.req('POST', '/save',
                             f'token={self.valid_token}&guild={self.valid_guild}&form_token={token}',
                             headers=headers)
        self.assertEqual(status, 303)
        # Token yang sama dipakai ulang harus ditolak (sudah dikonsumsi).
        status2, _ = self.req('POST', '/save',
                              f'token={self.valid_token}&guild={self.valid_guild}&form_token={token}',
                              headers=headers)
        self.assertEqual(status2, 403)


class PanelListenerAwareUpdateTests(unittest.TestCase):
    """M1: jalur fallback pembaruan tidak boleh me-restart bot saat ada pendengar."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_file = os.path.join(self.tmp.name, 'state.json')
        os.environ['BOT_STATE_FILE'] = self.state_file
        self.addCleanup(os.environ.pop, 'BOT_STATE_FILE', None)

    def _write_state(self, listeners, age=0.0):
        with open(self.state_file, 'w', encoding='utf-8') as fh:
            json.dump({'total_listeners': listeners, 'updated_at': time.time() - age}, fh)

    def test_listeners_active_true_when_listeners_present(self):
        self._write_state(2)
        self.assertTrue(panel.listeners_active())

    def test_listeners_active_false_when_zero(self):
        self._write_state(0)
        self.assertFalse(panel.listeners_active())

    def test_listeners_active_false_when_state_stale(self):
        self._write_state(5, age=300)
        self.assertFalse(panel.listeners_active())

    def test_listeners_active_false_when_no_file(self):
        self.assertFalse(panel.listeners_active())

    def test_fallback_update_defers_restart_when_listeners_active(self):
        self._write_state(3)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            proc = unittest.mock.MagicMock()
            proc.returncode = 0
            proc.stdout = ''
            proc.stderr = ''
            return proc

        with unittest.mock.patch.object(panel, 'UPDATE_RUNNER', None), \
             unittest.mock.patch.object(panel, 'bot_state', return_value='active'), \
             unittest.mock.patch.object(panel, 'listeners_active', return_value=True), \
             unittest.mock.patch('panel.os.path.exists', return_value=False), \
             unittest.mock.patch('panel.os.access', return_value=False), \
             unittest.mock.patch('panel.subprocess.run', side_effect=fake_run):
            ok, out = panel._run_update_inner()

        restart_calls = [c for c in calls if 'restart' in c]
        self.assertEqual(restart_calls, [], 'bot di-restart padahal ada pendengar')
        self.assertIn('ditunda', out)
