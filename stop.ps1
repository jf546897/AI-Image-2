$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Port = if ($env:AI_IMAGE_PORT) { [int]$env:AI_IMAGE_PORT } else { 8012 }
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if (-not $connections) {
    Write-Host "AI Image 2 is not running on port $Port."
    exit 0
}

foreach ($connection in $connections) {
    $targetProcessId = $connection.OwningProcess
    $process = Get-Process -Id $targetProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "Stopping PID=$targetProcessId ($($process.ProcessName)) ..."
        Stop-Process -Id $targetProcessId -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'AI Image 2 stop command completed.'
