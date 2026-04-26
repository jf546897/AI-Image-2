$ErrorActionPreference = 'Stop'

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

$HostName = if ($env:AI_IMAGE_HOST) { $env:AI_IMAGE_HOST } else { '127.0.0.1' }
$Port = if ($env:AI_IMAGE_PORT) { [int]$env:AI_IMAGE_PORT } else { 8012 }
$BrowseHost = if ($HostName -eq '0.0.0.0') { '127.0.0.1' } else { $HostName }
$TargetUrl = "http://${BrowseHost}:${Port}/"
$ConfigUrl = "http://${BrowseHost}:${Port}/api/config"
$LogPath = Join-Path $ProjectRoot 'ai-image2.log'
$ErrorLogPath = Join-Path $ProjectRoot 'ai-image2.err.log'
$VenvDir = Join-Path $ProjectRoot '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$RequirementsPath = Join-Path $ProjectRoot 'requirements.txt'
$BundledExe = Join-Path $ProjectRoot 'runtime\AI_Image2_Server.exe'

function Write-Step {
    param([string]$Message)
    Write-Host "[AI Image 2] $Message"
}

function Test-AppReady {
    try {
        $response = Invoke-WebRequest -Uri $ConfigUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Find-SystemPython {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @{ File = $python.Source; Args = @() } }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return @{ File = $py.Source; Args = @('-3') } }

    return $null
}

function Invoke-Python {
    param(
        [hashtable]$PythonCommand,
        [string[]]$Arguments
    )
    $allArgs = @()
    if ($PythonCommand.Args) { $allArgs += $PythonCommand.Args }
    $allArgs += $Arguments

    & $PythonCommand.File @allArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $($PythonCommand.File) $($allArgs -join ' ')"
    }
}

function Ensure-Venv {
    if (Test-Path $VenvPython) {
        Write-Step 'Local virtual environment found.'
        return
    }

    $systemPython = Find-SystemPython
    if (-not $systemPython) {
        throw 'Python was not found. Install Python 3.10+ and enable Add python.exe to PATH.'
    }

    Write-Step 'First run: creating local virtual environment .venv ...'
    Invoke-Python -PythonCommand $systemPython -Arguments @('-m', 'venv', $VenvDir)

    if (-not (Test-Path $VenvPython)) {
        throw 'Failed to create .venv. Please check your Python installation.'
    }
}

function Ensure-Dependencies {
    if (-not (Test-Path $RequirementsPath)) {
        throw 'requirements.txt is missing. This is not a complete AI-image2 folder.'
    }

    $stampPath = Join-Path $VenvDir '.deps-installed'
    $requirementsHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $RequirementsPath).Hash
    $currentStamp = if (Test-Path $stampPath) { Get-Content -Raw -LiteralPath $stampPath } else { '' }

    if ($currentStamp -eq $requirementsHash) {
        Write-Step 'Dependencies already installed.'
        return
    }

    Write-Step 'Installing dependencies. This may take a few minutes on first run...'
    & $VenvPython -m pip install --disable-pip-version-check -r $RequirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw 'Dependency installation failed. Check network access or run .venv\Scripts\python.exe -m pip install -r requirements.txt'
    }

    Set-Content -LiteralPath $stampPath -Value $requirementsHash -Encoding ASCII
}

Write-Step 'Starting portable AI Image 2...'
Write-Step "Project: $ProjectRoot"
Write-Step "URL: $TargetUrl"

if (-not (Test-Path (Join-Path $ProjectRoot 'app.py'))) {
    throw 'app.py was not found. Run this file from the AI-image2 folder.'
}

if (Test-AppReady) {
    Write-Step 'Service is already running. Opening page...'
    Start-Process $TargetUrl
    Start-Sleep -Seconds 2
    exit 0
}

$env:AI_IMAGE_HOST = $HostName
$env:AI_IMAGE_PORT = [string]$Port
$env:AI_IMAGE_PROJECT_ROOT = $ProjectRoot

if (Test-Path $LogPath) {
    Remove-Item -LiteralPath $LogPath -Force
}
if (Test-Path $ErrorLogPath) {
    Remove-Item -LiteralPath $ErrorLogPath -Force
}

if (Test-Path $BundledExe) {
    Write-Step 'Bundled runtime found. Python installation is not required.'
    $process = Start-Process -FilePath $BundledExe -WorkingDirectory $ProjectRoot -RedirectStandardOutput $LogPath -RedirectStandardError $ErrorLogPath -PassThru -WindowStyle Hidden
}
else {
    Write-Step 'Bundled runtime not found. Falling back to local Python + .venv.'
    Ensure-Venv
    Ensure-Dependencies
    $process = Start-Process -FilePath $VenvPython -ArgumentList @('app.py') -WorkingDirectory $ProjectRoot -RedirectStandardOutput $LogPath -RedirectStandardError $ErrorLogPath -PassThru -WindowStyle Hidden
}
Write-Step "Server process started. PID=$($process.Id)"

$ready = $false
for ($attempt = 1; $attempt -le 90; $attempt++) {
    if ($process.HasExited) {
        Write-Host 'Server process exited. Log:' -ForegroundColor Red
        if (Test-Path $LogPath) { Get-Content $LogPath }
        if (Test-Path $ErrorLogPath) { Get-Content $ErrorLogPath }
        exit 1
    }

    if (Test-AppReady) {
        $ready = $true
        break
    }

    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    Write-Host 'Server startup timed out. Log:' -ForegroundColor Yellow
    if (Test-Path $LogPath) { Get-Content $LogPath }
    if (Test-Path $ErrorLogPath) { Get-Content $ErrorLogPath }
    exit 1
}

Start-Process $TargetUrl
Write-Step 'AI Image 2 opened.'
Write-Step 'If this is a new PC, enter API URL Base and API Key in the page, then click Save.'
Write-Step 'Close this window does not stop the server. Use Stop_AI_Image2.bat to stop it.'
Start-Sleep -Seconds 3
exit 0
