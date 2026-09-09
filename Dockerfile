FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HUSH_FRONTEND_DIR=/app/frontend

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "hush.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
