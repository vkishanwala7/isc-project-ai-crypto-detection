"""v2 data: add face crops from SAFL *videos* to the v1 image manifest.

Why: v1 learned "real" almost only from CelebA stills, so ordinary camera photos were often
flagged. Real Celeb-DF interview footage (212 videos) adds natural camera faces; Avatarify and
DeepFaceLab videos (204) add video-domain fakes so "video" itself is not a cue.

* v1 image rows keep their v1 split (so the v1 test images stay unseen).
* Per video: K frames evenly spaced (skipping the first/last 5%), largest MTCNN face, the same
  224x224 crop + JPEG q=92 pipeline as v1. All frames of a video share one group and one split
  (no frame-level leakage). Split per family 70/15/15, seed 42.
* The two Demo-workspace videos (C0042, AV0042) are forced into the test split.

Output: data/datasets/safl_faces/manifest_v2.csv, prep_summary_v2.json
Usage:  python backend/scripts/prepare_dataset_v2.py [--frames 10]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import cv2  # noqa: E402
import imagehash  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app.services.ai.faces import detect_faces  # noqa: E402

VID = ROOT / "data" / "datasets" / "safl" / "videos"
OUT = ROOT / "data" / "datasets" / "safl_faces"
SEED = 42
FORCE_TEST = {"C0042", "AV0042"}
FAMILY = {"C": "celebdf_video_real", "AV": "avatarify_video", "DFL": "deepfacelab_video"}


def fam(stem: str) -> str:
    for p in ("DFL", "AV", "C"):
        if stem.startswith(p):
            return FAMILY[p]
    return "other_video"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=10)
    a = ap.parse_args()
    v1 = list(csv.DictReader(open(OUT / "manifest.csv")))
    for r in v1:
        r["group_id"] = f"img-{r['group_id']}"
        r["source_kind"] = "image"

    videos = sorted(VID.glob("*/*.mp4"))
    rng = random.Random(SEED)
    by_fam: dict[str, list[Path]] = defaultdict(list)
    for v in videos:
        by_fam[fam(v.stem)].append(v)
    split_of: dict[str, str] = {}
    for f in sorted(by_fam):
        vs = sorted(by_fam[f], key=lambda p: p.stem)
        rng.shuffle(vs)
        rest = [v for v in vs if v.stem not in FORCE_TEST]
        n = len(vs)
        n_test, n_val = round(n * 0.15), round(n * 0.15)
        forced = [v for v in vs if v.stem in FORCE_TEST]
        for v in forced:
            split_of[v.stem] = "test"
        for i, v in enumerate(rest):
            split_of[v.stem] = "test" if i < n_test - len(forced) else ("val" if i < n_test - len(forced) + n_val else "train")

    rows, skipped, t0 = [], Counter(), time.time()
    for vi, v in enumerate(videos):
        label = "real" if v.parent.name == "real" else "fake"
        cap = cv2.VideoCapture(str(v))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n <= 0:
            skipped["unreadable_video"] += 1
            continue
        lo, hi = int(n * 0.05), max(int(n * 0.95) - 1, int(n * 0.05))
        idxs = sorted(set(np.linspace(lo, hi, a.frames).round().astype(int).tolist()))
        src_sha = hashlib.sha256(v.read_bytes()).hexdigest()
        kept = 0
        for k, idx in enumerate(idxs):
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, fr = cap.read()
            if not ok:
                skipped["unreadable_frame"] += 1
                continue
            img = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
            faces = detect_faces(img, max_faces=1)
            if not faces:
                skipped[f"no_face:{fam(v.stem)}"] += 1
                continue
            dst = OUT / f"v{label}" / f"{v.stem}_f{k:02d}.jpg"
            dst.parent.mkdir(parents=True, exist_ok=True)
            faces[0].crop.save(dst, "JPEG", quality=92)
            rows.append({
                "file": f"v{label}/{dst.name}", "label": label, "source_family": fam(v.stem),
                "source_file": f"videos/{v.parent.name}/{v.name}#frame{idx}", "source_sha256": src_sha,
                "crop_sha256": hashlib.sha256(dst.read_bytes()).hexdigest(), "face_prob": round(faces[0].prob, 4),
                "phash": str(imagehash.phash(faces[0].crop)), "src_w": img.size[0], "src_h": img.size[1],
                "group_id": f"vid-{v.stem}", "split": split_of[v.stem], "source_kind": "video_frame",
            })
            kept += 1
        cap.release()
        if (vi + 1) % 40 == 0:
            print(f"  {vi+1}/{len(videos)} videos, {len(rows)} frames, {time.time()-t0:.0f}s", flush=True)

    allrows = v1 + rows
    fields = list(allrows[0].keys())
    with open(OUT / "manifest_v2.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(allrows)
    summary = {
        "videos": len(videos), "video_frames_kept": len(rows), "frames_per_video_requested": a.frames,
        "skipped": dict(skipped), "forced_test_videos": sorted(FORCE_TEST),
        "per_split_label": {s: dict(Counter(r["label"] for r in allrows if r["split"] == s)) for s in ("train", "val", "test")},
        "per_split_family": {s: dict(Counter(r["source_family"] for r in allrows if r["split"] == s)) for s in ("train", "val", "test")},
        "videos_per_split": dict(Counter(split_of.values())), "seconds": round(time.time() - t0, 1),
    }
    (OUT / "prep_summary_v2.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
