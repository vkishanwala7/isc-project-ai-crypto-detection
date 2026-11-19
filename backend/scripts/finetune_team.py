"""v2.1: fine-tune the v2 model with real webcam footage recorded by the team (with consent).

Why: every real face in SAFL is a celebrity (CelebA photos, YouTube interviews). Ordinary people
on a laptop webcam were outside that distribution and were often flagged. A few clips from our
own cameras teach the model that domain.

Leakage control / honest test: the data is split BY PERSON. One person (default: B) is never
used for training; their clips and photo are the held-out test of "an unseen face on this webcam".
Threshold and temperature are re-fitted on the SAFL validation split only (no team data).

Inputs : TEAM_DIR/<person>/*.mp4|*.jpg      (default TEAM_DIR = data/datasets/team_webcam, git-ignored)
Outputs: model_weights/veriframe_effb0_safl.pt (v2.1.0), metrics.json, training_log.json,
         test_predictions.csv, team_holdout.json
Usage  : python backend/scripts/finetune_team.py [--holdout B] [--epochs 3]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import timm  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from PIL import Image  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from torchvision import transforms as T  # noqa: E402

import train_model as tm  # noqa: E402  (augmentations, dataset, epoch loop)
from app.services.ai.faces import detect_faces  # noqa: E402
from app.services.ai.metrics import binary_metrics, expected_calibration_error, fit_temperature  # noqa: E402

TEAM = ROOT / "data" / "datasets" / "team_webcam"
CROPS = ROOT / "data" / "datasets" / "team_webcam_faces"
W = ROOT / "model_weights"
SEED = 42


def crop_media(person: str, path: Path, frames: int) -> list[dict]:
    out = []
    if path.suffix.lower() == ".mp4":
        cap = cv2.VideoCapture(str(path))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for k, idx in enumerate(np.linspace(int(n * 0.03), int(n * 0.97) - 1, frames).round().astype(int)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, fr = cap.read()
            if not ok:
                continue
            out.append((f"{path.stem}_f{k:03d}", Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))))
        cap.release()
    else:
        out.append((path.stem, Image.open(path).convert("RGB")))
    rows = []
    for name, img in out:
        faces = detect_faces(img, max_faces=1)
        if not faces:
            continue
        dst = CROPS / person / f"{name}.jpg"
        dst.parent.mkdir(parents=True, exist_ok=True)
        faces[0].crop.save(dst, "JPEG", quality=92)
        rows.append({"file": str(dst), "label": "real", "source_family": "team_webcam_real", "person": person,
                     "media": path.name, "group_id": f"team-{person}"})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", default="B")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--frames", type=int, default=40, help="frames sampled per training clip")
    ap.add_argument("--safl_subset", type=int, default=3000)
    ap.add_argument("--team_repeat", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    a = ap.parse_args()
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    people = sorted(p.name for p in TEAM.iterdir() if p.is_dir())
    team_train, team_test = [], []
    for person in people:
        for m in sorted((TEAM / person).iterdir()):
            if m.suffix.lower() not in (".mp4", ".jpg", ".jpeg", ".png"):
                continue
            rows = crop_media(person, m, a.frames)
            (team_test if person == a.holdout else team_train).extend(rows)
    print(f"people={people} holdout={a.holdout} team_train={len(team_train)} team_test_frames={len(team_test)}", flush=True)

    manifest = list(csv.DictReader(open(tm.DATA / "manifest_v2.csv")))
    split = {s: [r for r in manifest if r["split"] == s] for s in ("train", "val", "test")}
    rng = random.Random(SEED)
    safl_sub = rng.sample(split["train"], min(a.safl_subset, len(split["train"])))
    train_rows = safl_sub + team_train * a.team_repeat
    n_real = sum(r["label"] == "real" for r in train_rows)
    n_fake = len(train_rows) - n_real
    pos_weight = torch.tensor(n_real / max(1, n_fake))

    train_tf = T.Compose([
        T.RandomResizedCrop(224, scale=(0.75, 1.0), ratio=(0.9, 1.1)), T.RandomHorizontalFlip(),
        T.RandomApply([T.ColorJitter(0.25, 0.25, 0.20, 0.03)], p=0.6), T.RandomGrayscale(p=0.05),
        tm.RandomDownUp(p=0.5), T.RandomApply([T.GaussianBlur(5, sigma=(0.1, 1.6))], p=0.3),
        tm.RandomNoise(p=0.3), tm.RandomJPEG(p=0.6, qmin=30, qmax=95), T.ToTensor(), T.Normalize(tm.MEAN, tm.STD),
    ])
    eval_tf = T.Compose([T.ToTensor(), T.Normalize(tm.MEAN, tm.STD)])
    dl_train = DataLoader(tm.Crops(train_rows, train_tf), batch_size=24, shuffle=True, num_workers=0,
                          generator=torch.Generator().manual_seed(SEED))
    dl_val = DataLoader(tm.Crops(split["val"], eval_tf), batch_size=32)
    dl_test = DataLoader(tm.Crops(split["test"], eval_tf), batch_size=32)

    base = torch.load(W / "v2.0" / "veriframe_effb0_safl.pt", map_location="cpu", weights_only=True)
    model = timm.create_model("efficientnet_b0", pretrained=False, num_classes=1, drop_rate=0.2)
    model.load_state_dict(base["state_dict"])
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs * len(dl_train))

    t0, log, best_auc, best = time.time(), [], -1, None
    for ep in range(1, a.epochs + 1):
        te = time.time()
        tr_loss, _, _ = tm.run_epoch(model, dl_train, loss_fn, opt, sched)
        va_loss, va_logits, va_y = tm.run_epoch(model, dl_val, loss_fn)
        auc = binary_metrics(va_y, 1 / (1 + np.exp(-va_logits)), 0.5)["roc_auc"]
        log.append({"epoch": ep, "train_loss": round(tr_loss, 4), "val_loss": round(va_loss, 4), "val_auc": auc, "seconds": round(time.time() - te, 1)})
        print(log[-1], flush=True)
        if auc > best_auc:
            best_auc, best = auc, {k: v.clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best)

    _, va_logits, va_y = tm.run_epoch(model, dl_val, loss_fn)
    temperature = fit_temperature(va_logits, va_y)
    va_p = 1 / (1 + np.exp(-va_logits / temperature))
    best_t, best_j = 0.5, -1
    for t in np.unique(np.round(va_p, 4)):
        pred = va_p >= t
        j = (pred & (va_y == 1)).sum() / max(1, (va_y == 1).sum()) + (~pred & (va_y == 0)).sum() / max(1, (va_y == 0).sum()) - 1
        if j > best_j:
            best_j, best_t = j, float(t)
    threshold = round(best_t, 4)

    _, te_logits, te_y = tm.run_epoch(model, dl_test, loss_fn)
    te_p = 1 / (1 + np.exp(-te_logits / temperature))
    test_m = binary_metrics(te_y, te_p, threshold)
    fam = {}
    for r, p in zip(split["test"], te_p):
        f = fam.setdefault(r["source_family"], {"n": 0, "correct": 0, "label": r["label"]})
        f["n"] += 1
        f["correct"] += int((p >= threshold) == (r["label"] == "fake"))
    for f in fam.values():
        f["accuracy"] = round(f["correct"] / f["n"], 4)
    vids = {}
    for r, p in zip(split["test"], te_p):
        if r.get("group_id", "").startswith("vid-"):
            vids.setdefault(r["group_id"], {"label": r["label"], "family": r["source_family"], "s": []})["s"].append(float(p))
    vy = np.array([1 if v["label"] == "fake" else 0 for v in vids.values()])
    vs = np.array([np.mean(v["s"]) for v in vids.values()])
    video_level = {"n_videos": len(vids), **binary_metrics(vy, vs, threshold),
                   "per_family": {f: round(float(np.mean([(np.mean(v["s"]) >= threshold) == (v["label"] == "fake") for v in vids.values() if v["family"] == f])), 4)
                                  for f in sorted({v["family"] for v in vids.values()})},
                   "aggregation": "mean of frame scores per video, deployed threshold"}

    # held-out person: frame level with the same eval transform
    hx = torch.stack([eval_tf(Image.open(r["file"]).convert("RGB")) for r in team_test]) if team_test else None
    with torch.inference_mode():
        hp = (1 / (1 + np.exp(-model(hx).squeeze(1).numpy() / temperature))) if hx is not None else np.array([])
    per_media = {}
    for r, p in zip(team_test, hp):
        per_media.setdefault(r["media"], []).append(float(p))
    holdout = {"person": a.holdout, "n_frames": int(len(hp)), "frames_flagged_rate": round(float((hp >= threshold).mean()), 4) if len(hp) else None,
               "frame_score_median": round(float(np.median(hp)), 4) if len(hp) else None,
               "per_media": {m: {"n": len(v), "mean": round(float(np.mean(v)), 4), "flagged": bool(np.mean(v) >= threshold)} for m, v in per_media.items()},
               "note": "This person never appeared in training; scores use the deployed threshold."}

    meta = {"model_name": "VERIFRAME-EffB0-SAFL", "architecture": f"efficientnet_b0 (timm {timm.__version__}), 1 logit",
            "version": "2.1.0", "input_size": 224, "mean": tm.MEAN, "std": tm.STD, "temperature": float(temperature),
            "threshold": threshold, "positive_class": "manipulated", "trained_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    ck = W / "veriframe_effb0_safl.pt"
    torch.save({"state_dict": best, "meta": meta}, ck)
    sha = hashlib.sha256(ck.read_bytes()).hexdigest()
    metrics = {
        "computed_on": "held-out SAFL test split (images + 63 whole videos, group-aware; never used for training, early stopping, calibration or threshold selection)",
        "n_test": int(len(te_y)), "n_test_real": int((te_y == 0).sum()), "n_test_fake": int((te_y == 1).sum()),
        "threshold": threshold, "temperature": float(temperature), "test": test_m,
        "ece_test_calibrated": expected_calibration_error(te_y, te_p), "per_source_family_test_accuracy": fam,
        "video_level_test": video_level, "team_holdout": holdout,
        "validation": {"n": int(len(va_y)), "best_roc_auc": float(best_auc), "youden_j": float(best_j)},
        "checkpoint_sha256": sha,
    }
    (W / "metrics.json").write_text(json.dumps({**metrics, "model": meta}, indent=2))
    (W / "team_holdout.json").write_text(json.dumps(holdout, indent=2))
    prev = json.loads((W / "v2.0" / "training_log.json").read_text())
    training = {**prev, "version": "2.1.0", "stage2": {
        "description": "fine-tuned from v2.0 with real webcam clips of team members (person-disjoint hold-out)",
        "init": "v2.0 checkpoint", "epochs": a.epochs, "lr": a.lr, "schedule": "cosine", "batch_size": 24,
        "safl_subset": len(safl_sub), "team_people_train": [p for p in people if p != a.holdout], "team_holdout": a.holdout,
        "team_train_crops": len(team_train), "team_repeat": a.team_repeat, "pos_weight": float(pos_weight),
        "epochs_log": log, "seconds": round(time.time() - t0, 1)}}
    (W / "training_log.json").write_text(json.dumps(training, indent=2))
    with open(W / "test_predictions.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "label", "source_family", "score_calibrated"])
        for r, p in zip(split["test"], te_p):
            w.writerow([r["file"], r["label"], r["source_family"], round(float(p), 5)])
    print(json.dumps({"threshold": threshold, "test": {k: test_m[k] for k in ("accuracy", "roc_auc", "specificity", "recall")},
                      "families": {k: v["accuracy"] for k, v in fam.items()}, "video": video_level["accuracy"], "holdout": holdout}, indent=1))


if __name__ == "__main__":
    main()
