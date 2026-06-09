FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY graph_update_worker.py .

# Ingestion worker is not a service, it's a batch worker
# Can be invoked as: docker run ... python graph_update_worker.py demo

CMD ["python", "graph_update_worker.py"]
