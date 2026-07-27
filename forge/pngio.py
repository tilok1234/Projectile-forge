"""Minimal deterministic PNG writer/reader (RGBA8, stdlib only).

The pack must be a reproducible build artifact (same inputs => byte-identical
output, mirroring the TileForge determinism rule), so no image library is
used: rows are emitted with filter type 0 and compressed with a fixed zlib
level. The reader only accepts what the writer emits — it exists so
`validate` can audit a pack from disk rather than trusting in-memory state.
"""

from __future__ import annotations

import struct
import zlib

_SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_rgba(width: int, height: int, pixels: bytes) -> bytes:
    """Encode raw RGBA bytes (row-major, 4 bytes/px) as a PNG file blob."""
    if len(pixels) != width * height * 4:
        raise ValueError("pixel buffer size mismatch")
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)  # filter type 0 on every row — keeps the reader trivial
        raw += pixels[y * stride : (y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)
    return _SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def read_rgba(blob: bytes) -> tuple[int, int, bytes]:
    """Decode a PNG produced by write_rgba. Returns (width, height, rgba)."""
    if blob[:8] != _SIG:
        raise ValueError("not a PNG")
    pos = 8
    width = height = 0
    idat = bytearray()
    while pos < len(blob):
        (length,) = struct.unpack(">I", blob[pos : pos + 4])
        tag = blob[pos + 4 : pos + 8]
        data = blob[pos + 8 : pos + 8 + length]
        if tag == b"IHDR":
            width, height, depth, ctype = struct.unpack(">IIBB", data[:10])
            if depth != 8 or ctype != 6:
                raise ValueError("unsupported PNG layout (writer emits RGBA8 only)")
        elif tag == b"IDAT":
            idat += data
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    stride = width * 4
    out = bytearray()
    for y in range(height):
        row = raw[y * (stride + 1) : (y + 1) * (stride + 1)]
        if row[0] != 0:
            raise ValueError("unexpected row filter (writer emits filter 0 only)")
        out += row[1:]
    return width, height, bytes(out)
