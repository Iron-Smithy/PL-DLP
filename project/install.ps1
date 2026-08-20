Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "    pl-dlp Windows Installer Launcher    " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check Python Availability
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonCmd) {
    Write-Host "[!] Python was not detected on your system." -ForegroundColor Red
    $choice = Read-Host "Would you like to install Python via winget now? (Y/N)"
    
    if ($choice -match '^[Yy]$') {
        Write-Host "Installing Python via Windows Package Manager..." -ForegroundColor Yellow
        winget install --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements
        
        # Refresh environment variables after winget install
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    }
}

if (-not $pythonCmd) {
    Write-Host "[ERROR] Python installation missing. Please install Python 3.10+ manually and re-run this installer." -ForegroundColor Red
    Pause
    Exit
}

# Run Setup Logic
python "$PSScriptRoot\setup.py"
Pause