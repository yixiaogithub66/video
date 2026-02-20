param(
    [switch]$Build,
    [switch]$Detached = $true
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found. Please install Docker Desktop and restart PowerShell."
}

Invoke-CheckedCommand -Command { docker info *> $null } -Name "docker engine check"

function Build-FrontendIfNeeded {
    $frontendRoot = Join-Path (Get-Location) "frontend"
    $packageJson = Join-Path $frontendRoot "package.json"
    $distIndex = Join-Path $frontendRoot "dist\\index.html"

    if (-not (Test-Path $packageJson)) {
        return
    }

    if (-not $Build -and (Test-Path $distIndex)) {
        return
    }

    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm not found. Install Node.js to build Vue frontend assets."
    }

    Push-Location $frontendRoot
    try {
        Invoke-CheckedCommand -Command { npm install } -Name "frontend npm install"
        Invoke-CheckedCommand -Command { npm run build } -Name "frontend npm run build"
    } finally {
        Pop-Location
    }
}

Build-FrontendIfNeeded

if ($Build) {
    Invoke-CheckedCommand -Command { docker compose build } -Name "docker compose build"
}

if ($Detached) {
    Invoke-CheckedCommand -Command { docker compose up -d } -Name "docker compose up -d"
} else {
    Invoke-CheckedCommand -Command { docker compose up } -Name "docker compose up"
}

Write-Host "Platform services are starting."
Write-Host "API: http://localhost:8000"
Write-Host "Ops Web: http://localhost:8080"
Write-Host "Temporal UI: http://localhost:8088"
Write-Host "MinIO Console: http://localhost:9001"
Write-Host "API token: dev-token"
