"""SHA-256 (cryptographic, exact-byte integrity) and pHash (perceptual similarity heuristic).

These are deliberately kept in separate functions: pHash is NEVER used for an integrity decision."""
from __future__ import annotations

import hashlib

import imagehash
from PIL import Image


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def phash_hex(img: Image.Image) -> str:
    """64-bit DCT perceptual hash (imagehash.phash), hex encoded."""
    return str(imagehash.phash(img.convert("RGB")))


def phash_distance(a: str, b: str) -> int:
    return int(imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b))


def similarity_label(distance: int) -> str:
    """Heuristic bands for a 64-bit pHash. Labelled as an estimate everywhere in the UI."""
    if distance <= 4:
        return "visually near-identical (heuristic)"
    if distance <= 10:
        return "visually similar (heuristic)"
    if distance <= 20:
        return "weakly similar (heuristic)"
    return "visually different (heuristic)"
