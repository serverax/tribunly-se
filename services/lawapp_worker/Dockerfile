FROM ghcr.io/serverax/lawapp/backend:latest

WORKDIR /app

COPY backend /app/backend
COPY services /app/services

ENV PYTHONPATH=/app
ENV SERVICE_NAME=lawapp_worker

CMD ["python", "-m", "services.lawapp_worker.app"]
