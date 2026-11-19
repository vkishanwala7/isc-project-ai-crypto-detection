"""Prepare the SAFL image subset for training.

Steps (all deterministic, seed 42):
  1. Enumerate data/datasets/safl/images/{real,fake}/*  (de-duplicate same-stem .jpg/.png pairs)
  2. Detect the largest face with MTCNN (same code as inference), crop with margin,
     resize to 224x224 and re-encode every crop as JPEG q=92 so real and fake
     crops share one compression pipeline (reduces source-format shortcuts).
  3. Group near-duplicate crops (pHash Hamming distance <= 8) with union-find so
     near-identical frames never straddle splits (leakage control).
  4. Split groups 70/15/15 stratified by (label, source family).

Outputs:
  data/datasets/safl_faces/<label>/<file>.jpg
  data/datasets/safl_faces/manifest.csv   (one row per crop incl. split + checksums)
  data/datasets/safl_faces/prep_summary.json

Usage:  python backend/scripts/prepare_dataset.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import imagehash  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402

from app.services.ai.faces import detect_faces  # noqa: E402

SRC = ROOT / "data" / "datasets" / "safl" / "images"
OUT = ROOT / "data" / "datasets" / "safl_faces"
SEED = 42
PHASH_GROUP_DIST = 8

# SAFL file-name prefixes -> source family (from the SAFL README)
SOURCE_FAMILIES = {
    "RC": "celeba_real", "RCV": "celebdf_frame_real", "RDFL": "dfl_source_real",
    "FARC": "faceapp_on_celeba", "FA": "faceapp", "TPNE": "stylegan_tpdne",
    "DFL": "deepfacelab", "D": "dalle",
}


def family(name: str) -> str:
    m = re.match(r"([A-Za-z]+)", name)
    prefix = m.group(1) if m else "?"
    return SOURCE_FAMILIES.get(prefix, "other")


class UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        self.p[self.find(a)] = self.find(b)


def main() -> None:
    torch.set_num_threads(max(1, torch.get_num_threads()))
    OUT.mkdir(parents=True, exist_ok=True)
    files: list[tuple[str, Path]] = []
    for label in ("real", "fake"):
        seen: dict[str, Path] = {}
        for p in sorted((SRC / label).iterdir()):
            if p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue
            # prefer .jpg when the same stem exists in two formats
            if p.stem in seen and seen[p.stem].suffix.lower() in {".jpg", ".jpeg"}:
                continue
            seen[p.stem] = p
        files += [(label, p) for p in seen.values()]
    print(f"{len(files)} source images after same-stem de-duplication", flush=True)

    rows, skipped = [], Counter()
    t0 = time.time()
    for i, (label, p) in enumerate(files):
        try:
            raw = p.read_bytes()
            img = Image.open(p).convert("RGB")
        except Exception:
            skipped["unreadable"] += 1
            continue
        faces = detect_faces(img, max_faces=1)
        if not faces:
            skipped[f"no_face:{family(p.name)}"] += 1
            continue
        f = faces[0]
        dst = OUT / label / (p.stem + ".jpg")
        dst.parent.mkdir(parents=True, exist_ok=True)
        f.crop.save(dst, "JPEG", quality=92)
        rows.append({
            "file": f"{label}/{dst.name}", "label": label, "source_family": family(p.name),
            "source_file": f"images/{label}/{p.name}", "source_sha256": hashlib.sha256(raw).hexdigest(),
            "crop_sha256": hashlib.sha256(dst.read_bytes()).hexdigest(), "face_prob": round(f.prob, 4),
            "phash": str(imagehash.phash(f.crop)), "src_w": img.size[0], "src_h": img.size[1],
        })
        if (i + 1) % 200 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(files)}  kept={len(rows)}  {el:.0f}s  eta {el/(i+1)*(len(files)-i-1):.0f}s", flush=True)

    # --- leakage-aware grouping on perceptual hash of the crop ---
    hashes = [imagehash.hex_to_hash(r["phash"]) for r in rows]
    uf = UnionFind(len(rows))
    for a in range(len(rows)):
        for b in range(a + 1, len(rows)):
            if hashes[a] - hashes[b] <= PHASH_GROUP_DIST:
                uf.union(a, b)
    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(rows)):
        groups[uf.find(i)].append(i)

    # stratify by the (label, family) of each group's first member
    rng = random.Random(SEED)
    strata: dict[tuple[str, str], list[int]] = defaultdict(list)
    for gid, members in groups.items():
        r0 = rows[members[0]]
        strata[(r0["label"], r0["source_family"])].append(gid)
    split_of_group: dict[int, str] = {}
    for key in sorted(strata):
        gids = sorted(strata[key])
        rng.shuffle(gids)
        n = len(gids)
        n_test = max(1, round(n * 0.15)) if n >= 3 else 0
        n_val = max(1, round(n * 0.15)) if n >= 3 else 0
        for j, g in enumerate(gids):
            split_of_group[g] = "test" if j < n_test else ("val" if j < n_test + n_val else "train")
    for gid, members in groups.items():
        for m in members:
            rows[m]["group_id"] = gid
            rows[m]["split"] = split_of_group[gid]

    with open(OUT / "manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    summary = {
        "source_images_considered": len(files),
        "crops_kept": len(rows),
        "skipped": dict(skipped),
        "multi_member_groups": sum(1 for g in groups.values() if len(g) > 1),
        "largest_group": max(len(g) for g in groups.values()),
        "phash_group_distance": PHASH_GROUP_DIST,
        "per_split_label": {
            s: dict(Counter(r["label"] for r in rows if r["split"] == s)) for s in ("train", "val", "test")
        },
        "per_split_family": {
            s: dict(Counter(r["source_family"] for r in rows if r["split"] == s)) for s in ("train", "val", "test")
        },
        "seconds": round(time.time() - t0, 1),
    }
    (OUT / "prep_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
