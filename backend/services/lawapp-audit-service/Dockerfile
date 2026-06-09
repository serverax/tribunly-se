FROM python:3.12-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=5s \
    CMD python -c "import requests; requests.get('http://localhost:8020/health', timeout=5)"

# Run service
CMD ["python", "main.py"]
