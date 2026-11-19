# Threat model

Scope: VERIFRAME as delivered — a single-user local academic demonstration (FastAPI on 127.0.0.1, Vite dev server, SQLite, local keys). Not a hardened multi-tenant service.

## Assets
1. Signing private keys (demo C2PA signer, demo root CA, Ed25519).
2. Integrity of stored evidence (cases, assets, audit log).
3. Correctness and honesty of the reported results (the interpretation users take away).
4. Availability of the local service.
5. Uploaded media (may contain faces / personal data).

## Adversaries
* **A1 Malicious uploader** — crafts files to crash, exhaust or exploit the server or the viewer.
* **A2 Media forger** — wants manipulated media to be believed (evade the classifier, forge or transplant credentials, strip credentials).
* **A3 Key thief / compromised signer** — obtains a signing key.
* **A4 Local attacker** — has file-system access to the machine.
* **A5 Misinterpretation** — not malicious: an evaluator or user over-reads a result.

## Attack surfaces, mitigations, residual risk

| Threat | Mitigation in VERIFRAME | Residual risk |
|---|---|---|
| Malicious upload / polyglot / wrong extension (A1) | Format from magic bytes only; client MIME and extension ignored; only JPEG/PNG/WebP/MP4/MOV/WebM accepted; files stored under generated UUID names outside any static directory; served only via `/api/files/{asset_id}` after DB lookup with `X-Content-Type-Options: nosniff`, restrictive CSP and `Content-Disposition`; uploads never executed | Parser bugs in Pillow/OpenCV/FFmpeg/c2pa-rs remain possible; keep dependencies updated |
| Decompression bombs / resource exhaustion (A1) | Byte caps enforced while streaming the upload (15 MB image / 60 MB video); `Image.MAX_IMAGE_PIXELS` = 40 MP; video duration ≤ 120 s; ≤ 16 (hard cap 24) sampled frames; ≤ 4 faces per image; detection on images downscaled to 640 px | No rate limiting or auth (single-user local demo); concurrent large jobs could saturate the CPU |
| Path traversal / XSS via filenames or metadata (A1) | Display names sanitised (path components, control and markup characters removed); React escapes all text; asset IDs validated as 32-hex; storage path resolution checked | — |
| Metadata spoofing (A2) | Unsigned EXIF/XMP is never used as evidence; only signed C2PA assertions are shown, and labelled as signer-asserted | Signed assertions are only as truthful as the signer |
| File replacement / byte tampering (A2) | C2PA hard binding (`dataHash`/`bmffHash`) and envelope SHA-256 detect any change; Integrity Lab demonstrates it | — |
| Signature stripping (A2) | Re-encoded media shows `NO_PROVENANCE_FOUND`, which is reported neutrally (not as authentic); detached envelope still detects mismatch if supplied | Without the original credential, a stripped file is indistinguishable from never-signed media — inherent to provenance |
| Credential transplant (A2) — copying a manifest onto other content | Hard binding fails on different bytes → `TAMPERED_OR_INVALID` | — |
| Third-party / self-made credentials (A2) | Trust evaluated against configured anchors only; untrusted signers shown as `VALID_BUT_UNTRUSTED_SIGNER`, separately from validity | Users may still over-trust "valid" — mitigated by wording |
| Private-key theft (A3, A4) | Keys in git-ignored `keys/` (dir 0700, files 0600), never in DB, API, logs, frontend bundle (tested); rotation script | Anyone with the OS account can read the keys; no HSM/KMS. A stolen key can sign arbitrary "trusted" (under local policy) content |
| Compromised or careless signer (A3) | Demo signer explicitly labelled as non-public; signing context assertion states no hardware attestation | No revocation (OCSP/CRL) infrastructure for the demo CA |
| Database / evidence tampering (A4) | Assets re-verifiable at any time (`verify-ref`) because integrity is checked against signatures, not DB fields | SQLite and audit log are not append-only or signed; an A4 attacker can edit history |
| Classifier evasion, domain shift (A2) | Score labelled as model estimate; inconclusive band; no-face → no score; limitations in UI and model card | Adversarial perturbations, new generators and heavy compression can defeat the model |
| Misleading trust interpretation (A5) | Separate AI and provenance panels; public deterministic matrix, no truth score; "missing provenance ≠ fake" and "valid signature ≠ true event" stated everywhere; persistent disclaimer | Users can still misread; the demo script rehearses the correct explanations |
| Privacy of uploaded media (5) | All processing local; no third-party APIs; media not logged | Files persist in `data/storage/` until the case is deleted (retention: manual delete via UI or `DELETE /api/cases/{id}`) |
| CORS / CSRF from other sites | CORS allow-list limited to the local Vite origin; no cookies or credentials used | Any local process can call the API on 127.0.0.1 |

## Out of scope
Authentication, multi-user isolation, TLS, hardware-backed capture attestation, RFC 3161 timestamping, revocation checking, and audio deepfake detection.
