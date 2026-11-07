param(
    [Parameter(Position = 0)]
    [ValidateSet("setup", "dev", "migrate", "seed", "lint", "typecheck", "test", "test-e2e", "provider-check", "billing-test", "build", "help")]
    [string]$Target = "help"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-Python {
    $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    throw "Python venv is missing. Run: powershell -File scripts/bb.ps1 setup"
}

function Set-PythonPath {
    $env:PYTHONPATH = @(
        (Join-Path $Root "services\backend"),
        (Join-Path $Root "services\worker"),
        (Join-Path $Root "packages\runtime")
    ) -join ";"
}

function Import-DotEnv {
    $path = Join-Path $Root ".env"
    if (-not (Test-Path $path)) {
        return
    }
    foreach ($line in Get-Content $path) {
        if ($line -match '^\s*#' -or $line -notmatch '=') {
            continue
        }
        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($name) {
            Set-Item -Path "Env:$name" -Value $value
        }
    }
}

switch ($Target) {
    "help" {
        Write-Host "Usage: powershell -File scripts/bb.ps1 <setup|dev|migrate|seed|lint|typecheck|test|test-e2e|provider-check|billing-test|build>"
    }
    "setup" {
        python -m venv (Join-Path $Root ".venv")
        $python = Get-Python
        & $python -m pip install --upgrade pip
        & $python -m pip install -e (Join-Path $Root "packages\runtime") -r (Join-Path $Root "services\backend\requirements.txt") -r (Join-Path $Root "services\worker\requirements.txt")
        Push-Location (Join-Path $Root "apps\web")
        npm install
        Pop-Location
    }
    "dev" {
        if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
            throw "Docker is not installed. Install Docker Desktop, then rerun dev."
        }
        docker compose up -d postgres redis mailpit
        if (-not (Test-Path (Join-Path $Root ".env"))) {
            Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
            Write-Host "Created .env from .env.example"
        }
        Import-DotEnv
        Set-PythonPath
        $python = Get-Python
        $api = Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", (Join-Path $Root "services\backend"), "--reload", "--port", "8000") -PassThru -WindowStyle Hidden
        $worker = Start-Process -FilePath $python -ArgumentList @("-m", "worker.main") -PassThru -WindowStyle Hidden
        Write-Host "API pid $($api.Id), worker pid $($worker.Id). Stop those processes when you finish."
        Push-Location (Join-Path $Root "apps\web")
        try {
            npm run dev -- --host 0.0.0.0 --port 5173
        }
        finally {
            Pop-Location
            Stop-Process -Id $api.Id, $worker.Id -Force -ErrorAction SilentlyContinue
        }
    }
    "migrate" {
        Import-DotEnv
        Set-PythonPath
        Push-Location (Join-Path $Root "services\backend")
        & (Get-Python) -m alembic upgrade head
        Pop-Location
    }
    "seed" {
        Import-DotEnv
        Set-PythonPath
        & (Get-Python) (Join-Path $Root "scripts\seed.py")
    }
    "lint" {
        Set-PythonPath
        & (Get-Python) -m ruff check (Join-Path $Root "services") (Join-Path $Root "packages") (Join-Path $Root "scripts")
        Push-Location (Join-Path $Root "apps\web")
        npm run lint
        Pop-Location
    }
    "typecheck" {
        Set-PythonPath
        & (Get-Python) -m mypy
        Push-Location (Join-Path $Root "apps\web")
        npm run typecheck
        Pop-Location
    }
    "test" {
        Set-PythonPath
        & (Get-Python) -m pytest -q
        Push-Location (Join-Path $Root "apps\web")
        npm test
        Pop-Location
    }
    "test-e2e" {
        Push-Location (Join-Path $Root "apps\web")
        npm run test:e2e
        Pop-Location
    }
    "provider-check" {
        Set-PythonPath
        & (Get-Python) (Join-Path $Root "scripts\provider_check.py")
    }
    "billing-test" {
        Set-PythonPath
        & (Get-Python) (Join-Path $Root "scripts\billing_test.py")
    }
    "build" {
        Push-Location (Join-Path $Root "apps\web")
        npm run build
        Pop-Location
    }
}
