#!/bin/sh
set -eu

mkdir -p /var/log/pgplanadvisor/backend

echo "[$(date -Iseconds)] Starting pgPlanAdvisor backend" >> /var/log/pgplanadvisor/backend/backend.log

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --access-log \
  --log-level info \
  2>&1 | tee -a /var/log/pgplanadvisor/backend/backend.log
