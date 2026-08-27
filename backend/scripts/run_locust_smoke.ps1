[CmdletBinding()]
param(
    [string]$Python = "C:\Python314\python.exe",
    [int]$Users = 2,
    [int]$SpawnRate = 1,
    [string]$Duration = "5s",
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
$DatabasePath = Join-Path $BackendRoot "locust_smoke.db"
$ApiLog = Join-Path $env:TEMP "ai-stylist-locust-smoke-api.log"
$CsvPrefix = Join-Path $env:TEMP "ai-stylist-locust-smoke"

Remove-Item $DatabasePath, $ApiLog -Force -ErrorAction SilentlyContinue
$env:DATABASE_URL = "sqlite:///./locust_smoke.db"
$env:AI_STYLIST_DEMO_MODE = "1"
$env:WORKFLOW_OUTBOX_ENABLED = "1"

$api = Start-Process -FilePath $Python `
    -ArgumentList "-m uvicorn main:app --host 127.0.0.1 --port $Port" `
    -WorkingDirectory $BackendRoot `
    -RedirectStandardOutput $ApiLog `
    -PassThru

try {
    Start-Sleep -Seconds 3
    if ($api.HasExited) {
        Get-Content $ApiLog -ErrorAction SilentlyContinue
        throw "Demo API did not start."
    }

    $seedRaw = & $Python (Join-Path $PSScriptRoot "seed_locust_styling_session.py") 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "Locust seed failed:`n$seedRaw"
    }
    $seed = $seedRaw | ConvertFrom-Json
    $env:LOCUST_LEGACY_ACTOR_ID = [string]$seed.LOCUST_LEGACY_ACTOR_ID
    $env:LOCUST_BODY_PROFILE_ID = [string]$seed.LOCUST_BODY_PROFILE_ID
    $env:LOCUST_WARDROBE_ASSET_IDS = [string]$seed.LOCUST_WARDROBE_ASSET_IDS

    Push-Location $BackendRoot
    try {
        & $Python -m locust -f load_tests\locustfile.py --headless -u $Users -r $SpawnRate -t $Duration --host "http://127.0.0.1:$Port" --csv $CsvPrefix
        if ($LASTEXITCODE -ne 0) {
            throw "Locust exited with code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    if (!$api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
    Remove-Item $DatabasePath -Force -ErrorAction SilentlyContinue
}
