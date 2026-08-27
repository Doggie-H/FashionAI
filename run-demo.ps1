$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $projectRoot 'backend'
$frontend = Join-Path $projectRoot 'web'

$env:AI_STYLIST_DEMO_MODE = '1'

Write-Host 'Starting AI Stylist backend on http://127.0.0.1:8000 ...'
Start-Process -FilePath 'python' `
  -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8000' `
  -WorkingDirectory $backend

Write-Host 'Starting AI Stylist frontend on http://127.0.0.1:3000 ...'
Start-Process -FilePath 'npm.cmd' `
  -ArgumentList 'run','dev' `
  -WorkingDirectory $frontend

Write-Host ''
Write-Host 'Demo is starting. Open http://127.0.0.1:3000 in your browser.'
Write-Host 'Backend health: http://127.0.0.1:8000/health'
Write-Host 'Demo mode is enabled; no large VLM weights are downloaded.'
