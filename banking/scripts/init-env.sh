#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -e .env ]; then echo '.env already exists; refusing to replace keys.' >&2; exit 1; fi
umask 077
set -o noclobber
{
  printf 'DB_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'RRN_ENCRYPTION_KEY=%s\n' "$(openssl rand -base64 32 | tr '+/' '-_')"
  printf 'JWT_SECRET=%s\n' "$(openssl rand -hex 32)"
  printf 'LAB_MODE=fixed\nWEB_PORT=8081\n'
} > .env
echo 'Created .env. Keep these keys when reusing the DB.'
