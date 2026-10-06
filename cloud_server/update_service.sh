#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
PROJECT_NAME="${1:-}"

cd "$REPO_ROOT"
git pull --ff-only

cd "$SCRIPT_DIR"

if [ ! -f ".env" ]; then
  echo "Missing cloud_server/.env. Create it from cloud_server/.env.example first." >&2
  exit 1
fi

if [ -z "$PROJECT_NAME" ]; then
  PROJECT_NAME="$(awk -F= '/^COMPOSE_PROJECT_NAME=/ {print $2; exit}' .env | tr -d '\r' || true)"
fi

if [ -z "$PROJECT_NAME" ]; then
  PROJECT_NAME="sarapp-cloud-server-db"
fi

docker compose -p "$PROJECT_NAME" --env-file .env up -d --build --remove-orphans
docker compose -p "$PROJECT_NAME" --env-file .env ps
