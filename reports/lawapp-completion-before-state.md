# LawApp Completion Before State

## Git Status
```bash
 M .claude-flow/sessions/current.json
 M .github/workflows/lawapp-ci.yml
 M .github/workflows/lawapp-deploy-talos.yml
 M Dockerfile
 M backend/api/main.py
 M client/public/pages/saved_case.html
 M pyproject.toml
 M test-results/.last-run.json
 D test-results/lawapp-journey-assessment--5d186-for-short-service-QP-fails--chromium-retry1/error-context.md
 D test-results/lawapp-journey-assessment--5d186-for-short-service-QP-fails--chromium/error-context.md
 D test-results/lawapp-journey-intake-dead-28ae6--correct-values-for-WASM-JS-chromium-retry1/error-context.md
 D test-results/lawapp-journey-intake-dead-28ae6--correct-values-for-WASM-JS-chromium/error-context.md
 D test-results/lawapp-journey-rules-endpoint-returns-unfair-dismissal-rules-chromium-retry1/error-context.md
 D test-results/lawapp-journey-rules-endpoint-returns-unfair-dismissal-rules-chromium/error-context.md
 M tests/document_intelligence/test_document_intelligence.py
?? db/migrations/021_payment_events.sql
?? phase0_baseline.sh
?? reports/claude-lawapp-final-hostile-completion-verification.md
?? reports/gemini-lawapp-final-ultimate-fullstack-qa-security-audit-v3.md
?? reports/lawapp-completion-before-state.md
?? reports/lawapp-full-cicd-setup.md
?? scripts/lawapp-check-talos.sh
?? scripts/lawapp-push.sh
?? scripts/lawapp-setup-github-secrets.sh
?? scripts/lawapp-trigger-deploy.sh
?? scripts/security-regression.sh
e165295 lawapp: add CI/CD pipeline and Talos auto deployment
```

## Docker Clean Start
```bash
 Image lawapp-backend Building 
#1 [internal] load local bake definitions
#1 reading from stdin 480B 0.0s done
#1 DONE 0.0s

#2 [internal] load build definition from Dockerfile
#2 transferring dockerfile:
#2 transferring dockerfile: 2.50kB 0.9s done
#2 DONE 0.9s

#3 [internal] load metadata for docker.io/library/python:3.12-slim
#3 ...

#4 [auth] library/python:pull token for registry-1.docker.io
#4 DONE 0.0s

#3 [internal] load metadata for docker.io/library/python:3.12-slim
#3 DONE 2.0s

#5 [internal] load .dockerignore
#5 transferring context: 32B 0.0s
#5 transferring context: 156B 1.0s done
#5 DONE 1.0s

#6 [ 1/15] FROM docker.io/library/python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203
#6 resolve docker.io/library/python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203 0.3s done
#6 DONE 0.4s

#7 [ 2/15] WORKDIR /app
#7 CACHED

#8 [ 3/15] RUN apt-get update     && apt-get install -y --no-install-recommends        build-essential curl libpq-dev libxml2-dev libxslt1-dev     && rm -rf /var/lib/apt/lists/*
#8 CACHED

#9 [internal] load build context
#9 transferring context: 328.39kB 5.0s
#9 transferring context: 341.00kB 10.0s
#9 transferring context: 344.59kB 15.1s
#9 transferring context: 377.55kB 20.1s
#9 transferring context: 382.66kB 25.2s
#9 transferring context: 389.43kB 30.3s
#9 transferring context: 394.33kB 35.4s
#9 transferring context: 401.31kB 40.4s
#9 transferring context: 407.53kB 45.5s
#9 transferring context: 412.18kB 50.6s
#9 transferring context: 415.43kB 55.7s
#9 transferring context: 420.50kB 60.7s
#9 transferring context: 428.07kB 65.8s
#9 transferring context: 444.91kB 69.7s done
#9 DONE 69.7s

#10 [ 4/15] COPY pyproject.toml ./
#10 DONE 0.2s

#11 [ 5/15] RUN pip install --no-cache-dir --upgrade pip     && pip install --no-cache-dir        "httpx[http2]>=0.27"        "tenacity>=8.3"        "lxml>=5.2"        "psycopg2-binary>=2.9"        "pgvector>=0.3"        "openai>=1.35"        "tiktoken>=0.7"        "fastapi>=0.111"        "uvicorn[standard]>=0.30"        "python-dotenv>=1.0"        "pydantic>=2.7"        "pydantic-settings>=2.3"        "rich>=13.7"        "anthropic>=0.28"        "aiofiles>=23.2"        "python-multipart>=0.0.9"        "cryptography>=42.0"        "PyJWT>=2.8"        "boto3>=1.34"        "fastembed>=0.3.0"        "slowapi>=0.1.9"        "redis[hiredis]>=5.0"        "stripe>=10.0"        "pypdf>=4.0"        "python-docx>=1.1"
#11 11.01 Requirement already satisfied: pip in /usr/local/lib/python3.12/site-packages (25.0.1)
#11 11.49 Collecting pip
#11 11.73   Downloading pip-26.1.2-py3-none-any.whl.metadata (4.6 kB)
#11 11.79 Downloading pip-26.1.2-py3-none-any.whl (1.8 MB)
#11 13.07    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.8/1.8 MB 1.4 MB/s eta 0:00:00
#11 13.28 Installing collected packages: pip
#11 13.28   Attempting uninstall: pip
#11 13.30     Found existing installation: pip 25.0.1
#11 13.74     Uninstalling pip-25.0.1:
#11 15.52       Successfully uninstalled pip-25.0.1
#11 22.30 WARNING: Running pip as the 'root' user can result in broken permissions and conflicting behaviour with the system package manager, possibly rendering your system unusable. It is recommended to use a virtual environment instead: https://pip.pypa.io/warnings/venv. Use the --root-user-action option if you know what you are doing and want to suppress this warning.
#11 22.30 Successfully installed pip-26.1.2
#11 30.16 Collecting httpx>=0.27 (from httpx[http2]>=0.27)
#11 30.45   Downloading httpx-0.28.1-py3-none-any.whl.metadata (7.1 kB)
#11 30.59 Collecting tenacity>=8.3
#11 30.64   Downloading tenacity-9.1.4-py3-none-any.whl.metadata (1.2 kB)
#11 33.26 Collecting lxml>=5.2
#11 33.30   Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl.metadata (3.5 kB)
#11 33.83 Collecting psycopg2-binary>=2.9
#11 33.89   Downloading psycopg2_binary-2.9.12-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.metadata (4.9 kB)
#11 33.99 Collecting pgvector>=0.3
#11 34.04   Downloading pgvector-0.4.2-py3-none-any.whl.metadata (19 kB)
#11 34.69 Collecting openai>=1.35
#11 34.73   Downloading openai-2.41.0-py3-none-any.whl.metadata (32 kB)
#11 35.08 Collecting tiktoken>=0.7
#11 35.13   Downloading tiktoken-0.13.0-cp312-cp312-manylinux_2_28_x86_64.whl.metadata (6.7 kB)
#11 35.45 Collecting fastapi>=0.111
#11 35.48   Downloading fastapi-0.136.3-py3-none-any.whl.metadata (27 kB)
#11 35.69 Collecting uvicorn>=0.30 (from uvicorn[standard]>=0.30)
#11 35.73   Downloading uvicorn-0.49.0-py3-none-any.whl.metadata (6.7 kB)
#11 35.85 Collecting python-dotenv>=1.0
#11 35.88   Downloading python_dotenv-1.2.2-py3-none-any.whl.metadata (27 kB)
#11 36.96 Collecting pydantic>=2.7
#11 37.03   Downloading pydantic-2.13.4-py3-none-any.whl.metadata (109 kB)
#11 37.37 Collecting pydantic-settings>=2.3
#11 37.41   Downloading pydantic_settings-2.14.1-py3-none-any.whl.metadata (3.4 kB)
#11 37.73 Collecting rich>=13.7
#11 37.79   Downloading rich-15.0.0-py3-none-any.whl.metadata (18 kB)
#11 38.16 Collecting anthropic>=0.28
#11 38.19   Downloading anthropic-0.105.2-py3-none-any.whl.metadata (3.2 kB)
#11 38.25 Collecting aiofiles>=23.2
#11 38.29   Downloading aiofiles-25.1.0-py3-none-any.whl.metadata (6.3 kB)
#11 38.39 Collecting python-multipart>=0.0.9
#11 38.42   Downloading python_multipart-0.0.30-py3-none-any.whl.metadata (2.1 kB)
#11 40.57 Collecting cryptography>=42.0
#11 40.60   Downloading cryptography-48.0.0-cp311-abi3-manylinux_2_34_x86_64.whl.metadata (4.3 kB)
#11 40.74 Collecting PyJWT>=2.8
#11 40.78   Downloading pyjwt-2.13.0-py3-none-any.whl.metadata (3.4 kB)
#11 43.18 Collecting boto3>=1.34
#11 43.22   Downloading boto3-1.43.22-py3-none-any.whl.metadata (6.6 kB)
#11 43.33 Collecting fastembed>=0.3.0
#11 43.38   Downloading fastembed-0.8.0-py3-none-any.whl.metadata (10 kB)
#11 43.46 Collecting slowapi>=0.1.9
#11 43.51   Downloading slowapi-0.1.9-py3-none-any.whl.metadata (3.0 kB)
#11 43.76 Collecting redis>=5.0 (from redis[hiredis]>=5.0)
#11 43.82   Downloading redis-8.0.0-py3-none-any.whl.metadata (13 kB)
#11 44.56 Collecting stripe>=10.0
#11 44.60   Downloading stripe-15.2.0-py3-none-any.whl.metadata (18 kB)
#11 44.84 Collecting pypdf>=4.0
#11 44.89   Downloading pypdf-6.12.2-py3-none-any.whl.metadata (7.2 kB)
#11 45.00 Collecting python-docx>=1.1
#11 45.08   Downloading python_docx-1.2.0-py3-none-any.whl.metadata (2.0 kB)
#11 45.28 Collecting anyio (from httpx>=0.27->httpx[http2]>=0.27)
#11 45.33   Downloading anyio-4.13.0-py3-none-any.whl.metadata (4.5 kB)
#11 45.50 Collecting certifi (from httpx>=0.27->httpx[http2]>=0.27)
#11 45.57   Downloading certifi-2026.5.20-py3-none-any.whl.metadata (2.5 kB)
#11 45.71 Collecting httpcore==1.* (from httpx>=0.27->httpx[http2]>=0.27)
#11 45.76   Downloading httpcore-1.0.9-py3-none-any.whl.metadata (21 kB)
#11 45.90 Collecting idna (from httpx>=0.27->httpx[http2]>=0.27)
#11 45.94   Downloading idna-3.18-py3-none-any.whl.metadata (6.1 kB)
#11 46.06 Collecting h11>=0.16 (from httpcore==1.*->httpx>=0.27->httpx[http2]>=0.27)
#11 46.11   Downloading h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
#11 48.67 Collecting numpy (from pgvector>=0.3)
#11 48.72   Downloading numpy-2.4.6-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (6.6 kB)
#11 48.84 Collecting distro<2,>=1.7.0 (from openai>=1.35)
#11 48.88   Downloading distro-1.9.0-py3-none-any.whl.metadata (6.8 kB)
#11 49.64 Collecting jiter<1,>=0.10.0 (from openai>=1.35)
#11 49.70   Downloading jiter-0.15.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (5.2 kB)
#11 49.82 Collecting sniffio (from openai>=1.35)
#11 49.87   Downloading sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
#11 50.18 Collecting tqdm>4 (from openai>=1.35)
#11 50.23   Downloading tqdm-4.67.3-py3-none-any.whl.metadata (57 kB)
#11 50.45 Collecting typing-extensions<5,>=4.11 (from openai>=1.35)
#11 50.54   Downloading typing_extensions-4.15.0-py3-none-any.whl.metadata (3.3 kB)
#11 50.61 Collecting annotated-types>=0.6.0 (from pydantic>=2.7)
#11 50.66   Downloading annotated_types-0.7.0-py3-none-any.whl.metadata (15 kB)
#11 59.25 Collecting pydantic-core==2.46.4 (from pydantic>=2.7)
#11 59.29   Downloading pydantic_core-2.46.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (6.6 kB)
#11 59.37 Collecting typing-inspection>=0.4.2 (from pydantic>=2.7)
#11 59.41   Downloading typing_inspection-0.4.2-py3-none-any.whl.metadata (2.6 kB)
#11 63.99 Collecting regex (from tiktoken>=0.7)
#11 64.05   Downloading regex-2026.5.9-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (40 kB)
#11 64.37 Collecting requests (from tiktoken>=0.7)
#11 64.44   Downloading requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
#11 64.70 Collecting starlette>=0.46.0 (from fastapi>=0.111)
#11 64.76   Downloading starlette-1.2.1-py3-none-any.whl.metadata (6.3 kB)
#11 64.94 Collecting annotated-doc>=0.0.2 (from fastapi>=0.111)
#11 65.01   Downloading annotated_doc-0.0.4-py3-none-any.whl.metadata (6.6 kB)
#11 65.19 Collecting click>=7.0 (from uvicorn>=0.30->uvicorn[standard]>=0.30)
#11 65.25   Downloading click-8.4.1-py3-none-any.whl.metadata (2.6 kB)
#11 65.42 Collecting markdown-it-py>=2.2.0 (from rich>=13.7)
#11 65.47   Downloading markdown_it_py-4.2.0-py3-none-any.whl.metadata (7.4 kB)
#11 65.71 Collecting pygments<3.0.0,>=2.13.0 (from rich>=13.7)
#11 65.80   Downloading pygments-2.20.0-py3-none-any.whl.metadata (2.5 kB)
#11 65.92 Collecting docstring-parser<1,>=0.15 (from anthropic>=0.28)
#11 65.98   Downloading docstring_parser-0.18.0-py3-none-any.whl.metadata (3.5 kB)
#11 67.25 Collecting cffi>=2.0.0 (from cryptography>=42.0)
#11 67.32   Downloading cffi-2.0.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.metadata (2.6 kB)
#11 70.08 Collecting botocore<1.44.0,>=1.43.22 (from boto3>=1.34)
#11 70.13   Downloading botocore-1.43.22-py3-none-any.whl.metadata (5.6 kB)
#11 70.20 Collecting jmespath<2.0.0,>=0.7.1 (from boto3>=1.34)
#11 70.26   Downloading jmespath-1.1.0-py3-none-any.whl.metadata (7.6 kB)
#11 70.38 Collecting s3transfer<0.19.0,>=0.18.0 (from boto3>=1.34)
#11 70.42   Downloading s3transfer-0.18.0-py3-none-any.whl.metadata (1.7 kB)
#11 70.49 Collecting python-dateutil<3.0.0,>=2.1 (from botocore<1.44.0,>=1.43.22->boto3>=1.34)
#11 70.59   Downloading python_dateutil-2.9.0.post0-py2.py3-none-any.whl.metadata (8.4 kB)
#11 70.80 Collecting urllib3!=2.2.0,<3,>=1.25.4 (from botocore<1.44.0,>=1.43.22->boto3>=1.34)
#11 70.83   Downloading urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
#11 70.92 Collecting six>=1.5 (from python-dateutil<3.0.0,>=2.1->botocore<1.44.0,>=1.43.22->boto3>=1.34)
#11 70.96   Downloading six-1.17.0-py2.py3-none-any.whl.metadata (1.7 kB)
#11 71.38 Collecting huggingface-hub<2.0,>=0.20 (from fastembed>=0.3.0)
#11 71.44   Downloading huggingface_hub-1.17.0-py3-none-any.whl.metadata (14 kB)
#11 71.63 Collecting loguru<0.8.0,>=0.7.2 (from fastembed>=0.3.0)
#11 71.69   Downloading loguru-0.7.3-py3-none-any.whl.metadata (22 kB)
#11 72.23 Collecting mmh3<6.0.0,>=4.1.0 (from fastembed>=0.3.0)
#11 72.27   Downloading mmh3-5.2.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl.metadata (14 kB)
#11 72.80 Collecting onnxruntime!=1.20.0,!=1.24.0,!=1.24.1,>=1.17.0 (from fastembed>=0.3.0)
#11 72.84   Downloading onnxruntime-1.26.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (5.3 kB)
#11 74.07 Collecting pillow<13.0,>=10.3.0 (from fastembed>=0.3.0)
#11 74.12   Downloading pillow-12.2.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl.metadata (8.8 kB)
#11 74.42 Collecting py-rust-stemmers<0.2.0,>=0.1.0 (from fastembed>=0.3.0)
#11 74.45   Downloading py_rust_stemmers-0.1.8-cp312-cp312-manylinux_2_28_x86_64.whl.metadata (3.5 kB)
#11 76.05 Collecting tokenizers<1.0,>=0.15 (from fastembed>=0.3.0)
#11 76.11   Downloading tokenizers-0.23.1-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (9.8 kB)
#11 76.34 Collecting filelock>=3.10.0 (from huggingface-hub<2.0,>=0.20->fastembed>=0.3.0)
#11 76.41   Downloading filelock-3.29.1-py3-none-any.whl.metadata (2.0 kB)
#11 76.56 Collecting fsspec>=2023.5.0 (from huggingface-hub<2.0,>=0.20->fastembed>=0.3.0)
#11 76.60   Downloading fsspec-2026.4.0-py3-none-any.whl.metadata (10 kB)
#11 77.50 Collecting hf-xet<2.0.0,>=1.4.3 (from huggingface-hub<2.0,>=0.20->fastembed>=0.3.0)
#11 77.55   Downloading hf_xet-1.5.0-cp37-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl.metadata (4.9 kB)
#11 77.65 Collecting packaging>=20.9 (from huggingface-hub<2.0,>=0.20->fastembed>=0.3.0)
#11 77.72   Downloading packaging-26.2-py3-none-any.whl.metadata (3.5 kB)
#11 78.05 Collecting pyyaml>=5.1 (from huggingface-hub<2.0,>=0.20->fastembed>=0.3.0)
#11 78.10   Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.4 kB)
#11 78.29 Collecting typer<0.26.0,>=0.20.0 (from huggingface-hub<2.0,>=0.20->fastembed>=0.3.0)
#11 78.35   Downloading typer-0.25.1-py3-none-any.whl.metadata (15 kB)
#11 79.34 Collecting charset_normalizer<4,>=2 (from requests->tiktoken>=0.7)
#11 79.40   Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (40 kB)
#11 79.75 Collecting shellingham>=1.3.0 (from typer<0.26.0,>=0.20.0->huggingface-hub<2.0,>=0.20->fastembed>=0.3.0)
#11 79.80   Downloading shellingham-1.5.4-py2.py3-none-any.whl.metadata (3.5 kB)
#11 80.08 Collecting limits>=2.3 (from slowapi>=0.1.9)
#11 80.13   Downloading limits-5.8.0-py3-none-any.whl.metadata (10 kB)
#11 80.38 Collecting pycparser (from cffi>=2.0.0->cryptography>=42.0)
#11 80.44   Downloading pycparser-3.0-py3-none-any.whl.metadata (8.2 kB)
#11 80.59 Collecting h2<5,>=3 (from httpx[http2]>=0.27)
#11 80.66   Downloading h2-4.3.0-py3-none-any.whl.metadata (5.1 kB)
#11 80.74 Collecting hyperframe<7,>=6.1 (from h2<5,>=3->httpx[http2]>=0.27)
#11 80.79   Downloading hyperframe-6.1.0-py3-none-any.whl.metadata (4.3 kB)
#11 80.84 Collecting hpack<5,>=4.1 (from h2<5,>=3->httpx[http2]>=0.27)
#11 80.89   Downloading hpack-4.1.0-py3-none-any.whl.metadata (4.6 kB)
#11 81.03 Collecting deprecated>=1.2 (from limits>=2.3->slowapi>=0.1.9)
#11 81.07   Downloading deprecated-1.3.1-py2.py3-none-any.whl.metadata (5.9 kB)
#11 82.92 Collecting wrapt<3,>=1.10 (from deprecated>=1.2->limits>=2.3->slowapi>=0.1.9)
#11 82.97   Downloading wrapt-2.2.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl.metadata (7.4 kB)
#11 83.04 Collecting mdurl~=0.1 (from markdown-it-py>=2.2.0->rich>=13.7)
#11 83.09   Downloading mdurl-0.1.2-py3-none-any.whl.metadata (1.6 kB)
#11 83.21 Collecting flatbuffers (from onnxruntime!=1.20.0,!=1.24.0,!=1.24.1,>=1.17.0->fastembed>=0.3.0)
#11 83.24   Downloading flatbuffers-25.12.19-py2.py3-none-any.whl.metadata (1.0 kB)
#11 84.54 Collecting protobuf (from onnxruntime!=1.20.0,!=1.24.0,!=1.24.1,>=1.17.0->fastembed>=0.3.0)
#11 84.57   Downloading protobuf-7.35.0-cp310-abi3-manylinux2014_x86_64.whl.metadata (595 bytes)
#11 85.84 Collecting hiredis>=3.2.0 (from redis[hiredis]>=5.0)
#11 85.87   Downloading hiredis-3.4.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (7.5 kB)
#11 86.56 Collecting httptools>=0.8.0 (from uvicorn[standard]>=0.30)
#11 86.60   Downloading httptools-0.8.0-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl.metadata (3.5 kB)
#11 87.02 Collecting uvloop>=0.15.1 (from uvicorn[standard]>=0.30)
#11 87.05   Downloading uvloop-0.22.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (4.9 kB)
#11 87.92 Collecting watchfiles>=0.20 (from uvicorn[standard]>=0.30)
#11 87.96   Downloading watchfiles-1.2.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (4.9 kB)
#11 88.72 Collecting websockets>=10.4 (from uvicorn[standard]>=0.30)
#11 88.78   Downloading websockets-16.0-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl.metadata (6.8 kB)
#11 88.97 Downloading httpx-0.28.1-py3-none-any.whl (73 kB)
#11 89.04 Downloading httpcore-1.0.9-py3-none-any.whl (78 kB)
#11 89.20 Downloading tenacity-9.1.4-py3-none-any.whl (28 kB)
#11 89.25 Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl (5.2 MB)
#11 91.28    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.2/5.2 MB 2.6 MB/s  0:00:02
#11 91.33 Downloading psycopg2_binary-2.9.12-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (4.3 MB)
#11 92.81    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.3/4.3 MB 3.0 MB/s  0:00:01
#11 92.86 Downloading pgvector-0.4.2-py3-none-any.whl (27 kB)
#11 92.94 Downloading openai-2.41.0-py3-none-any.whl (1.4 MB)
#11 93.73    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.4/1.4 MB 1.9 MB/s  0:00:00
#11 93.83 Downloading pydantic-2.13.4-py3-none-any.whl (472 kB)
#11 94.10 Downloading pydantic_core-2.46.4-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (2.1 MB)
#11 95.05    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.1/2.1 MB 2.5 MB/s  0:00:00
#11 95.10 Downloading anyio-4.13.0-py3-none-any.whl (114 kB)
#11 95.19 Downloading distro-1.9.0-py3-none-any.whl (20 kB)
#11 95.22 Downloading jiter-0.15.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (346 kB)
#11 95.41 Downloading typing_extensions-4.15.0-py3-none-any.whl (44 kB)
#11 95.47 Downloading tiktoken-0.13.0-cp312-cp312-manylinux_2_28_x86_64.whl (1.1 MB)
#11 96.32    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.1/1.1 MB 1.1 MB/s  0:00:00
#11 96.37 Downloading fastapi-0.136.3-py3-none-any.whl (117 kB)
#11 96.51 Downloading uvicorn-0.49.0-py3-none-any.whl (71 kB)
#11 96.62 Downloading python_dotenv-1.2.2-py3-none-any.whl (22 kB)
#11 96.71 Downloading pydantic_settings-2.14.1-py3-none-any.whl (60 kB)
#11 96.80 Downloading rich-15.0.0-py3-none-any.whl (310 kB)
#11 97.05 Downloading pygments-2.20.0-py3-none-any.whl (1.2 MB)
#11 98.15    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 1.2/1.2 MB 1.2 MB/s  0:00:01
#11 98.20 Downloading anthropic-0.105.2-py3-none-any.whl (837 kB)
#11 98.82    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 837.5/837.5 kB 1.5 MB/s  0:00:00
#11 98.86 Downloading docstring_parser-0.18.0-py3-none-any.whl (22 kB)
#11 98.98 Downloading aiofiles-25.1.0-py3-none-any.whl (14 kB)
#11 99.02 Downloading python_multipart-0.0.30-py3-none-any.whl (29 kB)
#11 99.08 Downloading cryptography-48.0.0-cp311-abi3-manylinux_2_34_x86_64.whl (4.7 MB)
#11 101.7    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.7/4.7 MB 1.9 MB/s  0:00:02
#11 101.8 Downloading pyjwt-2.13.0-py3-none-any.whl (31 kB)
#11 101.8 Downloading boto3-1.43.22-py3-none-any.whl (140 kB)
#11 102.0 Downloading botocore-1.43.22-py3-none-any.whl (15.1 MB)
#11 108.8    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 15.1/15.1 MB 2.2 MB/s  0:00:06
#11 108.9 Downloading jmespath-1.1.0-py3-none-any.whl (20 kB)
#11 108.9 Downloading python_dateutil-2.9.0.post0-py2.py3-none-any.whl (229 kB)
#11 109.1 Downloading s3transfer-0.18.0-py3-none-any.whl (88 kB)
#11 109.2 Downloading urllib3-2.7.0-py3-none-any.whl (131 kB)
#11 109.3 Downloading fastembed-0.8.0-py3-none-any.whl (116 kB)
#11 109.3 Downloading huggingface_hub-1.17.0-py3-none-any.whl (671 kB)
#11 109.6    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 671.5/671.5 kB 2.2 MB/s  0:00:00
#11 109.7 Downloading hf_xet-1.5.0-cp37-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (4.5 MB)
#11 112.0    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.5/4.5 MB 2.0 MB/s  0:00:02
#11 112.1 Downloading loguru-0.7.3-py3-none-any.whl (61 kB)
#11 112.1 Downloading mmh3-5.2.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl (103 kB)
#11 112.2 Downloading pillow-12.2.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (7.1 MB)
#11 115.5    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7.1/7.1 MB 2.2 MB/s  0:00:03
#11 115.5 Downloading py_rust_stemmers-0.1.8-cp312-cp312-manylinux_2_28_x86_64.whl (323 kB)
#11 115.8 Downloading requests-2.34.2-py3-none-any.whl (73 kB)
#11 115.9 Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (216 kB)
#11 115.9 Downloading idna-3.18-py3-none-any.whl (65 kB)
#11 116.0 Downloading tokenizers-0.23.1-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (3.3 MB)
#11 116.9    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.3/3.3 MB 3.8 MB/s  0:00:00
#11 117.0 Downloading tqdm-4.67.3-py3-none-any.whl (78 kB)
#11 117.1 Downloading typer-0.25.1-py3-none-any.whl (58 kB)
#11 117.1 Downloading slowapi-0.1.9-py3-none-any.whl (14 kB)
#11 117.2 Downloading redis-8.0.0-py3-none-any.whl (499 kB)
#11 117.5 Downloading stripe-15.2.0-py3-none-any.whl (2.2 MB)
#11 118.3    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2.2/2.2 MB 3.1 MB/s  0:00:00
#11 118.3 Downloading pypdf-6.12.2-py3-none-any.whl (343 kB)
#11 118.5 Downloading python_docx-1.2.0-py3-none-any.whl (252 kB)
#11 118.6 Downloading annotated_doc-0.0.4-py3-none-any.whl (5.3 kB)
#11 118.7 Downloading annotated_types-0.7.0-py3-none-any.whl (13 kB)
#11 118.7 Downloading certifi-2026.5.20-py3-none-any.whl (134 kB)
#11 118.8 Downloading cffi-2.0.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.whl (219 kB)
#11 119.0 Downloading click-8.4.1-py3-none-any.whl (116 kB)
#11 119.0 Downloading filelock-3.29.1-py3-none-any.whl (40 kB)
#11 119.1 Downloading fsspec-2026.4.0-py3-none-any.whl (203 kB)
#11 119.2 Downloading h11-0.16.0-py3-none-any.whl (37 kB)
#11 119.3 Downloading h2-4.3.0-py3-none-any.whl (61 kB)
#11 119.3 Downloading hpack-4.1.0-py3-none-any.whl (34 kB)
#11 119.4 Downloading hyperframe-6.1.0-py3-none-any.whl (13 kB)
#11 119.4 Downloading limits-5.8.0-py3-none-any.whl (60 kB)
#11 119.5 Downloading deprecated-1.3.1-py2.py3-none-any.whl (11 kB)
#11 119.5 Downloading wrapt-2.2.1-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl (169 kB)
#11 119.6 Downloading markdown_it_py-4.2.0-py3-none-any.whl (91 kB)
#11 119.7 Downloading mdurl-0.1.2-py3-none-any.whl (10.0 kB)
#11 119.7 Downloading numpy-2.4.6-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (16.6 MB)
#11 126.5    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 16.6/16.6 MB 2.5 MB/s  0:00:06
#11 126.5 Downloading onnxruntime-1.26.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl (18.2 MB)
#11 134.7    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 18.2/18.2 MB 2.2 MB/s  0:00:08
#11 134.8 Downloading packaging-26.2-py3-none-any.whl (100 kB)
#11 134.8 Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (807 kB)
#11 135.3    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 807.9/807.9 kB 2.4 MB/s  0:00:00
#11 135.3 Downloading hiredis-3.4.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (313 kB)
#11 135.7 Downloading shellingham-1.5.4-py2.py3-none-any.whl (9.8 kB)
#11 135.8 Downloading six-1.17.0-py2.py3-none-any.whl (11 kB)
#11 135.8 Downloading starlette-1.2.1-py3-none-any.whl (73 kB)
#11 136.0 Downloading typing_inspection-0.4.2-py3-none-any.whl (14 kB)
#11 136.1 Downloading httptools-0.8.0-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl (523 kB)
#11 136.4 Downloading uvloop-0.22.1-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (4.4 MB)
#11 138.0    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.4/4.4 MB 2.8 MB/s  0:00:01
#11 138.0 Downloading watchfiles-1.2.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (456 kB)
#11 138.3 Downloading websockets-16.0-cp312-cp312-manylinux1_x86_64.manylinux_2_28_x86_64.manylinux_2_5_x86_64.whl (184 kB)
#11 138.4 Downloading flatbuffers-25.12.19-py2.py3-none-any.whl (26 kB)
#11 138.4 Downloading protobuf-7.35.0-cp310-abi3-manylinux2014_x86_64.whl (327 kB)
#11 138.5 Downloading pycparser-3.0-py3-none-any.whl (48 kB)
#11 138.6 Downloading regex-2026.5.9-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (801 kB)
#11 138.8    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 801.2/801.2 kB 2.8 MB/s  0:00:00
#11 138.9 Downloading sniffio-1.3.1-py3-none-any.whl (10 kB)
#11 143.5 Installing collected packages: flatbuffers, wrapt, websockets, uvloop, urllib3, typing-extensions, tqdm, tenacity, sniffio, six, shellingham, regex, redis, pyyaml, python-multipart, python-dotenv, pypdf, PyJWT, pygments, pycparser, py-rust-stemmers, psycopg2-binary, protobuf, pillow, packaging, numpy, mmh3, mdurl, lxml, loguru, jmespath, jiter, idna, hyperframe, httptools, hpack, hiredis, hf-xet, h11, fsspec, filelock, docstring-parser, distro, click, charset_normalizer, certifi, annotated-types, annotated-doc, aiofiles, uvicorn, typing-inspection, requests, python-docx, python-dateutil, pydantic-core, pgvector, onnxruntime, markdown-it-py, httpcore, h2, deprecated, cffi, anyio, watchfiles, tiktoken, stripe, starlette, rich, pydantic, limits, httpx, cryptography, botocore, typer, slowapi, s3transfer, pydantic-settings, openai, fastapi, anthropic, huggingface-hub, boto3, tokenizers, fastembed
