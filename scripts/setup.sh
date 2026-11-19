#!/usr/bin/env bash
# One-time setup (Linux/macOS). Run from the repository root:  bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# CPU-only PyTorch keeps the download small; remove --index-url to use the default build.
pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu || pip install torch==2.15.0 torchvision==0.29.2
pip install -r backend/requirements.txt
pip install --no-deps facenet-pytorch==2.6.0   # MTCNN weights ship inside this wheel
python backend/scripts/generate_demo_keys.py
python scripts/fetch_demo_samples.py || echo "Sample download failed; the demo workspace will show 'Not fetched'."
(cd frontend && npm install)
echo "Setup complete. Start with: bash scripts/start.sh"
