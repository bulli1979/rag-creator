# Einmalige Vorbereitung fuer Windows PowerShell
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Write-Host "Created .env from .env.example"
}

Write-Host "Docker modular stack ready."
Write-Host "Examples:"
Write-Host "  docker compose --profile backend --profile ollama up -d --build"
Write-Host "  docker compose --profile full up -d --build"
