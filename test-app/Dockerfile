FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY worker/ ./worker/
COPY VERSION ./VERSION

RUN useradd --system --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app

USER 10001:10001
EXPOSE 8080 9101

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
