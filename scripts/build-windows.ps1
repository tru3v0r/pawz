$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed (exit code $LASTEXITCODE). No successful build was produced."
    }
}

# Python 3.12 has prebuilt wheels for pygame 2.6.1 on Windows.
& python -c 'import sys; print(sys.version); sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'Python 3.12 is required. Install it from python.org, then rerun this script.'
}

# Keep the environment outside the (Dropbox-synced) project: venvs are machine-specific.
$VenvRoot = if ($env:PAWZ_VENV_DIR) { $env:PAWZ_VENV_DIR } else { Join-Path $env:LOCALAPPDATA 'pawz\venv-py312' }
$Python = Join-Path $VenvRoot 'Scripts\python.exe'
if (Test-Path $Python) {
    & $Python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) {
        throw "Existing virtual environment is not Python 3.12: $VenvRoot. Remove it or set PAWZ_VENV_DIR."
    }
} else {
    Invoke-Checked 'Create Python 3.12 environment' { python -m venv $VenvRoot }
}

Invoke-Checked 'Install dependencies' { & $Python -m pip install --only-binary pygame -e '.[build,test,dev]' }
Invoke-Checked 'Run tests' { & $Python -m pytest -q }
Invoke-Checked 'Prepare UI Automation interfaces' {
    & $Python -c "from comtypes.client import GetModule; GetModule('UIAutomationCore.dll')"
}

Invoke-Checked 'Build Windows executable' {
    & $Python -m PyInstaller --noconfirm --clean pawz.spec
}

$Exe = Join-Path $ProjectRoot 'dist\pawz\pawz.exe'
if (-not (Test-Path $Exe)) { throw "PyInstaller finished without creating $Exe" }
& (Join-Path $PSScriptRoot 'test-build-windows.ps1') -Executable $Exe

New-Item -ItemType Directory -Force 'dist\pawz\config' | Out-Null
Copy-Item 'config\*' 'dist\pawz\config\' -Recurse -Force -ErrorAction Stop
Copy-Item 'docs' 'dist\pawz\docs' -Recurse -Force -ErrorAction Stop
Copy-Item 'browser-extension' 'dist\pawz\browser-extension' -Recurse -Force -ErrorAction Stop
Copy-Item 'LICENSE' 'dist\pawz\LICENSE' -Force -ErrorAction Stop
Write-Host "SUCCESS: $Exe" -ForegroundColor Green
