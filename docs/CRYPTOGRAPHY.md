# Cryptography & provenance in VERIFRAME

This document explains every cryptographic mechanism the software actually uses, where it lives in the code, and what each one does **not** prove.

## 1. Two provenance implementations (both active)

| | **C2PA Content Credentials** (primary) | **Detached Ed25519 envelope** (supplementary, educational) |
|---|---|---|
| Code | `backend/app/services/provenance/c2pa_adapter.py` | `backend/app/services/provenance/ed25519_envelope.py` |
| Library | Official CAI bindings `c2pa-python 0.39.0` (native c2pa-rs 0.92.0) | `cryptography` (Ed25519) |
| Storage | Embedded in the file (JUMBF: JPEG APP11, PNG `caBX`, BMFF box for MP4/MOV, RIFF chunk for WebP) | Separate JSON file `*.veriframe-sig.json` |
| Signature | COSE_Sign1, **ES256** (ECDSA P-256 + SHA-256), X.509 chain | Ed25519 (RFC 8032) over canonical JSON |
| Binding | C2PA hard binding: SHA-256 over the asset bytes excluding the manifest (`c2pa.hash.data`, or `c2pa.hash.bmff` for video) | SHA-256 of the **entire** file in the signed claim |
| UI label | "C2PA Content Credentials" | "VERIFRAME detached-signature demo — not a C2PA Content Credential." |

Why both? C2PA is the real standard and is what the project relies on. The envelope makes the underlying idea (hash → sign → verify) visible in ~100 lines, survives re-encoding as a separate file (so it still *detects* a re-encoded copy after the embedded manifest has been stripped), and gives a provenance path for WebM recordings, which the installed C2PA SDK cannot embed into.

## 2. SHA-256

* `app/services/media/hashing.py::sha256_hex` computes SHA-256 over the exact uploaded bytes for every asset.
* Properties relied on: determinism, pre-image and collision resistance, avalanche (a 1-byte change flips ≈128 of 256 output bits; the Integrity Lab displays the exact count).
* A digest alone proves nothing about who produced a file. It is meaningful only when compared with a digest that is itself protected — by a signature.

## 3. Digital signatures and certificates

### Keys (`app/services/provenance/keys.py`)
Generated on first start (or with `python backend/scripts/generate_demo_keys.py [--rotate]`) into `keys/` (git-ignored, directory 0700, private keys 0600):

| File | Content |
|---|---|
| `demo_root_ca.pem` / `.key` | "VERIFRAME Local Demo Root CA", ECDSA P-256, self-signed, `CA:TRUE, pathlen:0`, keyCertSign/cRLSign |
| `demo_signer_chain.pem` / `demo_signer.key` | "VERIFRAME Demo Signer" end-entity cert issued by the demo root: `CA:FALSE`, digitalSignature, EKU emailProtection (accepted by C2PA's certificate profile), 1-year validity |
| `ed25519_private.pem` / `ed25519_public.pem` | Ed25519 key pair; key id = `vf-ed25519-` + first 16 hex chars of SHA-256(public key) |

Private keys are loaded only in the backend process. They are never returned by the API, written to the database, logged, or shipped to the browser (`tests/test_crypto.py::test_private_keys_never_in_public_material`). `GET /api/keys/public` exposes only certificates and the Ed25519 public key.

### Signing workflow (`app/services/workflows.py::sign`)
1. Preserve the exact received bytes (stored unchanged as the `original` asset).
2. SHA-256 of those bytes.
3. Build a C2PA manifest with the SDK's **Builder intents** (so the manifest is spec-compliant):
   * **Browser capture** → intent `CREATE` + IPTC digital source type `digitalCapture` (SDK emits `c2pa.created`).
   * **Upload** → intent `EDIT`: the SDK records the received bytes as the `parentOf` ingredient and emits `c2pa.opened` linked to it. No claim about original creation is made.
   * A vendor assertion `org.veriframe.signing-context` states truthfully: demo service, workflow, time, `hardware_attestation: false`, and that the signer is a local demo CA.
4. Sign with ES256 via `c2pa.Signer.from_info` and embed the manifest store.
5. Create the detached Ed25519 envelope over the **signed** file's SHA-256.
6. **Re-open the signed bytes through the verifier** (`verify_media`) — the stored status comes from this independent check, not from the signing call's return value.
7. Offer downloads: signed file (credential embedded) and envelope JSON.

No RFC 3161 timestamp authority is used (the demo must work offline). Signing times are therefore signer-asserted; the UI says so.

## 4. Verification (`c2pa_adapter.verify`, `ed25519_envelope.verify_envelope`, `service.verify_media`)

The C2PA reader is run with a trust configuration containing only the demo root (plus `VERIFRAME_EXTRA_TRUST_ANCHORS` if set). The SDK's validation codes are mapped:

| SDK result | VERIFRAME status |
|---|---|
| `ManifestNotFound` | `NO_PROVENANCE_FOUND` — *says nothing about real vs fake* |
| any failure other than `signingCredential.untrusted` (e.g. `assertion.dataHash.mismatch`, `assertion.bmffHash.mismatch`, `claimSignature.mismatch`) | `TAMPERED_OR_INVALID` |
| only `signingCredential.untrusted` | `VALID_BUT_UNTRUSTED_SIGNER` |
| `signingCredential.trusted`, no failures | `VALID_PROVENANCE` (trusted **under the local demo policy**) |
| parse error / unsupported format | `TAMPERED_OR_INVALID` if a manifest structure was present but broken, else `UNSUPPORTED_OR_UNREADABLE` |

Signature validity (`claimSignature.validated`), content-binding validity and signer trust are returned as **three separate fields** and shown separately in the UI. Example: a byte-tampered file typically has a *valid* claim signature but a *failed* binding — the signature is fine, it just no longer describes these bytes.

The envelope verifier independently checks (a) Ed25519 signature over `canonical_json(claim)` — sorted keys, compact separators, UTF-8 — and (b) `SHA-256(file) == claim.asset.sha256`, and (c) trust by pinning the service's own public key. A third-party re-signed envelope verifies as `VALID_BUT_UNTRUSTED_SIGNER` (tested).

When both are present, the headline status is the most severe (`TAMPERED_OR_INVALID` > valid > no provenance).

Verified behaviour of a real third-party credential: the c2pa-python fixture `C.jpg` (signed by the C2PA test signing certificate) verifies as `VALID_BUT_UNTRUSTED_SIGNER` — available as a Demo Workspace sample.

## 5. Trust model

* The demo root CA is **not** on the official C2PA trust list and is not a recognised camera or organisation identity. "Trusted" in VERIFRAME means "chains to the anchor this verifier was configured with".
* To evaluate real-world Content Credentials, download the official C2PA trust anchors PEM and point `VERIFRAME_EXTRA_TRUST_ANCHORS` at it.
* A trusted signer can still sign misleading media; a stolen demo key would let an attacker produce "trusted" credentials (see `THREAT_MODEL.md`). Rotation: `generate_demo_keys.py --rotate`.

## 6. pHash — similarity, not integrity

`imagehash.phash` (64-bit DCT hash) is computed for images and for the middle frame of videos. VERIFRAME uses it only to (a) show the nearest previously stored asset ("visual similarity estimate") and (b) contrast with SHA-256 in the Integrity Lab. It never contributes to a provenance status (`test_phash_is_not_integrity_decision`). It is not collision-resistant and can be adversarially manipulated.

## 7. Integrity Lab — the tamper demonstration (`workflows.integrity_lab`, `provenance/tamper.py`)

1. Source: the user's JPEG/PNG or an app-generated demo image (no people). Stored unchanged.
2. Sign → embedded C2PA + Ed25519 envelope over the signed bytes.
3. Verify the clean signed copy → expected `VALID_PROVENANCE`.
4. **Byte-level tamper** on a copy: JPEG — increment one quantisation-table coefficient (1 byte; file stays decodable, change nearly invisible, manifest bytes untouched); PNG — change one decompressed pixel byte inside IDAT, recompress, recompute the chunk CRC. Verify → C2PA `assertion.dataHash.mismatch` → `TAMPERED_OR_INVALID`; envelope digest mismatch.
5. **Visual edit + re-encode** on a copy: brighten a small patch, re-save as JPEG. The embedded manifest disappears (signature stripping) → C2PA reports `NO_PROVENANCE_FOUND`; the detached envelope reports `TAMPERED_OR_INVALID`.
6. Report SHA-256 before/after (with differing hex characters highlighted and the number of flipped bits) and pHash distances (typically 0–4 of 64: "visually near-identical").

Every result is produced by a real verification call; the frontend only renders what the API returns. Automated equivalents: `tests/test_api.py::test_integrity_lab_real_failures`, `tests/test_crypto.py::test_c2pa_tampered_bytes_fail_binding`, `test_png_tamper_detected`, `test_mp4_sign_verify_tamper`.
