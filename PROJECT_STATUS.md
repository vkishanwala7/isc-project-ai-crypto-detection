# PROJECT_STATUS — VERIFRAME

_Last updated: 18 Nov 2026 (model v2.1, camera analysis added)._

## Completed and verified
| Area | State | Evidence |
|---|---|---|
| Backend API (FastAPI) | All routes from the brief plus `/api/config`, `/api/keys/public`, `/api/provenance/verify-ref/{ref}`, `/api/samples`, `DELETE /api/cases/{id}`, `/api/files/{id}` | OpenAPI at `/docs`; `tests/test_api.py` |
| Persistence | SQLite: cases, assets, analyses, provenance_records, audit_events; UUID case ids; generated storage names | `tests/test_api.py` |
| C2PA (genuine) | Embedded sign + verify for JPEG/PNG/WebP/MP4/MOV with `c2pa-python 0.39.0`; CREATE/digitalCapture for captures, EDIT/parentOf for uploads; trust separate from validity; third-party credential verified as untrusted | `tests/test_crypto.py` |
| Ed25519 envelope | Detached, canonical-JSON claim, labelled "not a C2PA Content Credential" | `tests/test_crypto.py` |
| Integrity lab | Real 1-byte tamper (JPEG DQT / PNG IDAT) and visual edit + re-encode; all four expectations met | `test_integrity_lab_real_failures`, browser run |
| AI model | v2.1: EfficientNet-B0 trained here on SAFL images + video frames, then fine-tuned on team webcam clips (person-disjoint). Test ROC-AUC 0.934, acc 86.9 %; held-out team member 0/81 frames flagged; StyleGAN 100 % | `model_weights/metrics.json`, `team_holdout.json`, `robustness.json`, `docs/AI_MODEL_CARD.md` |
| Image + video inference | Faces → crops → calibrated score; ≤16 sampled frames for video; NO_FACE → inconclusive; missing weights → explicit unavailable | `tests/test_ai.py` |
| Camera analysis | Analyze page: "From my computer" or "Use camera" (photo or ≤10 s clip, analysed immediately) | Playwright with a fake camera fed by held-out member B: photo 0.016, clip 0.011 (low signal) |
| Frontend | 9 required routes + `/cases` list + 404; responsive (verified at 390 px and 1440 px, no horizontal overflow); toasts, skeletons, empty and error states, confirm dialog, print stylesheet, reduced motion | Playwright run in Chrome |
| Docs | README, ARCHITECTURE, CRYPTOGRAPHY, AI_MODEL_CARD, DATASET_RESEARCH, DATASET_CARD, THREAT_MODEL, DEMO_SCRIPT, this file | `docs/` |

## Commands run and results (this session)
* `cd backend && python -m pytest -q` → **41 passed**
* `cd frontend && npx tsc -b --noEmit` → no errors; `npx vitest run` → **6 passed**; `npm run build` → success
* `python backend/scripts/prepare_dataset.py` → 4,472 crops (240 s); `python backend/scripts/train_model.py --epochs 5` → 24 min CPU; `python backend/scripts/robustness_eval.py` → done
* `python scripts/fetch_demo_samples.py` → 9/9 samples fetched, SHA-256 verified
* Browser E2E (Playwright + Chrome, fake camera): sample analysis, video analysis, camera capture & sign, downloads, verification with envelope, third-party C2PA verification, integrity lab, case report, activity log, dashboard — all succeeded with **no console errors**.

## Known limitations
* Model: real faces in training are celebrities plus three team members on one webcam; unfamiliar real faces can still be flagged. CelebA-style real photos became slightly more likely to be flagged in v2.1 (specificity 90 %). FaceApp edits caught only 72 %. The real Celeb-DF demo video now scores 0.65 (still flagged, down from 0.998 in v1).
* Signer: local demo CA, not on the C2PA trust list; no RFC 3161 timestamps; no revocation.
* WebM recordings (browsers without MP4 MediaRecorder) receive only the detached envelope.
* PDF export is via the browser print dialog (print stylesheet), not server-side PDF generation.
* No authentication/rate limiting — local single-user demo only.
* The full `setup.sh`/`setup.ps1` install path was written from the commands verified here, but a fresh-machine install (especially on Windows) was not executed in this session.

## Exact next steps (if continuing)
1. Run `scripts/setup.ps1` on a team member's Windows machine and fix any path issues.
2. Add the official C2PA trust anchors via `VERIFRAME_EXTRA_TRUST_ANCHORS` to show real-world trust evaluation.
3. If approval for FaceForensics++ (c23) or Celeb-DF v2 is obtained, write a manifest for it and retrain/evaluate cross-dataset; add blur/low-resolution augmentation to reduce false positives.
4. Optional: server-side PDF report generation; an RFC 3161 TSA when online.
