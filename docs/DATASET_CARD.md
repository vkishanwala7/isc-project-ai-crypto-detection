# Dataset card — data used by VERIFRAME (model v2.1)

| | |
|---|---|
| **Name** | SAFL — Synthetic and Authentic Forensic Lab dataset (images subset) |
| **Source** | https://github.com/oigres5/SAFL |
| **Version** | Git commit `bfc0cb9dc5b00ba071a83abb50ac24d3c92b87df` (22 Nov 2025) |
| **Accessed** | 17 Nov 2026 |
| **Licence** | Creative Commons Attribution 4.0 (CC BY 4.0). The README notes users must also comply with the original licences of CelebA and Celeb-DF and applicable data-protection rules. CelebA's terms restrict use to non-commercial research/education and prohibit redistribution of its images. |
| **Approval / access status** | Public repository — no account, form or agreement required. Nothing pending. |
| **Citation** | Falcón-López, S. A. *Synthetic and Authentic Forensic Lab (SAFL) Dataset.* GitHub: oigres5/SAFL. Associated article: "Forensic Analysis of Manipulated Images and Videos", submitted to *Applied Sciences* (MDPI), 2025. Underlying: Liu, Z. et al. "Deep Learning Face Attributes in the Wild", ICCV 2015 (CelebA); Li, Y. et al. "Celeb-DF", CVPR 2020. |
| **Downloaded** | `images/` (4,497 files, 620 MB) and `videos/` (416 MP4 files, 398 MB) via sparse checkout |
| **Storage path** | `data/datasets/safl/images/` (raw, git-ignored), `data/datasets/safl_faces/` (crops + manifest, git-ignored) |

## Composition (raw, from the SAFL README and file listing)

| Prefix | Family | Label | Files |
|---|---|---|---|
| RC | CelebA | real | 2,092 |
| RCV / RDFL | Celeb-DF / DFL source frames | real | 6 / 4 |
| FARC / FA | FaceApp edits (of CelebA) / other | fake | 609 / 4 |
| TPNE | thispersondoesnotexist (StyleGAN) | fake | 1,009 |
| DFL | DeepFaceLab swap frames | fake | 453 |
| D | DALL·E 2/3 | fake | 320 |

## Processing (`backend/scripts/prepare_dataset.py`)
1. Same-stem `.jpg`/`.png` duplicates collapsed (prefer `.jpg`) → 4,477 images.
2. MTCNN largest face, 30 % margin, 224×224, JPEG q=92 → **4,472 crops**; 5 CelebA images had no detectable face and were dropped.
3. Leakage control: crops with pHash Hamming distance ≤ 8 are union-found into groups (373 multi-member groups, largest 297); whole groups go to one split.
4. Group-level split 70/15/15 stratified by (label, family), seed 42.

## Video frames (added for model v2, `backend/scripts/prepare_dataset_v2.py`)

* 10 frames per video, evenly spaced (skipping the first/last 5 %), largest MTCNN face, same crop pipeline → **4,155 crops** (5 frames had no face).
* All frames of a video share one group and one split: 290 train / 63 val / 63 test videos, per family 70/15/15, seed 42. The demo videos C0042 and AV0042 are forced into test.
* Families: Celeb-DF real interviews (212 videos), Avatarify deepfakes (104), DeepFaceLab deepfakes (100).

## Team webcam clips (added for model v2.1)

* Recorded 18 Nov 2026 on the demo laptop's webcam (1280×720, about 30 fps) by the four team members, who consented to their use for training and testing this model.
* 9 clips (9–13 s) and 5 photos. Person A: 2 clips + 2 photos; B: 2 + 1; C: 3 + 1; D: 2 + 1.
* **Split by person:** A, C, D for training (282 face crops); **B held out entirely** for testing (81 crops).
* Stored only in `data/datasets/team_webcam/` (git-ignored). Not included in the project archive and not redistributed.

## Image split counts (v1, unchanged in v2)

| Split | Real | Manipulated | Total |
|---|---|---|---|
| Train | 1,487 | 1,756 | 3,243 |
| Validation | 305 | 307 | 612 |
| Test | 303 | 314 | 617 |

Combined v2 split (images + video frames): train 2,966 real / 3,173 manipulated, val 625 / 617, test 623 / 623. Per-family counts: `docs/dataset_prep_summary.json` (v1) and `docs/dataset_prep_summary_v2.json` (v2). Class imbalance in train handled with `pos_weight = 0.847`; no resampling.

## Checksums
* Every crop's SHA-256 **and** the SHA-256 of its source file, plus split and group id, are listed in `docs/dataset_split_manifest.csv` (SHA-256 of that manifest: `4c1512f10a3e9938d2523e848d7f9c26bdc4ba99fdb6e6323cd99e19391d6649`).
* Demo samples: SHA-256 pinned in `data/samples/samples.json`, verified by `scripts/fetch_demo_samples.py`.

## Re-acquire
```bash
mkdir -p data/datasets && cd data/datasets
git clone --filter=blob:none --no-checkout https://github.com/oigres5/SAFL safl && cd safl
git sparse-checkout init --no-cone && git sparse-checkout set '/README.md' '/images/' '/videos/'
git checkout bfc0cb9dc5b00ba071a83abb50ac24d3c92b87df
```

## Known limitations
No identity labels or source-video IDs; heterogeneous resolutions and compression between classes; celebrity-heavy real class; small size. See `AI_MODEL_CARD.md`.

## Redistribution
VERIFRAME does not redistribute any SAFL media or team recordings. Only metadata (file names, labels, hashes) is included.
