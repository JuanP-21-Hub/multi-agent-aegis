#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# A unique project/volume ensures no user data is touched. Keep volume after tests.
project="aegis-test-$(date +%s)-$$"
export DB_PASSWORD="$(openssl rand -hex 24)"
export RRN_ENCRYPTION_KEY="$(openssl rand -base64 32 | tr '+/' '-_')"
export JWT_SECRET="$(openssl rand -hex 32)"
export WEB_PORT=8081 LAB_MODE=fixed
dc() { docker compose --env-file /dev/null -p "$project" -f compose.yaml -f compose.test.yaml "$@"; }
trap 'dc stop >/dev/null 2>&1 || true' EXIT
node --test tests/api-client.test.cjs
dc up -d --wait database
dc exec -T database psql -U bank_admin -d banklab_test -v ON_ERROR_STOP=1 < tests/legacy-fixture.sql
dc run --rm migrate
dc run --rm migrate
dc exec -T database psql -U bank_admin -d banklab_test -v ON_ERROR_STOP=1 < tests/check-legacy.sql
dc up -d --build --wait
dc run --rm --no-deps backend sh -c 'pip install --no-cache-dir -r requirements-test.txt && python -m unittest discover -s tests -v'
python3 tests/smoke.py before
export SMOKE_STAFF_ID="browser_staff_$$"
export SMOKE_STAFF_PASSWORD="$(openssl rand -hex 24)"
dc exec -T -e SMOKE_STAFF_ID -e SMOKE_STAFF_PASSWORD backend python -m tests.bootstrap_browser
npm install --prefix tests/browser --ignore-scripts --no-audit --no-fund
node tests/browser/node_modules/playwright/cli.js install --with-deps chromium
node tests/browser/smoke.cjs
python3 tests/bola_http.py fixed
export LAB_MODE=vulnerable
dc up -d --force-recreate backend
dc up -d --force-recreate --wait web
python3 tests/bola_http.py vulnerable
export LAB_MODE=fixed
dc up -d --force-recreate backend
dc up -d --force-recreate --wait web
dc restart database backend web
dc up -d --wait
python3 tests/smoke.py after
echo "PASS: isolated Compose suite. Stopped test project: $project (volume retained)."
