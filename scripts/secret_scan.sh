#!/usr/bin/env bash
# Looks for likely credentials. Reports every hit for human review, and fails on high confidence patterns.
set -u
cd "$(dirname "$0")/.."
EXCLUDE=(--exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir=.mypy_cache --exclude-dir=.ruff_cache --exclude-dir=.pytest_cache --exclude=package-lock.json --exclude=secret_scan.sh --exclude=*.zip)

echo "== high confidence patterns (must be empty) =="
HIGH=$(grep -rInE "(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|xox[abp]-[A-Za-z0-9-]{10,})" "${EXCLUDE[@]}" . || true)
echo "${HIGH:-none}"

echo; echo "== keyword review (expected: config names, tests, docs) =="
grep -rIlE "API_KEY|SECRET|PASSWORD|TOKEN|PRIVATE_KEY|DATABASE_PASSWORD" "${EXCLUDE[@]}" . | sort

echo; echo "== tracked env files (must be only .env.example) =="
find . -name ".env*" -not -path "*/node_modules/*" -not -name ".env.example" | grep . || echo "none"

[ -z "$HIGH" ]
