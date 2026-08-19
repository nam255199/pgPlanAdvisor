#!/bin/sh
set -eu

mkdir -p logs/backend logs/frontend

case "${1:-all}" in
  backend)
    sudo docker compose logs -f backend | tee -a logs/backend/docker-compose-backend.log
    ;;
  frontend)
    sudo docker compose logs -f frontend | tee -a logs/frontend/docker-compose-frontend.log
    ;;
  all)
    sudo docker compose logs -f | tee -a logs/docker-compose-all.log
    ;;
  *)
    echo "Usage: ./scripts/logs.sh [all|backend|frontend]"
    exit 1
    ;;
esac
