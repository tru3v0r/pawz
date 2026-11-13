$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
# Same machine-local environment as build-windows.ps1, outside the synced project.
$VenvRoot = if ($env:PAWZ_VENV_DIR) { $env:PAWZ_VENV_DIR } else { Join-Path $env:LOCALAPPDATA 'pawz\venv-py312' }
$Python = Join-Path $VenvRoot 'Scripts\python.exe'
if (-not (Test-Path $Python)) { py -3.12 -m venv $VenvRoot }
& $Python -m pip install -e '.[test,dev]'
& $Python -m pawz
