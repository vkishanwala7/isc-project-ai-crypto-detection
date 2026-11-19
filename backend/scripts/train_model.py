"""Fine-tune EfficientNet-B0 (timm, ImageNet init) for binary real/manipulated face classification
on the prepared SAFL face crops, then calibrate (temperature scaling) and pick the decision threshold
on the validation split, and finally evaluate ONCE on the held-out test split.

Usage:
  python backend/scripts/train_model.py [--epochs 6] [--batch 32] [--lr 3e-4]

Requires: data/datasets/safl_faces/manifest.csv (from prepare_dataset.py) and
          model_weights/pretrained/efficientnet_b0_ra-3dd342df.pth (ImageNet weights from the timm GitHub release)
Writes:   model_weights/veriframe_effb0_safl.pt, model_weights/metrics.json,
          model_weights/training_log.json, model_weights/test_predictions.csv
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np  # noqa: E402
import timm  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from PIL import Image  # noqa: E402
from torch.utils.data import DataLoader, Dataset  # noqa: E402
from torchvision import transforms as T  # noqa: E402

from app.services.ai.metrics import binary_metrics, expected_calibration_error, fit_temperature  # noqa: E402

DATA = ROOT / "data" / "datasets" / "safl_faces"
WEIGHTS = ROOT / "model_weights"
PRETRAINED = WEIGHTS / "pretrained" / "efficientnet_b0_ra-3dd342df.pth"
MEAN, STD = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
SEED = 42


class RandomJPEG:
    """Re-encode with a random JPEG quality (compression-robustness augmentation)."""

    def __init__(self, p=0.5, qmin=50, qmax=95):
        self.p, self.qmin, self.qmax = p, qmin, qmax

    def __call__(self, img):
        if random.random() > self.p:
            return img
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=random.randint(self.qmin, self.qmax))
        buf.seek(0)
        return Image.open(buf).convert("RGB")


class RandomDownUp:
    """Randomly lose resolution (downscale then upscale) so sharpness is not a class cue."""

    def __init__(self, p=0.5, smin=56, smax=200):
        self.p, self.smin, self.smax = p, smin, smax

    def __call__(self, img):
        if random.random() > self.p:
            return img
        s = random.randint(self.smin, self.smax)
        down = random.choice([Image.BILINEAR, Image.BICUBIC, Image.LANCZOS, Image.NEAREST])
        return img.resize((s, s), down).resize(img.size, random.choice([Image.BILINEAR, Image.BICUBIC]))


class RandomNoise:
    """Additive Gaussian sensor-like noise."""

    def __init__(self, p=0.3, smin=2.0, smax=10.0):
        self.p, self.smin, self.smax = p, smin, smax

    def __call__(self, img):
        if random.random() > self.p:
            return img
        a = np.asarray(img, dtype=np.float32)
        a = a + np.random.normal(0, random.uniform(self.smin, self.smax), a.shape)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


class Crops(Dataset):
    def __init__(self, rows, tf):
        self.rows, self.tf = rows, tf

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(DATA / r["file"]).convert("RGB")
        return self.tf(img), torch.tensor(1.0 if r["label"] == "fake" else 0.0)


def run_epoch(model, loader, loss_fn, opt=None, sched=None):
    train = opt is not None
    model.train(train)
    logits_all, y_all, loss_sum, n = [], [], 0.0, 0
    with torch.set_grad_enabled(train):
        for bi, (x, y) in enumerate(loader):
            out = model(x).squeeze(1)
            loss = loss_fn(out, y)
            if train:
                opt.zero_grad()
                loss.backward()
                opt.step()
                sched.step()
            loss_sum += loss.item() * len(y)
            n += len(y)
            logits_all.append(out.detach())
            y_all.append(y)
            if train and bi % 25 == 0:
                print(f"    batch {bi}/{len(loader)} loss {loss.item():.4f}", flush=True)
    return loss_sum / n, torch.cat(logits_all).numpy(), torch.cat(y_all).numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--manifest", default="manifest_v2.csv")
    ap.add_argument("--version", default="2.0.0")
    args = ap.parse_args()

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    rows = list(csv.DictReader(open(DATA / args.manifest)))
    split = {s: [r for r in rows if r["split"] == s] for s in ("train", "val", "test")}
    n_real = sum(r["label"] == "real" for r in split["train"])
    n_fake = sum(r["label"] == "fake" for r in split["train"])
    pos_weight = torch.tensor(n_real / max(1, n_fake))
    print({k: len(v) for k, v in split.items()}, "train real/fake", n_real, n_fake, "pos_weight", round(pos_weight.item(), 3), flush=True)

    train_tf = T.Compose([
        T.RandomResizedCrop(224, scale=(0.75, 1.0), ratio=(0.9, 1.1)),
        T.RandomHorizontalFlip(),
        T.RandomApply([T.ColorJitter(0.25, 0.25, 0.20, 0.03)], p=0.6),
        T.RandomGrayscale(p=0.05),
        RandomDownUp(p=0.5),
        T.RandomApply([T.GaussianBlur(5, sigma=(0.1, 1.6))], p=0.3),
        RandomNoise(p=0.3),
        RandomJPEG(p=0.6, qmin=30, qmax=95),
        T.ToTensor(), T.Normalize(MEAN, STD),
    ])
    eval_tf = T.Compose([T.ToTensor(), T.Normalize(MEAN, STD)])
    dl = {
        "train": DataLoader(Crops(split["train"], train_tf), batch_size=args.batch, shuffle=True, num_workers=0,
                            generator=torch.Generator().manual_seed(SEED)),
        "val": DataLoader(Crops(split["val"], eval_tf), batch_size=32, num_workers=0),
        "test": DataLoader(Crops(split["test"], eval_tf), batch_size=32, num_workers=0),
    }

    model = timm.create_model("efficientnet_b0", pretrained=False, num_classes=1, drop_rate=0.2)
    sd = torch.load(PRETRAINED, map_location="cpu", weights_only=True)
    sd = {k: v for k, v in sd.items() if not k.startswith("classifier.")}
    missing = model.load_state_dict(sd, strict=False)
    print("loaded ImageNet init; missing:", missing.missing_keys, flush=True)

    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * len(dl["train"]), pct_start=0.15)

    log, best_auc, best_state = [], -1.0, None
    t0 = time.time()
    for ep in range(1, args.epochs + 1):
        te = time.time()
        tr_loss, tr_logits, tr_y = run_epoch(model, dl["train"], loss_fn, opt, sched)
        va_loss, va_logits, va_y = run_epoch(model, dl["val"], loss_fn)
        va_m = binary_metrics(va_y, 1 / (1 + np.exp(-va_logits)), 0.5)
        tr_m = binary_metrics(tr_y, 1 / (1 + np.exp(-tr_logits)), 0.5)
        entry = {"epoch": ep, "train_loss": round(tr_loss, 4), "train_acc": tr_m["accuracy"], "val_loss": round(va_loss, 4),
                 "val_auc": va_m["roc_auc"], "val_acc": va_m["accuracy"], "seconds": round(time.time() - te, 1)}
        log.append(entry)
        print(entry, flush=True)
        if va_m["roc_auc"] > best_auc:
            best_auc = va_m["roc_auc"]
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            entry["best"] = True

    model.load_state_dict(best_state)
    _, va_logits, va_y = run_epoch(model, dl["val"], loss_fn)
    temperature = fit_temperature(va_logits, va_y)
    va_p = 1 / (1 + np.exp(-va_logits / temperature))
    # threshold maximising balanced accuracy (Youden's J) on validation
    cands = np.unique(np.round(va_p, 4))
    best_t, best_j = 0.5, -1
    for t in cands:
        pred = va_p >= t
        tpr = (pred & (va_y == 1)).sum() / max(1, (va_y == 1).sum())
        tnr = (~pred & (va_y == 0)).sum() / max(1, (va_y == 0).sum())
        if tpr + tnr - 1 > best_j:
            best_j, best_t = tpr + tnr - 1, float(t)
    threshold = round(best_t, 4)

    # ---- single held-out test evaluation ----
    _, te_logits, te_y = run_epoch(model, dl["test"], loss_fn)
    te_p_raw = 1 / (1 + np.exp(-te_logits))
    te_p = 1 / (1 + np.exp(-te_logits / temperature))
    test_m = binary_metrics(te_y, te_p, threshold)
    fam = {}
    for r, p in zip(split["test"], te_p):
        f = fam.setdefault(r["source_family"], {"n": 0, "correct": 0, "label": r["label"]})
        f["n"] += 1
        f["correct"] += int((p >= threshold) == (r["label"] == "fake"))
    for f in fam.values():
        f["accuracy"] = round(f["correct"] / f["n"], 4)

    # video-level evaluation: mean of frame scores per held-out test video
    vids = {}
    for r, p in zip(split["test"], te_p):
        g = r.get("group_id", "")
        if g.startswith("vid-"):
            vids.setdefault(g, {"label": r["label"], "family": r["source_family"], "scores": []})["scores"].append(float(p))
    video_level = None
    if vids:
        vy = np.array([1 if v["label"] == "fake" else 0 for v in vids.values()])
        vs = np.array([np.mean(v["scores"]) for v in vids.values()])
        video_level = {"n_videos": len(vids), **binary_metrics(vy, vs, threshold),
                       "per_family": {f: round(float(np.mean([(np.mean(v["scores"]) >= threshold) == (v["label"] == "fake") for v in vids.values() if v["family"] == f])), 4)
                                      for f in sorted({v["family"] for v in vids.values()})},
                       "aggregation": "mean of frame scores per video, deployed threshold"}

    WEIGHTS.mkdir(exist_ok=True)
    ckpt_path = WEIGHTS / "veriframe_effb0_safl.pt"
    meta = {
        "model_name": "VERIFRAME-EffB0-SAFL", "architecture": "efficientnet_b0 (timm %s), 1 logit" % timm.__version__,
        "version": args.version, "input_size": 224, "mean": MEAN, "std": STD, "temperature": float(temperature),
        "threshold": threshold, "positive_class": "manipulated",
        "trained_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    torch.save({"state_dict": best_state, "meta": meta}, ckpt_path)
    ckpt_sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()

    metrics = {
        "computed_on": "held-out SAFL test split (group-aware, never used for training, early stopping, calibration or threshold selection)",
        "n_test": int(len(te_y)), "n_test_real": int((te_y == 0).sum()), "n_test_fake": int((te_y == 1).sum()),
        "threshold": threshold, "temperature": float(temperature),
        "test": test_m,
        "test_at_0.5_uncalibrated": binary_metrics(te_y, te_p_raw, 0.5),
        "ece_test_uncalibrated": expected_calibration_error(te_y, te_p_raw),
        "ece_test_calibrated": expected_calibration_error(te_y, te_p),
        "per_source_family_test_accuracy": fam,
        "video_level_test": video_level,
        "validation": {"n": int(len(va_y)), "best_roc_auc": float(best_auc), "youden_j": float(best_j)},
        "checkpoint_sha256": ckpt_sha,
    }
    training = {
        "seed": SEED, "epochs": args.epochs, "batch_size": args.batch, "optimizer": "AdamW(wd=1e-4)",
        "schedule": "OneCycleLR(pct_start=0.15)", "max_lr": args.lr, "loss": "BCEWithLogits(pos_weight=n_real/n_fake)",
        "pos_weight": float(pos_weight), "augmentations": "RandomResizedCrop(0.75-1), HFlip, ColorJitter(p=.6), Grayscale(p=.05), RandomDownUp(56-200px,p=.5), GaussianBlur(sigma .1-1.6,p=.3), GaussianNoise(2-10,p=.3), RandomJPEG(q30-95,p=.6) - applied identically to both classes", "manifest": args.manifest,
        "split_sizes": {k: len(v) for k, v in split.items()}, "train_real": n_real, "train_fake": n_fake,
        "hardware": f"CPU only ({platform.processor() or platform.machine()}, torch threads={torch.get_num_threads()})",
        "torch": torch.__version__, "total_seconds": round(time.time() - t0, 1), "epochs_log": log,
        "init_weights": "timm efficientnet_b0_ra-3dd342df.pth (ImageNet-1k), sha256 3dd342dfa1fee25ae65e7bbdf8998cad6e45d6e77e69d580f0bd14d3eeb0b3f3",
    }
    (WEIGHTS / "metrics.json").write_text(json.dumps({**metrics, "model": meta}, indent=2))
    (WEIGHTS / "training_log.json").write_text(json.dumps(training, indent=2))
    with open(WEIGHTS / "test_predictions.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["file", "label", "source_family", "score_calibrated"])
        for r, p in zip(split["test"], te_p):
            w.writerow([r["file"], r["label"], r["source_family"], round(float(p), 5)])
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
