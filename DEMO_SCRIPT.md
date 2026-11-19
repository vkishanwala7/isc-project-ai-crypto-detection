# VERIFRAME — evaluator demo script (4–6 minutes)

**Before the session:** `bash scripts/start.sh` (or the two manual commands), open http://localhost:5173, confirm the header says **All systems ready**. Run `python scripts/fetch_demo_samples.py` once so the Demo workspace samples show **Analyze**. Have one ordinary photo of your own (any JPEG) ready on the desktop. Chrome or Edge on `localhost` gives camera access.

Numbers quoted below are what this build produced on 17 Nov 2026; re-runs give the same model scores.

---

### 1. Overview — the two layers (≈40 s)
**Click:** Overview.
**Say:** "VERIFRAME answers two different questions and never merges them into one number. Cyan is the AI signal: does a face look like the manipulated examples our model learned from? Violet is cryptographic provenance: do these exact bytes match a signed C2PA claim, and do we trust the signer?"
**Point at:** the counters (all computed from the database — they started at zero, nothing is seeded) and the evidence matrix: "This is the public rule we use to combine them. There is no hidden truth score."

### 2. AI analysis: a real face vs an AI-generated face (≈75 s)
**Click:** Analyze media → **Use camera** → **Start camera** → **Capture photo & analyze**, with a team member in front of the webcam.
**Observe:** *Low manipulation signal*, score close to 0 (a held-out team member scored about 0.01–0.02 in testing).
**Then:** switch to **From my computer** and upload a face saved from thispersondoesnotexist.com just before the demo (or use the Demo-workspace *StyleGAN face* sample).
**Observe:** *Manipulation signal detected*, score >0.99. Optionally also run *DeepFaceLab face-swap frame* or the *Avatarify deepfake clip*.
**Say:** "The model was trained in two stages: first on the SAFL dataset of real and manipulated faces and videos, then on webcam clips of three of us, so ordinary camera faces are not mistaken for fakes. The fourth member was kept out of training as a test, and none of his 81 frames were flagged. Fully generated faces like StyleGAN were caught 100% of the time on held-out data."
**Optional:** Model & dataset page: ROC-AUC 0.934, the unseen-person panel, and the robustness table. Say: "Subtle edits like FaceApp are harder, at 72%, which is why AI is only one of our two checks."

### 3. No provenance ≠ fake (≈30 s)
**Click:** Analyze media → drop your own photo → **Run analysis**.
**Observe:** Provenance panel: **No provenance found**, *"This says nothing by itself about whether the content is real or manipulated."* If the photo has no face: AI *Inconclusive / No face detected*, no score.
**Say:** "Most genuine photos online carry no Content Credentials, and screenshots or re-encoding strip them. So absence is neutral. We never call something fake because it lacks a manifest."

### 4. Capture & sign (≈45 s)
**Click:** Capture & sign → **Start camera** → allow → **Capture still & sign**.
**Observe:** *Signed and re-verified*, **Valid provenance**, chip *C2PA Content Credential embedded*, two SHA-256 values (captured bytes vs signed file), signer *VERIFRAME Demo Signer*, ES256, share reference `VF-…`.
**Say:** "The browser sent the exact JPEG bytes; the server embedded a C2PA manifest with a `c2pa.created` / `digitalCapture` action and signed it with ECDSA P-256. Then it re-opened the file through the verifier — the green status comes from that independent check. Note the banner: we signed *after* browser capture. A browser can't prove which camera took the photo, so we claim no hardware attestation."
**Click:** **Signed file (C2PA embedded)** and **Detached envelope (.json)** to download both.
*(No camera? Use "Or upload & sign" — the credential then records `c2pa.opened` instead.)*

### 5. Independent verification (≈40 s)
**Click:** Verify a file → drop the downloaded signed JPEG; optionally drop the `.veriframe-sig.json` as detached credential → **Verify provenance**.
**Observe:** steps — manifest discovery ✓, content binding ✓, claim signature ✓, signer trust ✓ (*local demo policy*); detached Ed25519 envelope ✓ labelled *not a C2PA Content Credential*; pHash similarity finds the original case (distance 0, identical bytes).
**Say:** "Signature validity and signer trust are separate. Our demo root CA is trusted only by this verifier's local policy; it is not on the official C2PA trust list."
**Optional:** verify the Demo-workspace file `data/samples/files/C.jpg` (or analyse the *Third-party C2PA-signed* sample): **Valid, signer not trusted** — a real credential from the C2PA test signer.

### 6. Integrity lab — real tamper detection (≈60 s)
**Click:** Integrity lab → **Run with demo image**.
**Observe:**
* *Signed original* → **Valid provenance**.
* *Byte-level tamper* → **Tampered or invalid**: one JPEG quantisation byte changed; SHA-256 differs in red, ≈130/256 digest bits flipped; C2PA reports `assertion.dataHash.mismatch`; pHash distance **0/64**.
* *Visual edit + re-encode* → C2PA **No provenance found** (manifest stripped), detached envelope **Tampered or invalid**.
**Say:** "One byte changed, the image looks identical, pHash says 'near-identical' — but the hash in the signed claim no longer matches, so verification fails. That's the difference between perceptual similarity and cryptographic integrity. The second copy shows signature stripping: the embedded credential is gone, which is why 'no provenance' must be reported neutrally, and why a detached signature still catches it."

### 7. Audit log and report (≈30 s)
**Click:** Activity log → expand a *Tamper test* row (technical details). Then Cases → open any case → **JSON report** and **Print / PDF**.
**Say:** "Every upload, analysis, signature, verification and error is persisted. Reports carry the immutable case ID, digests, both dimensions and the interpretation rule."

---

## Key concepts to explain if asked
* **SHA-256:** deterministic 256-bit digest; any change → completely different digest (avalanche); collision-resistant.
* **Digital signature:** proves the holder of the private key signed *this exact claim*. Trust in *who* that is comes from certificates and the verifier's trust anchors.
* **C2PA hard binding:** the signed claim contains a hash of the asset bytes (excluding the manifest). Change bytes → mismatch.
* **pHash:** 64-bit perceptual fingerprint of how an image looks; good for near-duplicate search, useless for integrity.
* **Calibration and threshold:** temperature scaling and the Youden-J threshold were fitted on validation data only; test data was used once.

## Likely evaluator questions — accurate answers

**Q: Is the AI result a probability that the image is fake?**
No. It is a temperature-scaled model output, calibrated on our validation split (ECE ≈ 0.02 on test). It estimates how much a face resembles the manipulated training examples. It is not a probability that the event is true or false.

**Q: How accurate is the model?**
On a held-out split of 1,246 face crops (images plus 63 whole videos): ROC-AUC 0.934 and accuracy 86.9 %. StyleGAN faces were caught 100 % of the time and FaceApp edits 72 %. A team member who was never in training had 0 of 81 webcam frames flagged. Our first version scored 96 % on an image-only test, but it flagged ordinary webcam faces, so we retrained it on video and webcam data. These are single-split numbers, not a benchmark.

**Q: Which dataset, and why not FaceForensics++?**
SAFL (CC BY 4.0, public GitHub). FaceForensics++, Celeb-DF and DFDC need approval forms or AWS credentials that we did not bypass; Hugging Face/Kaggle/Zenodo were also unreachable from the build environment. Comparison table in `docs/DATASET_RESEARCH.md`.

**Q: Did you train it or download it?**
Trained in this project from ImageNet weights, on CPU, in two stages (about 48 + 18 minutes). No pretrained deepfake detector was used.

**Q: Isn't training on your own faces cheating?**
We kept one member completely out of training and tested on him, and we report that separately. The webcam data teaches the model what ordinary camera faces look like. An unfamiliar face, room or camera can still be flagged, and we say so.

**Q: Is this real C2PA?**
Yes — the official `c2pa-python` 0.39.0 SDK (native c2pa-rs 0.92). The manifests can be inspected with other C2PA tools; they will show our signer as untrusted because our demo CA is not on the C2PA trust list.

**Q: Why is your own signer shown as trusted?**
Because VERIFRAME's verifier is configured with our local demo root as its only trust anchor. Trust is a policy decision; we show it separately from mathematical validity.

**Q: What stops someone stealing your key and signing fakes?**
In this demo, only file permissions (0600, git-ignored, never in the API or browser). A stolen key would let an attacker produce "trusted" credentials under our policy — production systems use HSMs/KMS, revocation and public trust lists. See `docs/THREAT_MODEL.md`.

**Q: If a credential is valid, is the image real?**
No. It proves the bytes are unchanged since the signer signed them and who signed. A trusted signer can still sign misleading content, and a deepfake can be signed. That's why the AI result is shown separately — the matrix cell "Signed origin, but AI flags it — inspect edits" exists for this.

**Q: Why did the re-encoded copy show "no provenance" instead of "tampered"?**
Re-encoding creates a new file without the embedded manifest. Without the original credential, a stripped file is indistinguishable from never-signed media. With the detached envelope supplied, VERIFRAME detects the digest mismatch.

**Q: Timestamps?**
No RFC 3161 timestamp authority (offline demo); the signing time is asserted by the signer and labelled as such.

**Q: Is the camera capture tamper-proof?**
No. The browser captures, then our server signs. We state "Signed by this VERIFRAME demo service after browser capture" and assert no hardware attestation.
