param(
    [ValidateSet('worker', 'gpu-worker', 'outbox-worker', 'api', 'check')]
    [string]$Role = 'check'
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $ProjectRoot 'backend'

if (-not (Test-Path $Backend)) {
    throw "Không tìm thấy backend tại: $Backend"
}

Set-Location $Backend

if ($Role -eq 'check') {
    Write-Host "Project root: $ProjectRoot"
    Write-Host "Backend: $Backend"
    python -c "import celery, redis; print('Celery', celery.__version__, '| Redis client OK')"
    python -c "import redis; r=redis.Redis(host='127.0.0.1', port=6379); print('Redis:', r.ping())"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Redis chưa chạy tại 127.0.0.1:6379. Hãy cài Docker Desktop/Redis hoặc chạy Redis trong WSL.'
    }
    exit 0
}

$env:PYTHONPATH = "$Backend;$ProjectRoot"
$env:AI_STYLIST_QUEUE_MODE = 'celery'
$env:CELERY_BROKER_URL = if ($env:CELERY_BROKER_URL) { $env:CELERY_BROKER_URL } else { 'redis://127.0.0.1:6379/0' }
$env:CELERY_RESULT_BACKEND = if ($env:CELERY_RESULT_BACKEND) { $env:CELERY_RESULT_BACKEND } else { 'redis://127.0.0.1:6379/1' }

if ($Role -eq 'worker') {
    python -m celery -A app.queue:celery_app worker --loglevel=INFO --pool=solo --queues=stylist_default
} elseif ($Role -eq 'gpu-worker') {
    python -m celery -A app.queue:celery_app worker --loglevel=INFO --pool=solo --queues=garment_gpu --hostname=garment-gpu@%h
} elseif ($Role -eq 'outbox-worker') {
    python -m celery -A app.queue:celery_app worker --loglevel=INFO --pool=solo --queues=stylist_outbox --hostname=stylist-outbox@%h
} elseif ($Role -eq 'api') {
    python -m uvicorn main:app --host 127.0.0.1 --port 8000
}
