# VERIFRAME — *Know what you're looking at.*

**AI-powered media integrity and cryptographic provenance verification.**
Information Security & Cryptography (ISC) project — **Team 16**: Alakh Bathani (U24AI102), Krishna Baheti (U24AI133), Divam Shah (U24AI076), Vivaan Kishanwala (U24AI114).

VERIFRAME keeps two independent kinds of evidence side by side and never blends them into a single "truth score":

| Dimension | What it answers | What it does **not** prove |
|---|---|---|
| **AI manipulation signal** (cyan) | Does a face look like the manipulated examples the model learned from? | That the event is true/false; detection of every future deepfake |
| **Cryptographic provenance** (violet) | Do these exact bytes match a signed C2PA claim, and is the signer trusted by this verifier's policy? | That the scene is factual. **Missing provenance does not mean fake.** |

Everything is real: a model trained in this project runs locally, C2PA credentials are created and validated with the official `c2pa-python` SDK, and every tamper failure in the UI comes from an actual verification call.

> Local academic demonstration — not a production forensic certification platform. Results are forensic indicators, not a guarantee of truth.

---

## What works

| Route | Feature |
|---|---|
| `/dashboard` | Live backend health, statistics computed from stored records, 14-day activity chart (empty state until real activity), recent cases, the public evidence matrix |
| `/analyze` | Choose an image/video from your computer **or capture a live camera photo/clip**, with client + server validation, preview, AI analysis (per-face / per-frame scores, threshold, model version) and independent provenance inspection; **Demo workspace** with held-out dataset samples |
| `/capture` | Browser camera (`getUserMedia`) still capture or short clip (`MediaRecorder`), immediately signed (embedded C2PA, `c2pa.created` + `digitalCapture`) and re-verified; upload-and-sign fallback (`c2pa.opened`); downloads |
| `/verify` | Independent verification with step-by-step results (manifest discovery, binding, signature, trust), optional detached credential (`.veriframe-sig.json` or `.c2pa` sidecar), verify by share reference, pHash similarity (heuristic) |
| `/cases`, `/cases/:id` | Durable evidence reports: media, metadata, both dimensions, trust interpretation, timeline, stored files, **JSON export**, print stylesheet (Print → Save as PDF), re-verify, delete with confirmation |
| `/integrity-lab` | Sign → verify → 1-byte tamper → verify → visual edit/re-encode → verify; SHA-256 diff highlighting, flipped-bit count, pHash comparison |
| `/model-lab` | Checkpoint, SHA-256, preprocessing, threshold, calibration, training curve, held-out test metrics, confusion matrix, per-source accuracy, limitations |
| `/activity` | Persisted audit log with filters and expandable technical details |
| `/about` | Architecture, AI, SHA-256, signatures, C2PA, trust model, pHash limits, evidence rules, threat model, references, team |

## Quick start

Prerequisites: **Python 3.10+** (tested 3.13), **Node.js 20+** (tested 22), ~3 GB disk for PyTorch.

```bash
# Linux / macOS
bash scripts/setup.sh        # venv, Python deps, demo keys, demo samples, npm install
bash scripts/start.sh        # backend :8000 + frontend :5173
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

Manual equivalent:

```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
pip install -r backend/requirements.txt
pip install --no-deps facenet-pytorch==2.6.0               # MTCNN weights are inside this wheel
python backend/scripts/generate_demo_keys.py               # optional: keys are also created on first start
python scripts/fetch_demo_samples.py                       # optional: demo workspace samples
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000     # terminal 1
cd frontend && npm install && npm run dev                           # terminal 2
```

| URL | |
|---|---|
| http://localhost:5173 | Web app |
| http://127.0.0.1:8000/docs | OpenAPI / Swagger UI |
| http://127.0.0.1:8000/api/health | Subsystem readiness |

Configuration is optional: copy `.env.example` to `.env` (paths, upload limits, video sampling, CORS origins, extra C2PA trust anchors).

## AI model

* **Loaded checkpoint:** `model_weights/veriframe_effb0_safl.pt`, VERIFRAME-EffB0-SAFL **v2.1.0**: an EfficientNet-B0 **trained by this project** on CPU, in two stages.
  * **Stage 1:** SAFL images plus face frames from all 416 SAFL videos.
  * **Stage 2:** webcam clips of three team members; a fourth was held out for testing.
* **Held-out SAFL test split** (1,246 crops, 63 whole videos): ROC-AUC 0.934, accuracy 86.9%, whole-video accuracy 84.1%, StyleGAN (thispersondoesnotexist) faces 100% caught.
* **Unseen team member on the demo webcam:** 0 of 81 frames flagged.
* Details, version history (v1.0 → v2.0 → v2.1) and limitations: `docs/AI_MODEL_CARD.md`.
* No face → `INCONCLUSIVE / NO_FACE_DETECTED`, no score. Missing weights → "Model weights unavailable", no score.
* The Analyze page accepts a file from your computer **or a live camera photo/clip**.

## Provenance

* **Genuine C2PA** (primary): embedded Content Credentials for JPEG, PNG, WebP, MP4, MOV via `c2pa-python 0.39.0`; ES256 demo signer chained to a locally generated demo root CA.
* **Detached Ed25519 envelope** (supplementary, labelled *"VERIFRAME detached-signature demo — not a C2PA Content Credential"*).
* **Signer trust:** the demo root is trusted only by VERIFRAME's local policy. It is not on the official C2PA trust list; third-party credentials show as *valid but untrusted* unless you add anchors via `VERIFRAME_EXTRA_TRUST_ANCHORS`. No RFC 3161 timestamps (offline).

## Tests

```bash
cd backend && python -m pytest -q       # crypto, AI and API end-to-end tests
cd frontend && npm run typecheck && npm test && npm run build
```

## Documentation

`docs/ARCHITECTURE.md` · `docs/CRYPTOGRAPHY.md` · `docs/AI_MODEL_CARD.md` · `docs/DATASET_RESEARCH.md` · `docs/DATASET_CARD.md` · `docs/THREAT_MODEL.md` · `DEMO_SCRIPT.md` · `PROJECT_STATUS.md`

## Security caveats

* Private keys live in `keys/` (git-ignored, 0600). Never commit them; rotate with `python backend/scripts/generate_demo_keys.py --rotate`.
* Single-user local demo: no authentication, no rate limiting, binds to 127.0.0.1. Do not expose it to a network as-is.
* Uploaded files are stored in `data/storage/` until you delete the case. Nothing is sent to third-party services.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Header shows "Backend offline" | Start the API on port 8000 (`cd backend && uvicorn app.main:app --port 8000`). The Vite proxy expects `127.0.0.1:8000` (override with `VITE_API_TARGET`). |
| `ai_model` not ready in health | `model_weights/veriframe_effb0_safl.pt` missing — copy it from the project archive or retrain. The app still runs and reports "Model weights unavailable". |
| `ModuleNotFoundError: facenet_pytorch` | `pip install --no-deps facenet-pytorch==2.6.0` |
| Camera does not start | Browsers allow `getUserMedia` only on `localhost`/HTTPS and after permission; use the upload fallback otherwise. |
| Clip recorded as WebM | That browser lacks MP4 `MediaRecorder` support; the clip gets the detached envelope only (stated in the result). |
| Demo samples show "Not fetched" | `python scripts/fetch_demo_samples.py` (needs GitHub access). |

## Demo flow (4–6 min)

See `DEMO_SCRIPT.md`. Short version: Dashboard → Analyze a labelled sample → upload a file without provenance (*no provenance ≠ fake*) → Capture & sign → Verify the signed file → Integrity lab tamper → Activity log → evidence report export.

## Licences and attribution

Code: written for this academic project. Dataset: SAFL (Falcón-López, CC BY 4.0; underlying CelebA/Celeb-DF terms apply — non-commercial research). Model init: timm EfficientNet-B0 ImageNet weights (Apache-2.0). Face detector: facenet-pytorch MTCNN (MIT). C2PA: c2pa-python (MIT/Apache-2.0). Dataset media are not redistributed; `scripts/fetch_demo_samples.py` downloads samples from their official sources.
