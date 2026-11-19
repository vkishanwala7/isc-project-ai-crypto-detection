"""Controlled tampering for the Integrity Lab. Always produces a NEW byte string;
the source bytes are never modified in place."""
from __future__ import annotations

import io
import struct
import zlib

from PIL import Image


def _jpeg_segments(data: bytes):
    """Yield (marker, start, length) for JPEG marker segments up to SOS."""
    i = 2
    while i < len(data) - 4:
        if data[i] != 0xFF:
            raise ValueError("bad JPEG marker alignment")
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        yield marker, i, seg_len
        if marker == 0xDA:  # start of scan
            return
        i += 2 + seg_len


def tamper_jpeg_quant_table(data: bytes) -> tuple[bytes, str]:
    """Increment one luminance quantisation-table coefficient by 1.

    The file stays a valid, decodable JPEG with an almost invisible change, and any embedded
    C2PA manifest (APP11) is left byte-for-byte intact — so verification must detect the change
    through the content-binding hash."""
    for marker, start, seg_len in _jpeg_segments(data):
        if marker == 0xDB:
            pq_tq = data[start + 4]
            if pq_tq >> 4 != 0:
                continue  # 16-bit table; skip for simplicity
            # coefficient index 10 (mid frequency) of the first 8-bit table
            pos = start + 5 + 10
            old = data[pos]
            new = old + 1 if old < 255 else old - 1
            out = bytearray(data)
            out[pos] = new
            return bytes(out), f"JPEG DQT coefficient #10 changed {old}→{new} at byte offset {pos} (1 byte modified)"
    raise ValueError("no 8-bit quantisation table found")


def _png_chunks(data: bytes):
    i = 8
    while i < len(data):
        length = struct.unpack(">I", data[i:i + 4])[0]
        ctype = data[i + 4:i + 8]
        yield ctype, i, length
        i += 12 + length


def tamper_png_pixel(data: bytes) -> tuple[bytes, str]:
    """Change one raw pixel byte inside the IDAT stream, recompress, fix the CRC.

    Other chunks (including the C2PA `caBX` chunk) are copied unchanged."""
    chunks = list(_png_chunks(data))
    idat = b"".join(data[s + 8:s + 8 + n] for t, s, n in chunks if t == b"IDAT")
    raw = bytearray(zlib.decompress(idat))
    ihdr = next(data[s + 8:s + 8 + n] for t, s, n in chunks if t == b"IHDR")
    width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr[:10])
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type, 3)
    bpp = max(1, channels * bit_depth // 8)
    stride = 1 + width * bpp  # +1 filter-type byte per scanline
    # middle pixel of the middle row — never a filter-type byte
    pos = (height // 2) * stride + 1 + (width // 2) * bpp
    raw[pos] = (raw[pos] + 7) % 256
    new_idat = zlib.compress(bytes(raw), 9)
    out = bytearray(data[:8])
    wrote = False
    for t, s, n in chunks:
        if t == b"IDAT":
            if not wrote:
                out += struct.pack(">I", len(new_idat)) + b"IDAT" + new_idat + struct.pack(">I", zlib.crc32(b"IDAT" + new_idat) & 0xFFFFFFFF)
                wrote = True
            continue
        out += data[s:s + 12 + n]
    return bytes(out), f"PNG IDAT: one decompressed pixel byte at index {pos} changed (+7), stream recompressed, CRC recomputed"


def byte_level_tamper(data: bytes, mime: str) -> tuple[bytes, str]:
    if mime == "image/jpeg":
        return tamper_jpeg_quant_table(data)
    if mime == "image/png":
        return tamper_png_pixel(data)
    # generic fallback: flip one byte in the final quarter of the file
    pos = len(data) - max(16, len(data) // 4)
    out = bytearray(data)
    out[pos] ^= 0x01
    return bytes(out), f"Bit flip at byte offset {pos} (generic)"


def visual_edit_reencode(data: bytes) -> tuple[bytes, str]:
    """Paint a small 12x12 patch and re-encode as a fresh JPEG. Re-encoding drops any embedded
    manifest (demonstrates signature stripping) and changes nearly every byte."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    w, h = img.size
    px = img.load()
    s = max(6, min(w, h) // 40)
    x0, y0 = w // 2 - s // 2, h // 2 - s // 2
    for x in range(x0, x0 + s):
        for y in range(y0, y0 + s):
            r, g, b = px[x, y]
            px[x, y] = (min(255, r + 60), g, b)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue(), f"{s}x{s} px patch brightened at image centre, then re-encoded as JPEG (q=90); all metadata dropped"
