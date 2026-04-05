param(
    [ValidateSet("start", "stop", "status", "verify")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"
$WorkerDir = Join-Path $Root "apps\worker"

$ApiLog = Join-Path $env:TEMP "detection-ai-api.log"
$ApiErr = Join-Path $env:TEMP "detection-ai-api.err.log"
$WebLog = Join-Path $env:TEMP "detection-ai-web.log"
$WebErr = Join-Path $env:TEMP "detection-ai-web.err.log"
$WorkerLog = Join-Path $env:TEMP "detection-ai-worker.log"
$WorkerErr = Join-Path $env:TEMP "detection-ai-worker.err.log"

function Get-ProjectProcesses {
    Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -eq "python.exe" -and ($_.CommandLine -like "*uvicorn*app.main:app*" -or $_.CommandLine -like "*$WorkerDir*")) -or
        ($_.Name -eq "node.exe" -and $_.CommandLine -like "*$WebDir*vite*")
    }
}

function Stop-ProjectProcesses {
    $targets = Get-ProjectProcesses
    foreach ($target in $targets) {
        try {
            Stop-Process -Id $target.ProcessId -Force -ErrorAction Stop
        } catch {
        }
    }
}

function Show-ProjectStatus {
    $targets = Get-ProjectProcesses | Select-Object ProcessId, Name, CommandLine
    if (-not $targets) {
        Write-Host "Detection AI dev stack is not running."
        return
    }

    Write-Host "Detection AI dev stack is running:"
    $targets | Format-Table -AutoSize
    Write-Host ""
    Write-Host "API:  http://127.0.0.1:8000"
    Write-Host "Web:  http://127.0.0.1:5173"
    Write-Host "Logs: $ApiErr | $WebErr | $WorkerErr"
}

function Start-ProjectProcesses {
    Stop-ProjectProcesses

    Start-Process -FilePath (Join-Path $ApiDir ".venv\Scripts\python.exe") `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $ApiDir `
        -RedirectStandardOutput $ApiLog `
        -RedirectStandardError $ApiErr | Out-Null

    Start-Process -FilePath "npm.cmd" `
        -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173" `
        -WorkingDirectory $WebDir `
        -RedirectStandardOutput $WebLog `
        -RedirectStandardError $WebErr | Out-Null

    Start-Process -FilePath (Join-Path $WorkerDir ".venv\Scripts\python.exe") `
        -ArgumentList "-m", "app.main" `
        -WorkingDirectory $WorkerDir `
        -RedirectStandardOutput $WorkerLog `
        -RedirectStandardError $WorkerErr | Out-Null

    Start-Sleep -Seconds 4
    Show-ProjectStatus
}

function Invoke-Verification {
    Push-Location $Root
    try {
        & (Join-Path $ApiDir ".venv\Scripts\python.exe") -m compileall apps\api\app apps\worker\app

        Push-Location $ApiDir
        try {
            & ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
        } finally {
            Pop-Location
        }

        Push-Location $WorkerDir
        try {
            & ".\.venv\Scripts\python.exe" -m unittest discover -s tests -v
        } finally {
            Pop-Location
        }

        Push-Location $WebDir
        try {
            npm run lint
            npm run build
        } finally {
            Pop-Location
        }
    } finally {
        Pop-Location
    }
}

switch ($Action) {
    "start" { Start-ProjectProcesses }
    "stop" {
        Stop-ProjectProcesses
        Write-Host "Detection AI dev stack stopped."
    }
    "status" { Show-ProjectStatus }
    "verify" { Invoke-Verification }
}
