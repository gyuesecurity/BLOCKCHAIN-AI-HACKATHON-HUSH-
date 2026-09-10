FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HUSH_FRONTEND_DIR=/app/frontend

WORKDIR /app
COPY . .
# llm  -> real Gemini structuring   chain -> EVM testnet anchoring
# postgres -> psycopg driver for a managed database (Railway injects DATABASE_URL)
RUN pip install --no-cache-dir '.[llm,chain,postgres]'

EXPOSE 8000
# Honour $PORT when the platform injects one (Railway, Render, Fly, Cloud Run).
CMD ["sh", "-c", "uvicorn hush.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
