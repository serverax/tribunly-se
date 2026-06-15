FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# System deps — libpq for psycopg2-binary, libxml2/libxslt for lxml,
# curl for compose healthcheck, build-essential for any src-build fallbacks
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential curl libpq-dev postgresql-client libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Install all runtime deps declared in pyproject.toml.
# Explicit list (not pip install -e .) so the image stays reproducible
# without requiring hatchling to resolve package directories at build time.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
       "httpx[http2]>=0.27" \
       "requests>=2.32" \
       "tenacity>=8.3" \
       "lxml>=5.2" \
       "psycopg2-binary>=2.9" \
       "pgvector>=0.3" \
       "openai>=1.35" \
       "tiktoken>=0.7" \
       "fastapi>=0.111" \
       "uvicorn[standard]>=0.30" \
       "python-dotenv>=1.0" \
       "pydantic>=2.7" \
       "pydantic-settings>=2.3" \
       "rich>=13.7" \
       "anthropic>=0.28" \
       "aiofiles>=23.2" \
       "python-multipart>=0.0.9" \
       "cryptography>=42.0" \
       "PyJWT>=2.8" \
       "boto3>=1.34" \
       "fastembed>=0.3.0" \
       "slowapi>=0.1.9" \
       "redis[hiredis]>=5.0" \
       "stripe>=10.0" \
       "pypdf>=4.0" \
       "python-docx>=1.1" \
       "opentelemetry-sdk>=1.27" \
       "opentelemetry-instrumentation-fastapi>=0.48b0" \
       "opentelemetry-exporter-otlp-proto-http>=1.27" \
       "litellm>=1.44" \
       "PyYAML>=6.0" \
       "networkx>=3.4" \
       "pytest>=7.4" \
       "pytest-asyncio>=0.23" \
       "pytest-cov>=4.1" \
       "httpx>=0.27"

# Pre-download the fastembed ONNX model so it's baked into the image.
# This avoids runtime download failures in airgapped/slow environments.
ENV FASTEMBED_CACHE_PATH=/app/fastembed_cache
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')" \
    && echo "fastembed model pre-downloaded OK"

# Create non-root user for K8s restricted PodSecurity
RUN groupadd -g 10001 lawapp && useradd -u 10001 -g 10001 -m lawapp \
    && chown -R lawapp:lawapp /app
USER 10001

COPY --chown=lawapp:lawapp backend ./backend
COPY --chown=lawapp:lawapp services ./services
COPY --chown=lawapp:lawapp shared ./shared
COPY --chown=lawapp:lawapp ingestion ./ingestion
COPY --chown=lawapp:lawapp db ./db
COPY --chown=lawapp:lawapp client ./client
COPY --chown=lawapp:lawapp scripts ./scripts
COPY --chown=lawapp:lawapp docs ./docs
COPY --chown=lawapp:lawapp docker-compose.yml ./docker-compose.yml
COPY --chown=lawapp:lawapp tests ./tests

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations then start backend
CMD ["bash", "/app/scripts/backend-entrypoint.sh"]
