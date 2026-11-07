#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import os, secrets
try:
    fd = os.open('.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('Using existing .env')
else:
    with os.fdopen(fd, 'w') as file:
        file.write('GRAFANA_ADMIN_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
    print('Created .env with a random local Grafana admin password')
PY
