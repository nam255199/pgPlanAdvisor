#!/bin/sh
set -eu

mkdir -p /var/log/pgplanadvisor/frontend

echo "[$(date -Iseconds)] Starting pgPlanAdvisor frontend" >> /var/log/pgplanadvisor/frontend/frontend.log

exec npm run dev 2>&1 | tee -a /var/log/pgplanadvisor/frontend/frontend.log
