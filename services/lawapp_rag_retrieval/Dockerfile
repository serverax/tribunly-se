FROM ghcr.io/serverax/lawapp/backend:latest

WORKDIR /app

COPY backend /app/backend
COPY services /app/services

ENV PYTHONPATH=/app
ENV SERVICE_NAME=lawapp_rag_retrieval

EXPOSE 8080

CMD ["uvicorn", "services.lawapp_rag_retrieval.app:app", "--host", "0.0.0.0", "--port", "8080"]
