#!/bin/sh
set -eu

PORT="${PORT:-8000}"
if [ "$#" -eq 0 ]; then
  exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers 1 \
    --threads 4
fi

exec "$@"
