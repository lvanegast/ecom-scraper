#!/bin/sh
set -e

DB_INIT_OUTPUT="$(python init_db.py)"
echo "$DB_INIT_OUTPUT"

DB_INIT_ACTION="$(echo "$DB_INIT_OUTPUT" | awk -F= '/DB_INIT_ACTION=/{print $2}' | tail -n 1)"

if [ "$DB_INIT_ACTION" = "bootstrap" ]; then
  alembic stamp head
elif [ "$DB_INIT_ACTION" = "stamp" ]; then
  alembic stamp head
else
  alembic upgrade head
fi

exec uvicorn main:app --host 0.0.0.0 --port 8000
