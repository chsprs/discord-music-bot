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


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        self.cfg = panel.ConfigStore(self.env)
        panel.STORE = self.cfg
        panel.PASSWORD = 'rahasia-uji'
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
        status, body, _ = self.req('POST', '/save', 'token=abc123def&guild=999', cookie=cookie)
        self.assertEqual(status, 303)
        self.assertNotIn('abc123def', body)
        saved = self.cfg.read()
        self.assertEqual(saved['token'], 'abc123def')
        self.assertEqual(saved['guild'], '999')
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
        status, body, _ = self.req('POST', '/update', '', cookie=cookie)
        # PRG: POST redirect 303, pesan via flash di GET berikutnya.
        self.assertEqual(status, 303)
        status, body, _ = self.req('GET', '/', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn('Pembaruan yt-dlp berhasil dijalankan', body)
        self.assertIn('yt-dlp updated successfully', body)
        panel.UPDATE_RUNNER = None

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
        panel.PASSWORD = ''
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
        if body is not None:
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload

    def test_foreign_host_with_matching_origin_is_rejected(self):
        """DNS-rebinding: Host & Origin palsu yang konsisten tetap ditolak."""
        status, _ = self.req('POST', '/save', 'token=abc&guild=7',
                             headers={'Host': 'evil.example:9130',
                                      'Origin': 'http://evil.example:9130'})
        self.assertEqual(status, 403)
        self.assertEqual(panel.ConfigStore(panel.STORE.path).read()['token'], '')

    def test_allowed_host_passes_origin_check(self):
        status, _ = self.req('POST', '/save', 'token=abc&guild=7',
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
        conn.request('GET', '/', headers={'Host': f'127.0.0.1:{self.port}'})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 200)

    def test_loopback_host_variants_accepted(self):
        """IP loopback apa pun (127.0.0.0/8) tetap diterima."""
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('GET', '/', headers={'Host': '127.0.0.5:9130'})
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
        panel.PASSWORD = ''
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
        payload = 'a' * 9000
        conn.request('POST', '/save', body=payload,
                     headers={'Content-Type': 'application/x-www-form-urlencoded',
                              'Host': f'127.0.0.1:{self.port}',
                              'Origin': f'http://127.0.0.1:{self.port}'})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 413)

    def test_oversized_body_does_not_execute_action(self):
        """413 harus membatalkan aksi; .env tidak boleh berubah (M1)."""
        panel.ConfigStore(self.env).write({'token': 'original', 'guild': '9'})
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.request('POST', '/save', body='token=HIJACK&guild=1' + 'x' * 9000,
                     headers={'Content-Type': 'application/x-www-form-urlencoded',
                              'Host': f'127.0.0.1:{self.port}',
                              'Origin': f'http://127.0.0.1:{self.port}'})
        res = conn.getresponse()
        res.read()
        conn.close()
        self.assertEqual(res.status, 413)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], 'original')

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
                              'Origin': origin})
        res = conn.getresponse()
        body = res.read().decode('utf-8', 'replace')
        conn.close()
        self.assertNotEqual(res.status, 400)
        self.assertNotIn('Token Discord belum diisi', body)


class PasswordlessTests(unittest.TestCase):
    """PANEL_PASSWORD kosong = panel terbuka, tapi CSRF tetap berlaku."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = os.path.join(self.tmp.name, '.env')
        panel.STORE = panel.ConfigStore(self.env)
        panel.PASSWORD = ''
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
        conn.request(method, path, body=body, headers=hdrs)
        res = conn.getresponse()
        payload = res.read().decode('utf-8', 'replace')
        conn.close()
        return res.status, payload

    def test_page_opens_without_login(self):
        status, body = self.req('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('Panel Bot Musik', body)

    def test_api_status_opens_without_login(self):
        status, body = self.req('GET', '/api/status')
        self.assertEqual(status, 200)
        self.assertIn('token_set', body)

    def test_cross_site_post_still_rejected(self):
        status, _ = self.req('POST', '/save', 'token=a&guild=1',
                             headers={'Origin': 'http://evil.example'})
        self.assertEqual(status, 403)

    def test_same_origin_save_works_without_login(self):
        origin = f'http://127.0.0.1:{self.port}'
        status, _ = self.req('POST', '/save', 'token=abc&guild=7',
                             headers={'Origin': origin})
        self.assertEqual(status, 303)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], 'abc')

    def test_start_without_token_is_rejected(self):
        origin = f'http://127.0.0.1:{self.port}'
        status, _ = self.req('POST', '/start', '', headers={'Origin': origin})
        self.assertEqual(status, 400)

    def test_post_redirect_get_no_resubmit_on_refresh(self):
        # Klik tombol lalu GET ulang: tidak ada POST ulang, tidak ada 405/409.
        # Lalu refresh berkali-kali tetap GET 200 tanpa warning resubmit browser.
        origin = f'http://127.0.0.1:{self.port}'
        self.req('POST', '/save', 'token=abc&guild=7', headers={'Origin': origin})
        status, body = self.req('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('Konfigurasi disimpan.', body)
        # Flash sekali tampil: refresh berikutnya bersih, tanpa warning POST.
        status, body = self.req('GET', '/')
        self.assertEqual(status, 200)
        self.assertNotIn('Konfigurasi disimpan.', body)

    def test_passwordless_update_executes(self):
        origin = f'http://127.0.0.1:{self.port}'
        panel.UPDATE_RUNNER = lambda: (True, '[Mock] Update OK')
        status, body = self.req('POST', '/update', '', headers={'Origin': origin})
        # PRG: POST redirect 303, pesan via flash di GET berikutnya.
        self.assertEqual(status, 303)
        status, body = self.req('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn('Pembaruan yt-dlp berhasil dijalankan', body)
        self.assertIn('[Mock] Update OK', body)
        panel.UPDATE_RUNNER = None

    def test_browser_form_without_origin_uses_page_nonce(self):
        status, page = self.req('GET', '/')
        self.assertEqual(status, 200)
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token=abc&guild=7&form_token={token}')
        self.assertEqual(status, 303)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], 'abc')

    def test_no_origin_start_with_page_nonce_reaches_validation(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        status, body = self.req('POST', '/start', f'form_token={match.group(1)}')
        self.assertEqual(status, 400)
        self.assertIn('Token Discord belum diisi', body)

    def test_no_origin_without_page_nonce_stays_rejected(self):
        status, _ = self.req('POST', '/save', 'token=abc&guild=7')
        self.assertEqual(status, 403)

    def test_origin_null_with_page_nonce_is_accepted(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token=abc&guild=7&form_token={token}',
                             headers={'Origin': 'null'})
        self.assertEqual(status, 303)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], 'abc')

    def test_origin_null_without_nonce_is_rejected(self):
        status, _ = self.req('POST', '/save', 'token=abc&guild=7',
                             headers={'Origin': 'null'})
        self.assertEqual(status, 403)

    def test_cross_site_fetch_site_with_page_nonce_is_rejected(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token=abc&guild=7&form_token={token}',
                             headers={'Sec-Fetch-Site': 'cross-site'})
        # Sec-Fetch-Site: cross-site ditolak tanpa syarat; nonce bukan pengganti
        # sinyal eksplisit dari browser.
        self.assertEqual(status, 403)
        self.assertEqual(panel.ConfigStore(self.env).read()['token'], '')

    def test_foreign_origin_rejected_even_with_nonce(self):
        _, page = self.req('GET', '/')
        match = re.search(r'name="form_token" value="([^"]+)"', page)
        if match is None:
            self.fail('Form token tidak muncul di panel')
        token = match.group(1)
        status, _ = self.req('POST', '/save', f'token=abc&guild=7&form_token={token}',
                             headers={'Origin': 'http://evil.example'})
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


if __name__ == '__main__':
    unittest.main()
