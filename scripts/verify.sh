#!/usr/bin/env bash
# One command verification: backend lint, types, tests, evaluation, migrations; frontend typecheck, tests, build.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

echo "== backend =="
cd backend
$PY -m ruff check app tests evaluation
$PY -m mypy app
$PY -m pytest -q
$PY evaluation/run_eval.py --min-safety-recall 1.0 > /dev/null && echo "evaluation gate passed"
cd ..

echo "== frontend =="
cd frontend
npm run typecheck
npm test
npm run build
cd ..

echo "== secret scan =="
./scripts/secret_scan.sh
echo "ALL CHECKS PASSED"
