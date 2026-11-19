# One-time setup (Windows PowerShell). Run from the repository root:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { pip install torch==2.15.0 torchvision==0.29.2 }
pip install -r backend\requirements.txt
pip install --no-deps facenet-pytorch==2.6.0
python backend\scripts\generate_demo_keys.py
python scripts\fetch_demo_samples.py
Push-Location frontend; npm install; Pop-Location
Write-Host "Setup complete. Start with: powershell -File scripts\start.ps1"
