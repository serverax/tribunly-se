param(
    [ValidateSet("all", "compose-only", "test-only")]
    [string]$Mode = "all"
)

$ErrorActionPreference = "Stop"

$root = (git rev-parse --show-toplevel).Trim()
Set-Location $root

function Invoke-Python {
    param(
        [string[]]$Args
    )

    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Args
        if ($LASTEXITCODE -ne 0) { throw "python failed with exit code $LASTEXITCODE" }
        return
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Args
        if ($LASTEXITCODE -ne 0) { throw "py -3 failed with exit code $LASTEXITCODE" }
        return
    }

    $candidate = "C:\Users\kalsh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $candidate) {
        & $candidate @Args
        if ($LASTEXITCODE -ne 0) { throw "$candidate failed with exit code $LASTEXITCODE" }
        return
    }

    throw "python not found"
}

$tmpEnv = $null
try {
    if (-not $env:SE_ENV_FILE) {
        $tmpEnv = [System.IO.Path]::GetTempFileName()
        @"
POSTGRES_PASSWORD=ci-password
POSTGRES_DB=postgres
POSTGRES_USER=lawapp
JWT_SECRET=ci-jwt-secret
ADMIN_API_KEY=ci-admin-key
ENCRYPTION_KEY=ci-encryption-key-00000000000000000000000000000000
LAWAPP_DOMAIN=employment_se
LAWAPP_ENABLE_SE=true
LAWAPP_LLM_PROVIDER=ollama_local
LAWAPP_OLLAMA_BASE_URL=http://ollama:11434
LAWAPP_OLLAMA_MODEL=qwen2.5:3b-instruct-q6_K
BACKEND_PORT=6450
OLLAMA_PORT=11450
REDACTION_SERVICE_PORT=8150
RATELIMIT_STORAGE_URI=redis://redis:6379
PAYMENT_MODE=disabled
LOG_LEVEL=INFO
ENVIRONMENT=development
"@ | Set-Content -NoNewline -Path $tmpEnv
        $env:SE_ENV_FILE = $tmpEnv
    }

    function Invoke-ComposeCheck {
        param(
            [string]$Label,
            [string[]]$ComposeArgs
        )

        Write-Host "==> docker compose config: $Label"
        & docker compose --env-file $env:SE_ENV_FILE @ComposeArgs config | Out-Null
    }

    if ($Mode -eq "compose-only" -or $Mode -eq "all") {
        Invoke-ComposeCheck -Label "root" -ComposeArgs @("-f", "docker-compose.yml")
        Invoke-ComposeCheck -Label "sweden" -ComposeArgs @("-f", "docker-compose.se.yml")
    }

    if ($Mode -eq "compose-only") {
        Write-Host "CI CHECK: compose-only pass"
        exit 0
    }

    if ($Mode -ne "test-only" -and $Mode -ne "all") {
        throw "Unknown mode: $Mode"
    }

    $devDepsReady = $true
    try {
        Invoke-Python -Args @("-c", "import pytest, ruff") | Out-Null
    } catch {
        $devDepsReady = $false
    }

    if (-not $devDepsReady) {
        Invoke-Python -Args @("-m", "pip", "install", "--upgrade", "pip")
        Invoke-Python -Args @("-m", "pip", "install", "-e", ".[dev]")
    } else {
        Write-Host "Dev deps already available; skipping install"
    }

    Invoke-Python -Args @("-m", "ruff", "check", "backend", "ingestion", "scripts", "tests")
    Invoke-Python -Args @(
        "-m",
        "pytest",
        "tests/test_jurisdiction_registry_se.py",
        "tests/ingestion/test_riksdagen_parser.py",
        "tests/test_rag_1024_retrieval_repair.py",
        "-q"
    )

    Write-Host "CI CHECK: pass"
}
finally {
    if ($tmpEnv) {
        Remove-Item -Force $tmpEnv
    }
}
