# FinAlly — Stop script for Windows PowerShell
# Stops and removes the container but keeps the data volume.

$ErrorActionPreference = "Stop"

$ContainerName = "finally"

$existing = docker ps -a --format '{{.Names}}' 2>$null | Where-Object { $_ -eq $ContainerName }
if ($existing) {
    Write-Host "Stopping '$ContainerName' container..."
    docker stop $ContainerName 2>$null | Out-Null
    docker rm $ContainerName 2>$null | Out-Null
    Write-Host "Container stopped and removed."
} else {
    Write-Host "No '$ContainerName' container found. Nothing to stop."
}

Write-Host "Data volume 'finally-data' has been preserved."
