import http.client
import json
import os
import stat
import tempfile
import threading
import unittest

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

    def test_start_requires_authentication(self):
        status, _, _ = self.req('POST', '/start')
        self.assertIn(status, (401, 403))

    def test_incomplete_config_cannot_start(self):
        self.cfg.write({'token': '', 'guild': ''})
        cookie = self.login()
        status, body, _ = self.req('POST', '/start', '', cookie=cookie)
        self.assertEqual(status, 400)
        self.assertNotIn('Traceback', body)


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


if __name__ == '__main__':
    unittest.main()
