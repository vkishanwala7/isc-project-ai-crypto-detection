# Dataset research — VERIFRAME

**Research date:** 17 November 2026 · **Researcher:** build session for Team 16 · **Status:** complete; one dataset selected, acquired and used.

## 1. Constraints of the build environment (measured, not assumed)

| Item | Finding |
|---|---|
| Compute | 2 CPU cores, 7.8 GB RAM, **no GPU** |
| Disk | ~31 GB free |
| Network (egress allow-list) | `pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org`, GitHub over git and `raw.githubusercontent.com`/GitHub release downloads: **reachable**. `huggingface.co`, `kaggle.com`, `zenodo.org`, `download.pytorch.org`: **blocked (HTTP 403 from the proxy)** |
| Session budget | Training must fit in well under an hour on CPU |

These constraints rule out downloading multi-GB video benchmarks and anything hosted only on Hugging Face, Kaggle or Zenodo **from this environment**. They do not change the licence analysis, which is reported for every candidate.

## 2. Shortlist and comparison

Sources were checked on their official pages (links below) on the research date.

| Criterion | **SAFL** (selected) | FaceForensics++ | Celeb-DF v2 | DFDC (full / preview) | OpenForensics | DeepFakeFace (DFF) |
|---|---|---|---|---|---|---|
| Manipulation types | FaceApp edits, StyleGAN (thispersondoesnotexist), DeepFaceLab swaps, DALL·E 2/3; video: Avatarify, DeepFaceLab | Deepfakes, Face2Face, FaceSwap, NeuralTextures, FaceShifter | Improved DeepFake face swaps | 8 face-swap / reenactment methods (full) | GAN-based face forgery in multi-face scenes | Stable Diffusion text2img & inpainting, InsightFace swaps |
| Real samples included | Yes — 2,102 CelebA images, 212 Celeb-DF videos | Yes — 1,000 YouTube videos | Yes — 890 real videos | Yes — paid actors | Yes — real faces in same scenes | Yes — IMDB-WIKI images |
| Modality | Images **and** videos (+ audio) | Video | Video | Video | Images | Images |
| Size | Image subset ≈ 620 MB (4.5k files); whole repo larger | ~1.5 TB raw / tens of GB compressed | 6,229 videos | 124k videos (~470 GB); preview 5k | 115k images, 56.4 GB | 4 × 30k images, ~5 GB |
| Small educational subset | Yes — images folder alone, sparse checkout | Benchmark images only | No official one | Preview set (still large) | Per-zip, still GBs | Per-zip (~1.3 GB) |
| Access method | Public GitHub repo, no account | Google form → approval → download script | Google/Tencent form → link sent after approval | AWS account + IAM keys | Zenodo (open) | Hugging Face (open) |
| Automated download permitted | Yes (public repo) | Only after approval | Only after approval | With AWS credentials | Yes | Yes |
| Licence / terms | **CC BY 4.0**; users must respect CelebA / Celeb-DF original terms | Custom terms of use (non-commercial research) | "Terms to Use Celeb-DF" (form); no open licence | Dataset terms; cite paper | **CC BY 4.0** | Card states apache-2.0 but sidebar lists openrail — conflicting |
| Grouping for leakage-safe splits | No identity labels; frames from DFL videos lack video IDs → must be constructed (done here with pHash grouping) | Official video-level splits | Official test list | Official splits | Official splits | Identity folders (IMDB-WIKI layout) |
| Fits this hardware/session | **Yes** (CPU fine-tune on ~4.5k 224² crops ≈ 25 min) | No (approval + size) | No (approval) | No (credentials + size) | No here (Zenodo blocked; 56 GB) | No here (HF blocked) |
| Maintenance / citation | Released 2025, last commit 22 Nov 2025; article submitted to *Applied Sciences* | Mature, widely cited (ICCV 2019) | CVPR 2020 | arXiv 2006.07397 | ICCV 2021 | arXiv 2309.02218 |

Also considered and rejected quickly: **140k Real and Fake Faces** and **Real and Fake Face Detection (Yonsei)** — Kaggle-only distribution (blocked here; Kaggle account terms); **WildDeepfake** — request-based access.

### Primary sources consulted
* SAFL — https://github.com/oigres5/SAFL (README: composition, CC BY 4.0, citation, note on CelebA/Celeb-DF terms)
* FaceForensics++ — https://github.com/ondyari/FaceForensics (access via Google form; download script sent after acceptance)
* Celeb-DF — https://github.com/yuezunli/celeb-deepfakeforensics (Google/Tencent request form; "Terms to Use Celeb-DF"; 590 + 300 real, 5,639 fake videos)
* DFDC — https://ai.meta.com/datasets/dfdc/ (AWS account, IAM user and access keys required; 124k videos; preview 5k)
* OpenForensics — https://sites.google.com/view/ltnghia/research/openforensics and https://zenodo.org/records/5528418 (CC BY 4.0; 115k images / 334k faces; 56.4 GB)
* DeepFakeFace — https://huggingface.co/datasets/OpenRL/DeepFakeFace (4 zips × 30k images, ≈5 GB; licence fields conflict)

## 3. Decision

**Selected: SAFL — Synthetic and Authentic Forensic Lab dataset, images subset, commit `bfc0cb9dc5b00ba071a83abb50ac24d3c92b87df`.**

Why it is the best choice for a runnable student demonstration *here*:

1. **Legally clear and genuinely accessible.** Public GitHub repository under CC BY 4.0, downloadable without bypassing any agreement, account or approval step. FaceForensics++, Celeb-DF and DFDC all require an approval or credential step that the build session cannot (and must not) complete on the user's behalf.
2. **Real and manipulated samples together, several manipulation families.** FaceApp edits of the *same* CelebA domain as the real class are the most informative pairing; StyleGAN, DeepFaceLab and DALL·E add diversity.
3. **Right size.** ~620 MB for the image subset; trainable on CPU in about half an hour.
4. **Includes videos**, used here only to test the video-sampling path (never for training).

Trade-offs accepted and disclosed (also in `AI_MODEL_CARD.md`):

* Small (≈4.5k images) and **source-heterogeneous**: real CelebA images are 178×218 JPEGs, StyleGAN images are 1024² etc. A classifier can learn such shortcuts. Mitigation: identical face-crop → 224² → JPEG q=92 pipeline for every class, JPEG-quality augmentation; residual risk remains.
* **No identity or source-video IDs.** Leakage control is constructed: near-duplicate crops (pHash Hamming ≤ 8) are union-found into groups and whole groups are assigned to splits.
* CelebA's own terms restrict use to **non-commercial research**; we therefore do not redistribute any dataset media (samples are fetched from the official repository by script) and mark the trained checkpoint for academic use only.

If approval-gated benchmarks become available to the team later, FaceForensics++ (c23) or Celeb-DF v2 would be the natural next step for a stronger, video-level evaluation; the training script only needs a new manifest.

## 4. What was actually obtained and used

| Item | Value |
|---|---|
| Acquisition | `git clone --filter=blob:none --depth 1` + sparse checkout of `images/` from https://github.com/oigres5/SAFL |
| Downloaded | 4,497 image files, **620 MB** (plus 2 videos, 1.0 MB, for pipeline testing) |
| Used for training/evaluation | 4,472 face crops (after de-duplicating same-stem .jpg/.png pairs and dropping 5 images with no detectable face) |
| Approval pending | None |
| Not used | SAFL audio and videos (except 2 clips for video-path testing) |

See `DATASET_CARD.md` for split counts, checksums and storage paths.
