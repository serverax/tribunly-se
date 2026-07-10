FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8009

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8009/health')" || exit 1

USER 65532:65532

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8009"]
