import json
import secrets
import sys
import urllib.request
import urllib.error

def call(path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request('http://127.0.0.1:8081/api'+path,
                                 data=json.dumps(body).encode() if body else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)

mode = sys.argv[1]
password = secrets.token_urlsafe(20)
first = 'bola_'+secrets.token_hex(5)
second = 'bola_'+secrets.token_hex(5)
for name in (first, second):
    status, result = call('/customers/signup', dict(login_id=name, password=password, full_name='접근검증', rrn='TEST-RRN-111111'))
    assert status == 201
target = result['customer_id']
status, result = call('/auth/customer/login', dict(login_id=first, password=password))
assert status == 200
token = result['access_token']
assert call(f'/customers/{target}', token=token)[0] == (403 if mode == 'fixed' else 200)
assert call(f'/customers/{target}')[0] == 401
assert call('/staff/customers', token=token)[0] == 403
print('PASS: server environment BOLA mode='+mode+', authentication and staff boundaries preserved')
