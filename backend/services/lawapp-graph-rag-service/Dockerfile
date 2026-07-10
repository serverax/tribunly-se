FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY . .

# Expose port
EXPOSE 8018

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=6 --start-period=5s \
  CMD python -c "import requests; requests.get('http://localhost:8018/health', timeout=2)" || exit 1

# Run service
USER 65532:65532

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8018"]
