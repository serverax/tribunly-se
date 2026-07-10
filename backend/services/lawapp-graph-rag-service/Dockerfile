FROM python:3.12-slim

WORKDIR /app

# Install system and Python dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY backend/services/lawapp-graph-rag-service/requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy shared modules plus service entrypoint from the repo-root build context.
COPY backend/ /app/backend/
COPY ingestion/ /app/ingestion/
COPY backend/services/lawapp-graph-rag-service/main.py /app/main.py

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8018

HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8018/health', timeout=2)" || exit 1

USER 65532:65532

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8018"]
