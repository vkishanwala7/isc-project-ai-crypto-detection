"""Post-hoc robustness check on the held-out SAFL test crops (no retraining, no threshold change).

Applies each perturbation to every test crop, scores it with the trained checkpoint, and reports
metrics at the fixed deployed threshold. Writes model_weights/robustness.json.

Usage: python backend/scripts/robustness_eval.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

from app.services.ai.detector import Detector  # noqa: E402
from app.services.ai.metrics import binary_metrics  # noqa: E402

DATA = ROOT / "data" / "datasets" / "safl_faces"


def jpeg(q):
    def f(img):
        b = io.BytesIO()
        img.save(b, "JPEG", quality=q)
        b.seek(0)
        return Image.open(b).convert("RGB")
    return f


def down_up(s):
    return lambda img: img.resize((s, s), Image.BILINEAR).resize((224, 224), Image.BILINEAR)


PERTURB = {
    "none": lambda i: i,
    "jpeg_q70": jpeg(70),
    "jpeg_q40": jpeg(40),
    "downscale_112": down_up(112),
    "downscale_64": down_up(64),
    "blur_r1.5": lambda i: i.filter(ImageFilter.GaussianBlur(1.5)),
}


def main():
    det = Detector()
    info = det.info()
    assert info.available, info.reason
    manifest = sys.argv[1] if len(sys.argv) > 1 else "manifest_v2.csv"
    rows = [r for r in csv.DictReader(open(DATA / manifest)) if r["split"] == "test"]
    y = np.array([1 if r["label"] == "fake" else 0 for r in rows])
    imgs = [Image.open(DATA / r["file"]).convert("RGB") for r in rows]
    out = {"note": "Held-out test crops (%s), perturbed after face cropping; fixed threshold %.4f; no retraining." % (manifest, info.threshold),
           "threshold": info.threshold, "n": len(rows), "results": {}}
    for name, fn in PERTURB.items():
        scores = []
        for i in range(0, len(imgs), 32):
            scores += det._score_crops([fn(im) for im in imgs[i:i + 32]])
        m = binary_metrics(y, np.array(scores), info.threshold)
        out["results"][name] = {k: m[k] for k in ("accuracy", "balanced_accuracy", "recall", "specificity", "roc_auc", "confusion_matrix")}
        print(name, out["results"][name], flush=True)
    (ROOT / "model_weights" / "robustness.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
