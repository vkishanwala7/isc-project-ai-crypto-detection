# Start backend (new window, port 8000) and frontend (this window, port 5173).
Set-Location (Split-Path $PSScriptRoot -Parent)
$root = Get-Location
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root'; .\.venv\Scripts\Activate.ps1; cd backend; uvicorn app.main:app --host 127.0.0.1 --port 8000"
Set-Location frontend
npm run dev
