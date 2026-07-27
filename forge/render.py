"""Rasterizer: family definition -> single-loop-row sheet + measured metrics.

Treatments (the whole point of the forge):

* hostile — the ONE shared signature from docs/12 §2.6 v0: a bright ~1px rim
  on every silhouette edge plus a hard bright core at the center, with a dark
  saturated body between them. High contrast in grayscale, identical
  treatment across every hostile family — hostile-vs-friendly never depends
  on color.
* player — flat muted body with a darker edge. No rim, no core: visually
  subordinate by construction (Law 2).

Pixels are hard-edged: alpha is strictly {0, 255} (coverage-thresholded, 4x4
supersampled). Nearest-filtered pixel art wants crisp edges, and binary alpha
makes every validator measurement exact.

Measured per family (into the manifest — these are the Law 8 data):
* inscribedRadiusPx — largest centered circle fully opaque in EVERY frame.
  Hostile render rule: scale = hitboxRadiusPx / inscribedRadiusPx makes the
  visual cover the collision circle exactly.
* crossHalfExtentPx / halfExtentPx — opaque extents; the friendly render rule
  caps the cross-axis at the hitbox (under-render is player-favorable).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .families import CELL, CORE_RGB, RIM_RGB, SIGNATURE, Family

_SS = 4          # supersamples per axis
_RIM_BAND = 1.35  # px: SDF band painted as the signature rim


@dataclass
class RenderedFamily:
    family: Family
    frames_rgba: list          # one bytes (CELL*CELL*4) per frame
    masks: list                # one list[int] (0/1, CELL*CELL) per frame
    inscribed_px: float
    cross_half_px: float
    half_extent_px: float

    @property
    def render_scale(self) -> float:
        f = self.family
        if f.role == "hostile":
            return f.hitbox_radius_px / self.inscribed_px
        return min(1.0, f.hitbox_radius_px / self.cross_half_px)

    def sheet_rgba(self) -> tuple:
        """(width, height, pixels) — frames left-to-right in one row."""
        n = len(self.frames_rgba)
        width = CELL * n
        out = bytearray(width * CELL * 4)
        for i, frame in enumerate(self.frames_rgba):
            for y in range(CELL):
                src = y * CELL * 4
                dst = (y * width + i * CELL) * 4
                out[dst : dst + CELL * 4] = frame[src : src + CELL * 4]
        return width, CELL, bytes(out)


def _coverage(sdf, phase: float, px: float, py: float) -> float:
    hits = 0
    for sy in range(_SS):
        for sx in range(_SS):
            x = px + (sx + 0.5) / _SS - 0.5
            y = py + (sy + 0.5) / _SS - 0.5
            if sdf(x, y, phase) < 0.0:
                hits += 1
    return hits / (_SS * _SS)


def render_family(fam: Family) -> RenderedFamily:
    c = CELL / 2.0
    # Static-silhouette pulse families keep one mask; spin families re-evaluate.
    base_inscribed = -fam.sdf(0.0, 0.0, 0.0)
    frames_rgba = []
    masks = []
    for f in range(fam.frames):
        phase = f / fam.frames
        spin_phase = phase if fam.spin_symmetry else 0.0
        pulse = math.sin(2.0 * math.pi * phase) * fam.pulse_px
        core_r = base_inscribed * SIGNATURE["coreRadiusFrac"] + pulse
        buf = bytearray(CELL * CELL * 4)
        mask = [0] * (CELL * CELL)
        for yy in range(CELL):
            for xx in range(CELL):
                px = xx + 0.5 - c
                py = yy + 0.5 - c
                cov = _coverage(fam.sdf, spin_phase, px, py)
                if cov < 0.5:
                    continue
                d = fam.sdf(px, py, spin_phase)
                if fam.role == "hostile":
                    rgb = _hostile_pixel(fam, d, px, py, core_r, base_inscribed)
                else:
                    rgb = _player_pixel(fam, d)
                i = (yy * CELL + xx) * 4
                buf[i] = rgb[0]
                buf[i + 1] = rgb[1]
                buf[i + 2] = rgb[2]
                buf[i + 3] = 255
                mask[yy * CELL + xx] = 1
        frames_rgba.append(bytes(buf))
        masks.append(mask)
    return RenderedFamily(
        family=fam,
        frames_rgba=frames_rgba,
        masks=masks,
        inscribed_px=_inscribed_radius(masks),
        cross_half_px=_cross_half_extent(masks),
        half_extent_px=_half_extent(masks),
    )


def _hostile_pixel(fam: Family, d: float, px: float, py: float, core_r: float, inscribed: float) -> tuple:
    if d >= -_RIM_BAND:
        return RIM_RGB
    r = math.hypot(px, py)
    if r <= core_r:
        return CORE_RGB
    if fam.silhouette == "roundel":
        # The Ringer roundel paints its ring PATTERN inside a solid disc —
        # never a hollow silhouette over a solid hitbox (Law 8).
        if 0.52 * inscribed <= r <= 0.74 * inscribed:
            b = fam.body_rgb
            return (
                b[0] + (CORE_RGB[0] - b[0]) * 2 // 3,
                b[1] + (CORE_RGB[1] - b[1]) * 2 // 3,
                b[2] + (CORE_RGB[2] - b[2]) * 2 // 3,
            )
    return fam.body_rgb


def _player_pixel(fam: Family, d: float) -> tuple:
    if d >= -_RIM_BAND:
        return fam.edge_rgb
    return fam.body_rgb


def _inscribed_radius(masks: list) -> float:
    """Largest centered circle fully opaque in every frame (0.25px steps)."""
    c = CELL / 2.0
    best = 0.0
    r = 0.25
    while r <= c:
        ok = True
        for mask in masks:
            for yy in range(CELL):
                for xx in range(CELL):
                    if mask[yy * CELL + xx]:
                        continue
                    # transparent pixel: its full square must lie outside r
                    nx = max(abs(xx + 0.5 - c) - 0.5, 0.0)
                    ny = max(abs(yy + 0.5 - c) - 0.5, 0.0)
                    if math.hypot(nx, ny) < r:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if not ok:
            break
        best = r
        r += 0.25
    return best


def _cross_half_extent(masks: list) -> float:
    c = CELL / 2.0
    best = 0.0
    for mask in masks:
        for yy in range(CELL):
            for xx in range(CELL):
                if mask[yy * CELL + xx]:
                    best = max(best, abs(yy + 0.5 - c) + 0.5)
    return best


def _half_extent(masks: list) -> float:
    c = CELL / 2.0
    best = 0.0
    for mask in masks:
        for yy in range(CELL):
            for xx in range(CELL):
                if mask[yy * CELL + xx]:
                    best = max(best, math.hypot(xx + 0.5 - c, yy + 0.5 - c) + 0.5)
    return best
