$Folder = $PSScriptRoot
$Python = Join-Path $Folder "venv\Scripts\pythonw.exe"

if (-not (Test-Path $Python)) {
    Write-Host "Griffin virtual environment not found."
    Write-Host "Create it first using:"
    Write-Host "python -m venv venv"
    Write-Host "venv\Scripts\pip install -r requirements.txt"
    exit 1
}

Start-Process -FilePath $Python `
    -ArgumentList "griffin_bridge.py" `
    -WorkingDirectory $Folder

Start-Sleep -Seconds 2

Start-Process -FilePath $Python `
    -ArgumentList "griffin_app.py" `
    -WorkingDirectory $Folder
