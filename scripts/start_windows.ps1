# FinAlly — Start script for Windows PowerShell
# Usage: .\scripts\start_windows.ps1 [-Build] [-Open]
#   -Build   Force rebuild the Docker image
#   -Open    Open the browser after starting

param(
    [switch]$Build,
    [switch]$Open
)

$ErrorActionPreference = "Stop"

$ContainerName = "finally"
$ImageName = "finally"
$Port = 8000
$VolumeName = "finally-data"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvFile = Join-Path $ProjectRoot ".env"

# Stop and remove existing container if running (idempotent)
$existing = docker ps -a --format '{{.Names}}' 2>$null | Where-Object { $_ -eq $ContainerName }
if ($existing) {
    Write-Host "Stopping existing '$ContainerName' container..."
    docker stop $ContainerName 2>$null | Out-Null
    docker rm $ContainerName 2>$null | Out-Null
}

# Build image if it doesn't exist or -Build flag is passed
$imageExists = docker image inspect $ImageName 2>$null
if ($Build -or -not $imageExists) {
    Write-Host "Building Docker image '$ImageName'..."
    docker build -t $ImageName $ProjectRoot
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }
} else {
    Write-Host "Docker image '$ImageName' already exists. Use -Build to rebuild."
}

# Ensure .env file exists
$envFlag = @()
if (-not (Test-Path $EnvFile)) {
    Write-Host "Warning: .env file not found at $EnvFile"
    $exampleEnv = Join-Path $ProjectRoot ".env.example"
    if (Test-Path $exampleEnv) {
        Write-Host "Creating from .env.example..."
        Copy-Item $exampleEnv $EnvFile
        $envFlag = @("--env-file", $EnvFile)
    } else {
        Write-Host "No .env.example found either. Container will start without environment file."
    }
} else {
    $envFlag = @("--env-file", $EnvFile)
}

# Run the container
Write-Host "Starting '$ContainerName' container..."
$dockerArgs = @(
    "run", "-d",
    "--name", $ContainerName,
    "-v", "${VolumeName}:/app/db",
    "-p", "${Port}:${Port}"
)
$dockerArgs += $envFlag
$dockerArgs += $ImageName

& docker @dockerArgs
if ($LASTEXITCODE -ne 0) { throw "Failed to start container" }

Write-Host ""
Write-Host "FinAlly is running at http://localhost:$Port"
Write-Host ""

# Optionally open the browser
if ($Open) {
    Start-Process "http://localhost:$Port"
}
