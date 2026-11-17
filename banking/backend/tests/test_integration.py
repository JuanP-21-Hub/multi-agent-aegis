"""Real PostgreSQL integration tests. Refuse to run against the normal database."""
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from app import main as m
from app import extensions as ext


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('DB_NAME') != 'banklab_test':
            raise RuntimeError('Use isolated compose.test.yaml / banklab_test only')
        cls.client = TestClient(m.app)
        cls.password = 'Integration!Pass1234'
        cls.pin = '6789'
        cls.employee = 'staff_' + uuid.uuid4().hex[:12]
        with m.get_db() as conn, conn.cursor() as cur:
            cur.execute('''INSERT INTO staff_users (employee_id,display_name,password_hash)
                           VALUES (%s,'검증직원',%s) RETURNING id''',
                        (cls.employee, m.password_hasher.hash(cls.password)))
            cls.staff_id = cur.fetchone()[0]
        r = cls.client.post('/api/auth/staff/login', json={'employee_id': cls.employee, 'password': cls.password})
        assert r.status_code == 200
        cls.staff_headers = {'Authorization': 'Bearer ' + r.json()['access_token']}

    def setUp(self):
        self.old_mode = ext.LAB_MODE
        ext.LAB_MODE = 'fixed'

    def tearDown(self):
        ext.LAB_MODE = self.old_mode

    def customer(self):
        login = 'user_' + uuid.uuid4().hex[:12]
        body = dict(login_id=login, password=self.password, full_name='테스트고객', rrn='TEST-RRN-123456')
        r = self.client.post('/api/customers/signup', json=body)
        self.assertEqual(r.status_code, 201, r.text)
        cid = r.json()['customer_id']
        r = self.client.post('/api/auth/customer/login', json={'login_id': login, 'password': self.password})
        self.assertEqual(r.status_code, 200)
        return cid, login, {'Authorization': 'Bearer ' + r.json()['access_token']}

    def test_signup_database_encryption_and_me(self):
        cid, login, h = self.customer()
        with m.get_db() as conn, conn.cursor() as cur:
            cur.execute('SELECT password_hash, rrn_encrypted, rrn_last4 FROM customers WHERE id=%s', (cid,))
            hashed, encrypted, last4 = cur.fetchone()
        self.assertTrue(m.password_hasher.verify(hashed, self.password))
        self.assertNotEqual(bytes(encrypted), b'TEST-RRN-123456')
        self.assertEqual(m.rrn_cipher.decrypt(bytes(encrypted)), b'TEST-RRN-123456')
        self.assertEqual(last4, '3456')
        r = self.client.get('/api/customers/me', headers=h)
        self.assertEqual(r.json(), {'customer_id': cid, 'login_id': login, 'full_name': '테스트고객'})

    def test_duplicate_and_bad_password(self):
        _, login, _ = self.customer()
        self.assertEqual(self.client.post('/api/customers/signup', json=dict(login_id=login, password=self.password,
                         full_name='중복', rrn='TEST-RRN-111111')).status_code, 409)
        self.assertEqual(self.client.post('/api/auth/customer/login', json=dict(login_id=login, password='wrong')).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/staff/login', json=dict(employee_id=self.employee, password='wrong')).status_code, 401)

    def test_account_creation_list_pin_and_ownership(self):
        cid, _, h = self.customer()
        r = self.client.post('/api/accounts', headers=h, json={'account_pin': self.pin})
        self.assertEqual(r.status_code, 201)
        a = r.json()
        self.assertEqual((a['balance'], a['status']), (0, 'ACTIVE'))
        self.assertRegex(a['account_number'], r'^100-\d{3}-\d{6}$')
        self.assertEqual(self.client.get('/api/accounts/me', headers=h).json(), [a])
        url = f"/api/accounts/{a['account_id']}/verify-pin"
        self.assertEqual(self.client.post(url, headers=h, json={'account_pin': self.pin}).status_code, 200)
        self.assertEqual(self.client.post(url, headers=h, json={'account_pin': '0000'}).status_code, 403)
        _, _, other = self.customer()
        for mode in ('fixed', 'vulnerable'):
            ext.LAB_MODE = mode
            self.assertEqual(self.client.post(url, headers=other, json={'account_pin': self.pin}).status_code, 403)
        with m.get_db() as conn, conn.cursor() as cur:
            cur.execute('SELECT account_pin_hash FROM accounts WHERE id=%s', (a['account_id'],))
            self.assertTrue(m.password_hasher.verify(cur.fetchone()[0], self.pin))

    def test_guest_and_customer_staff_boundaries(self):
        _, _, h = self.customer()
        for url in ('/api/staff/me', '/api/staff/customers', '/api/staff/customers/1',
                    '/api/staff/customers/1/accounts', '/api/staff/users', '/api/staff/audit-logs', '/api/lab'):
            self.assertEqual(self.client.get(url).status_code, 401, url)
            self.assertEqual(self.client.get(url, headers=h).status_code, 403, url)
        self.assertEqual(self.client.get('/api/customers/me').status_code, 401)
        self.assertEqual(self.client.get('/api/accounts/me').status_code, 401)
        self.assertEqual(self.client.post('/api/accounts', json={'account_pin': self.pin}).status_code, 401)
        self.assertEqual(self.client.post('/api/staff/users', headers=h, json=dict(employee_id='forbidden',
                         display_name='금지', password=self.password)).status_code, 403)
        self.assertEqual(self.client.patch(f'/api/staff/users/{self.staff_id}', headers=h, json={'active': False}).status_code, 403)

    def test_staff_detail_accounts_and_pagination(self):
        cid, _, h = self.customer()
        a = self.client.post('/api/accounts', headers=h, json={'account_pin': self.pin}).json()
        self.assertEqual(self.client.get('/api/staff/me', headers=self.staff_headers).json()['staff_id'], self.staff_id)
        rows = self.client.get(f'/api/staff/customers?after_id={cid-1}&limit=1', headers=self.staff_headers).json()
        self.assertEqual(rows[0]['customer_id'], cid)
        detail = self.client.get(f'/api/staff/customers/{cid}', headers=self.staff_headers)
        self.assertEqual(detail.json()['rrn_last4'], '3456')
        self.assertNotIn('rrn_encrypted', detail.text)
        self.assertEqual(self.client.get(f'/api/staff/customers/{cid}/accounts', headers=self.staff_headers).json(), [a])

    def test_staff_create_disable_reactivate_revokes_old_token(self):
        employee = 'new_' + uuid.uuid4().hex[:12]
        r = self.client.post('/api/staff/users', headers=self.staff_headers,
                             json=dict(employee_id=employee, display_name='신규직원', password=self.password, role='ADMIN'))
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()['role'], 'STAFF')
        sid = r.json()['staff_id']
        credentials = dict(employee_id=employee, password=self.password)
        token = self.client.post('/api/auth/staff/login', json=credentials).json()['access_token']
        h = {'Authorization': 'Bearer ' + token}
        self.assertEqual(self.client.get('/api/staff/users', headers=h).status_code, 200)
        self.assertEqual(self.client.patch(f'/api/staff/users/{sid}', headers=self.staff_headers, json={'active': False}).status_code, 200)
        for url in ('/api/staff/me', '/api/staff/users', '/api/staff/customers', '/api/staff/audit-logs'):
            self.assertEqual(self.client.get(url, headers=h).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/staff/login', json=credentials).status_code, 401)
        self.client.patch(f'/api/staff/users/{sid}', headers=self.staff_headers, json={'active': True})
        self.assertEqual(self.client.get('/api/staff/users', headers=h).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/staff/login', json=credentials).status_code, 200)
        self.assertEqual(self.client.patch(f'/api/staff/users/{self.staff_id}', headers=self.staff_headers, json={'active': False}).status_code, 400)

    def test_expired_and_malformed_token(self):
        cid, _, _ = self.customer()
        token = jwt.encode(dict(sub=str(cid), role='CUSTOMER', iss='finlab', aud='finlab-client',
                                exp=datetime.now(timezone.utc)-timedelta(seconds=1)), os.environ['JWT_SECRET'], algorithm='HS256')
        for value in (token, 'malformed'):
            self.assertEqual(self.client.get('/api/customers/me', headers={'Authorization': 'Bearer '+value}).status_code, 401)

    def test_logout_revokes_token(self):
        _, _, h = self.customer()
        self.assertEqual(self.client.post('/api/auth/logout', headers=h).status_code, 200)
        self.assertEqual(self.client.get('/api/customers/me', headers=h).status_code, 401)

    def test_bola_mode_is_limited_to_customer_detail(self):
        cid, _, h = self.customer()
        other, _, _ = self.customer()
        self.assertEqual(self.client.get(f'/api/customers/{cid}', headers=h).status_code, 200)
        self.assertEqual(self.client.get(f'/api/customers/{other}', headers=h).status_code, 403)
        ext.LAB_MODE = 'vulnerable'
        r = self.client.get(f'/api/customers/{other}', headers=h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.json()), {'customer_id', 'login_id', 'full_name'})
        self.assertEqual(self.client.get(f'/api/customers/{other}').status_code, 401)
        self.assertEqual(self.client.get('/api/staff/customers', headers=h).status_code, 403)

    def test_validation_does_not_echo_secrets(self):
        bad = dict(login_id='bad', password='sensitive', full_name=' ', rrn='900101-1234567')
        r = self.client.post('/api/customers/signup', json=bad)
        self.assertEqual(r.status_code, 422)
        for value in ('sensitive', '900101-1234567', 'input', 'ctx'):
            self.assertNotIn(value, r.text)

    def test_audit_persistence_download_and_no_secret_leaks(self):
        cid, _, h = self.customer()
        r = self.client.get('/api/customers/me?password=not-for-logs', headers=h)
        self.assertEqual(r.headers['X-Audit-Persisted'], 'true')
        with m.get_db() as conn, conn.cursor() as cur:
            cur.execute('SELECT actor_id, http_status, request_path FROM audit_logs WHERE request_id=%s', (r.headers['X-Request-ID'],))
            self.assertEqual(cur.fetchone(), (cid, 200, '/api/customers/me'))
            cur.execute("SELECT row_to_json(a)::text FROM audit_logs a WHERE action='API_REQUEST' ORDER BY id DESC LIMIT 1000")
            logged = '\n'.join(row[0] for row in cur.fetchall())
        for secret in (self.password, 'TEST-RRN-123456', h['Authorization'], 'not-for-logs'):
            self.assertNotIn(secret, logged)
        r = self.client.get('/api/staff/audit-logs?format=jsonl', headers=self.staff_headers)
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r.headers['content-disposition'])
        self.assertTrue(all('http_status' in json.loads(line) for line in r.text.splitlines()))
        self.assertNotIn('details', r.text)
        self.assertEqual(self.client.get('/api/staff/audit-logs?format=jsonl', headers=h).status_code, 403)


if __name__ == '__main__':
    unittest.main()
