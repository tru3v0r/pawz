param([Parameter(Mandatory=$true)][string]$Executable)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Exe = (Resolve-Path -LiteralPath $Executable).Path
$SmokeRoot = Join-Path $ProjectRoot ('build\smoke-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $SmokeRoot -Force | Out-Null
$Report = Join-Path $SmokeRoot 'report.json'
$PreviousData = $env:PAWZ_DATA_DIR
$PreviousReport = $env:PAWZ_SMOKE_REPORT
try {
    $env:PAWZ_DATA_DIR = Join-Path $SmokeRoot 'settings'
    $env:PAWZ_SMOKE_REPORT = $Report
    # Use an ephemeral loopback port so another running copy is not disturbed.
    New-Item -ItemType Directory -Path $env:PAWZ_DATA_DIR -Force | Out-Null
    '{"schema_version":2,"profiles":{"Default":{}},"port":0}' |
        Set-Content -LiteralPath (Join-Path $env:PAWZ_DATA_DIR 'settings.json') -Encoding Ascii
    $Process = Start-Process -FilePath $Exe -WorkingDirectory $env:TEMP -WindowStyle Hidden -PassThru
    if (-not $Process.WaitForExit(30000)) {
        $Process.Kill()
        throw 'Application startup timed out; no successful smoke test.'
    }
    if ($Process.ExitCode -ne 0) { throw "Application failed: $($Process.ExitCode)" }
    if (-not (Test-Path -LiteralPath $Report)) { throw 'Application did not produce its startup report.' }
    $Result = Get-Content -LiteralPath $Report -Raw | ConvertFrom-Json
    if (-not $Result.started -or -not $Result.svg_valid -or $Result.models -lt 1) {
        throw "Startup/resource validation failed: $(ConvertTo-Json $Result -Compress)"
    }
    if ($Result.fonts.'Matcha Style' -ne 'Matcha Style' -or $Result.fonts.'Inter 18pt' -ne 'Inter 18pt' -or -not $Result.library_prompt_valid) {
        throw 'Bundled fonts or library SVG prompts failed to load.'
    }
    if (-not $Result.vector_icon_native_dpi) { throw 'Native-DPI SVG icon rendering failed.' }
    if (-not $Result.model_svgs_valid) { throw 'Packaged controller model SVGs failed to load.' }
    Write-Host "Startup, JSON schema/catalog and SVG loading verified: $Report"
} finally {
    $env:PAWZ_DATA_DIR = $PreviousData
    $env:PAWZ_SMOKE_REPORT = $PreviousReport
}
