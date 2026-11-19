# AI model card — VERIFRAME-EffB0-SAFL v2.1.0

| | |
|---|---|
| **Status** | Trained by this project (Team 16) on 18 Nov 2026; loaded by the backend at startup |
| **Checkpoint** | `model_weights/veriframe_effb0_safl.pt` (16.3 MB) |
| **Checkpoint SHA-256** | `c7d4ebfb0c1bbec4eefd21d1b4c461cd372557640fa29529c5eff51341618272` |
| **Architecture** | EfficientNet-B0 (timm 1.0.31), single logit, dropout 0.2 |
| **Initialisation** | timm ImageNet-1k weights `efficientnet_b0_ra-3dd342df.pth` (Apache-2.0) |
| **Task** | Binary: face crop is *authentic* vs *manipulated/synthetic* (positive class = manipulated) |
| **Training data** | SAFL images + face frames from all 416 SAFL videos (stage 1); real webcam clips of 3 team members (stage 2) |
| **Not used** | Any pretrained deepfake detector; any remote code |
| **Intended use** | Classroom demonstration of an AI forensic *signal* alongside cryptographic provenance |
| **Out of scope** | Legal, journalistic or moderation decisions; non-face content; very low-resolution faces; audio |

## Version history (why v2.1 exists)

| Version | Training data | What happened |
|---|---|---|
| v1.0 (17 Nov) | SAFL images only | 96.1 % on its image test set, but ordinary camera faces (webcam, event photos) and real interview video were scored ≈ 0.99 — false positives. Real training faces were all CelebA celebrity photos. |
| v2.0 (18 Nov) | + 4,155 face frames from 416 SAFL videos; class-agnostic quality augmentation | Real interview videos mostly fixed; robustness to blur/downscaling greatly improved; team webcam photos still flagged (4 of 5). |
| **v2.1 (18 Nov, deployed)** | v2.0 + webcam clips of team members A, C, D; member B held out | Held-out member B: **0 of 81 frames flagged**. StyleGAN faces still 100 % caught. Small loss on CelebA-style real photos (specificity 95.4 % → 90.1 %). |

v1.0 and v2.0 metrics are kept in `model_weights/v1/` and `model_weights/v2.0/`.

## Preprocessing (identical in training and inference — `backend/app/services/ai/faces.py`)
1. Decode, apply EXIF orientation, RGB.
2. MTCNN face detection (facenet-pytorch 2.6.0, weights bundled in the PyPI wheel, MIT) on a copy ≤640 px; faces with probability ≥ 0.90.
3. Square crop with 30 % margin, resize to 224×224 (bicubic). Training crops re-encoded as JPEG q=92.
4. ImageNet mean/std normalisation.

## Training

**Stage 1** (`backend/scripts/prepare_dataset_v2.py`, `train_model.py --manifest manifest_v2.csv`)
* Data: 6,139 train / 1,242 val / 1,246 test crops (train 2,966 real / 3,173 manipulated). Images keep their v1 split (pHash-grouped); video frames are grouped **per video** (290 / 63 / 63 videos), 10 frames per video. The two Demo-workspace videos are forced into the test split.
* ImageNet init, 5 epochs, batch 24, AdamW (lr 3e-4, wd 1e-4), OneCycle, BCEWithLogits (pos_weight 0.935). 48 min on 2 CPU threads.
* Augmentation applied identically to both classes: random resized crop, flip, colour jitter, grayscale, **random resolution loss (56–200 px), blur, Gaussian noise, JPEG q30–95** — so image quality stops being a "fake" cue.

**Stage 2** (`backend/scripts/finetune_team.py --holdout B`)
* Data: 282 face crops (40 frames per clip + photos) from webcam clips of team members A, C, D, recorded on 18 Nov 2026 on the demo laptop with their consent, repeated ×3 and mixed with 3,000 random SAFL training crops. **Member B never used for training.**
* Init from v2.0, up to 3 epochs, lr 1e-4, cosine schedule; best validation ROC-AUC kept (epoch 1, 0.942). 18 min.
* Temperature (T = 2.3231) and threshold (**0.4618**, Youden's J) re-fitted on the SAFL validation split only. Scores within ±0.10 of the threshold are reported as INCONCLUSIVE.

## Results

### Held-out SAFL test split (`model_weights/metrics.json`)
1,246 crops (623 real, 623 manipulated): images + frames of 63 whole videos never used in any training stage.

| Metric | v2.1 | v2.0 |
|---|---|---|
| ROC-AUC | **0.934** | 0.941 |
| Accuracy (= balanced) | 86.9 % | 88.5 % |
| Precision / recall | 86.3 % / 87.8 % | 91.5 % / 84.9 % |
| Specificity (real correct) | 86.0 % | 92.1 % |
| Whole-video accuracy (63 videos, mean of frame scores) | 84.1 % | 88.9 % |
| ECE (calibrated) | 0.039 | — |

Confusion matrix (v2.1, threshold 0.4618): TN 536, FP 87, FN 76, TP 547. Whole videos: TN 27, FP 5, FN 5, TP 26.

Per family (v2.1 test): StyleGAN (thispersondoesnotexist) **100 %** (n 135) · DALL·E 96.7 % (30) · DeepFaceLab images 86.9 % (61) · DeepFaceLab videos 87.3 % (149 frames) · Avatarify videos 85.0 % (160 frames) · FaceApp-on-CelebA 72.1 % (86) · CelebA real 90.1 % (302) · real interview-video frames 82.2 % (320).

### Unseen person on a normal webcam (`model_weights/team_holdout.json`)
Member B (2 clips + 1 photo, never in training): **0 / 81 frames flagged**, median score 0.010; clip means 0.017 and 0.022, photo 0.181. The same photo scored 0.729 (flagged) under v2.0. Through the full app pipeline, a live browser camera feed of B gave 0.016 (photo) and 0.011 (clip). One person, one room, one camera: a sanity check, not a benchmark.

### Robustness (`backend/scripts/robustness_eval.py`, `model_weights/robustness.json`)
Same test crops, perturbed after cropping, fixed threshold:

| Perturbation | Accuracy | Specificity v2.1 | Specificity v1.0 |
|---|---|---|---|
| none | 86.9 % | 86.0 % | 96.4 % |
| JPEG q70 | 85.9 % | 87.6 % | 98.0 % |
| JPEG q40 | 84.0 % | 87.3 % | 93.1 % |
| downscale 112 px | 83.2 % | **80.7 %** | 28.7 % |
| downscale 64 px | 76.9 % | 66.9 % | 44.5 % |
| blur r=1.5 | 81.1 % | **76.9 %** | 16.8 % |

(v1.0 numbers were measured on its own, image-only test set.)

## Limitations and risks
* **Narrow notion of "real".** Real training faces are celebrities (CelebA, YouTube interviews) plus three students on one webcam in one room. Other demographics, ages, rooms, lighting and cameras are thinly covered; an unfamiliar real face can still be flagged.
* **Trade-off chosen deliberately.** Stage 2 made webcam faces reliable but CelebA-style photos slightly more likely to be flagged (specificity 95.4 → 90.1 %).
* **Subtle edits are hard.** FaceApp edits are caught only 72 % of the time; fully generated faces far more reliably.
* **Unseen generators and heavy compression** reduce accuracy; very low resolution still raises false positives.
* **Splits.** SAFL has no identity labels (a celebrity may appear in train and test); video frames are split per video and team data per person.
* **Single runs, one dataset.** No confidence intervals; not comparable to published detectors.
* **False-positive harm.** The UI always presents the score as a model estimate with the threshold, separate from provenance.
* **Video.** ≤16 evenly sampled frames, mean over face-containing frames; no temporal modelling, no audio.

## Licence / privacy
Weights derive from CelebA/Celeb-DF-containing data (non-commercial research terms) and from team members' faces: for the team's academic use only — do not publish. The team clips are stored only in `data/datasets/team_webcam/` (git-ignored) and are not included in the project archive.

## Reproduce
```bash
python backend/scripts/prepare_dataset.py && python backend/scripts/prepare_dataset_v2.py
python backend/scripts/train_model.py --epochs 5 --manifest manifest_v2.csv --version 2.0.0
#   copy the resulting checkpoint + metrics to model_weights/v2.0/
python backend/scripts/finetune_team.py --holdout B --epochs 3   # needs data/datasets/team_webcam/<person>/
python backend/scripts/robustness_eval.py manifest_v2.csv
```
