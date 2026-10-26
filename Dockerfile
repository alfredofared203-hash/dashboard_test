FROM node:22-bookworm-slim AS frontend-build

WORKDIR /workspace/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run typecheck && npm run build

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false \
    HOME=/home/dcc \
    PORT=8000

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /workspace/frontend/dist/ ./frontend/dist/
COPY docker-entrypoint.sh ./docker-entrypoint.sh

WORKDIR /app/backend
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput

RUN groupadd --gid 10001 dcc \
    && useradd --uid 10001 --gid 10001 --create-home --home-dir /home/dcc --shell /usr/sbin/nologin dcc \
    && install -d --mode 0750 --owner 10001 --group 10001 /home/dcc/.gunicorn

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import json, urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/api/health/', timeout=5).read();" || exit 1
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
USER 10001:10001
