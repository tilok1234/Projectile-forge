"""Rasterizer: family definition -> hitbox-native single-loop-row sheet.

Two-pass "bake":

1. Measure the authored SDF (analytic center-to-edge distance, sampled
   extents at 32px) and derive the family's final on-screen scale from the
   render rules (hostile: inscribed circle == hitbox circle, Law 8; player:
   cross-axis capped at the hitbox, Law 2).
2. Rasterize AT that final size into a per-family cell. The manifest then
   ships renderScale = 1.0: the game draws sheets 1:1 in its 640x360 buffer
   with no runtime scaling, so pixels stay crisp under Nearest and the
   hostile signature rim is a uniform 1px on every family — cleanliness and
   consistency by construction, not by tuning.

Treatments:
* hostile — the ONE shared signature from docs/12 §2.6 v0: a bright 1px rim
  on every silhouette edge plus a hard bright core at the hitbox center,
  dark saturated body between. High contrast in grayscale; identical across
  every hostile family.
* player — flat muted body with a darker edge. No rim, no core (Law 2).

Edges are analytically anti-aliased from the SDF (alpha = clamp(0.5 - d)):
a one-pixel smooth fringe at the silhouette boundary, fully opaque interior.
Color transitions (rim -> body -> core, ring bands) blend over sub-pixel
ramps instead of hard bands. The validator enforces the shape of this
smoothness: partial alpha may exist ONLY hugging the outer boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .families import CORE_RGB, RIM_RGB, SIGNATURE, Family

_RIM_BAND = 1.05   # screen px: the signature rim band (uniform per family)
_BLEND = 0.9       # px: color-transition ramp width (rim->body, core->body)
_MARGIN = 2        # px of clear space around the shape in its cell


@dataclass
class RenderedFamily:
    family: Family
    cell: int                  # px — per-family, hitbox-native
    frames_rgba: list          # one bytes (cell*cell*4) per frame
    masks: list                # one list[int] (0/1, cell*cell) per frame
    bake_scale: float          # authored-32px-space -> screen px factor
    inscribed_px: float        # measured on the baked masks
    cross_half_px: float
    half_extent_px: float

    def sheet_rgba(self) -> tuple:
        """(width, height, pixels) — frames left-to-right in one row."""
        n = len(self.frames_rgba)
        width = self.cell * n
        out = bytearray(width * self.cell * 4)
        for i, frame in enumerate(self.frames_rgba):
            for y in range(self.cell):
                src = y * self.cell * 4
                dst = (y * width + i * self.cell) * 4
                out[dst : dst + self.cell * 4] = frame[src : src + self.cell * 4]
        return width, self.cell, bytes(out)


def _measure_authored(fam: Family) -> tuple:
    """(inscribed, cross_half, half_extent) of the authored shape, in the
    32px authoring space, across all frames.

    Inscribed is measured by radial marching — the FIRST boundary crossing
    per direction, minimized over directions — never by trusting the SDF
    value at the center: min-union SDFs (cross, twin lobes) underestimate
    interior distance near seams, and a wrong inscribed radius here bakes a
    dishonest hitbox fit (Law 8)."""
    inscribed = 1e9
    cross = 0.0
    half = 0.0
    steps = 120
    for f in range(fam.frames):
        phase = (f / fam.frames) if fam.spin_symmetry else 0.0
        for i in range(steps):
            ang = 2.0 * math.pi * i / steps
            c, s = math.cos(ang), math.sin(ang)
            last_in = 0.0
            first_out = 16.0
            rr = 0.125
            while rr <= 16.0:
                if fam.sdf(c * rr, s * rr, phase) < 0.0:
                    last_in = rr
                elif first_out == 16.0:
                    first_out = rr
                rr += 0.125
            inscribed = min(inscribed, first_out)
            half = max(half, last_in)
            cross = max(cross, abs(s) * last_in)
    return inscribed, cross, half


def bake_scale_for(fam: Family) -> tuple:
    """(scale, metrics) — the authored->screen factor per the render rules.
    Hostile gets a +0.5px pad against raster quantization of the
    half-coverage contour — enough to keep the baked inscribed circle
    at-or-above the hitbox without inflating the sprite."""
    inscribed, cross, half = _measure_authored(fam)
    if fam.role == "hostile":
        scale = (fam.hitbox_radius_px + 0.5) / inscribed
    else:
        scale = min(1.0, fam.hitbox_radius_px / cross)
    return scale, (inscribed, cross, half)


def render_family(fam: Family) -> RenderedFamily:
    scale, (a_ins, a_cross, a_half) = bake_scale_for(fam)
    cell = 2 * int(math.ceil(a_half * scale)) + 2 * _MARGIN
    cell += cell % 2  # even, so the center sits between pixels
    c = cell / 2.0

    def sdf_screen(x: float, y: float, phase: float) -> float:
        return fam.sdf(x / scale, y / scale, phase) * scale

    core_base = fam.hitbox_radius_px * SIGNATURE["coreRadiusFrac"]
    frames_rgba = []
    masks = []
    for f in range(fam.frames):
        phase = f / fam.frames
        spin_phase = phase if fam.spin_symmetry else 0.0
        pulse = math.sin(2.0 * math.pi * phase) * fam.pulse_px
        core_r = core_base + pulse
        buf = bytearray(cell * cell * 4)
        mask = [0] * (cell * cell)
        for yy in range(cell):
            for xx in range(cell):
                px = xx + 0.5 - c
                py = yy + 0.5 - c
                d = sdf_screen(px, py, spin_phase)
                a = 0.5 - d  # analytic 1px edge AA
                if a <= 0.0:
                    continue
                a = min(a, 1.0)
                if fam.role == "hostile":
                    rgb = _hostile_pixel(fam, d, px, py, core_r)
                else:
                    rgb = _player_pixel(fam, d)
                i = (yy * cell + xx) * 4
                buf[i] = rgb[0]
                buf[i + 1] = rgb[1]
                buf[i + 2] = rgb[2]
                buf[i + 3] = int(round(a * 255.0))
                if a >= 0.5:
                    mask[yy * cell + xx] = 1
        frames_rgba.append(bytes(buf))
        masks.append(mask)
    return RenderedFamily(
        family=fam,
        cell=cell,
        frames_rgba=frames_rgba,
        masks=masks,
        bake_scale=scale,
        inscribed_px=_inscribed_radius(masks, cell),
        cross_half_px=_cross_half_extent(masks, cell),
        half_extent_px=_half_extent(masks, cell),
    )


def _clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def _mix(a: tuple, b: tuple, t: float) -> tuple:
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def _hostile_pixel(fam: Family, d: float, px: float, py: float, core_r: float) -> tuple:
    r = math.hypot(px, py)
    body = fam.body_rgb
    # soft energy glow: the body warms toward the core, so shapes read as
    # lit from within instead of flat-filled
    glow_span = max(fam.hitbox_radius_px * 1.6 - core_r, 1.0)
    col = _mix(body, CORE_RGB, 0.30 * _clamp01(1.0 - (r - core_r) / glow_span))
    if fam.pattern == "rings":
        # Painted INSIDE a solid silhouette, never cut out of it (Law 8).
        hb = fam.hitbox_radius_px
        mid = _mix(body, CORE_RGB, 2.0 / 3.0)
        band = _clamp01((r - 0.58 * hb) / _BLEND) * _clamp01((0.82 * hb - r) / _BLEND)
        col = _mix(col, mid, band)
    # hard bright core with a soft shoulder
    col = _mix(col, CORE_RGB, _clamp01((core_r - r) / _BLEND + 1.0))
    # thin dark ink line just inside the rim: definition against dark floors
    dark = (body[0] * 2 // 5, body[1] * 2 // 5, body[2] * 2 // 5)
    ink = _clamp01((d + 3.1) / 0.7) * _clamp01(-(d + 1.6) / 0.7)
    col = _mix(col, dark, ink)
    # the signature rim on top: full strength at the boundary, soft inner side
    col = _mix(col, RIM_RGB, _clamp01((d + _RIM_BAND) / _BLEND + 1.0))
    return col


def _player_pixel(fam: Family, d: float) -> tuple:
    return _mix(fam.body_rgb, fam.edge_rgb, _clamp01((d + _RIM_BAND) / _BLEND + 1.0))


def _inscribed_radius(masks: list, cell: int) -> float:
    """Largest centered circle whose every covered pixel CENTER is opaque at
    the half-coverage contour, minimized over frames. Pixel-center sampling
    matches how the AA sheets actually read on screen — the fringe outside
    the contour still carries ink."""
    c = cell / 2.0
    best = 1e9
    for mask in masks:
        for yy in range(cell):
            for xx in range(cell):
                if not mask[yy * cell + xx]:
                    best = min(best, math.hypot(xx + 0.5 - c, yy + 0.5 - c))
    return max(0.0, math.floor((best - 0.01) / 0.25) * 0.25)


def _cross_half_extent(masks: list, cell: int) -> float:
    c = cell / 2.0
    best = 0.0
    for mask in masks:
        for yy in range(cell):
            for xx in range(cell):
                if mask[yy * cell + xx]:
                    best = max(best, abs(yy + 0.5 - c) + 0.5)
    return best


def _half_extent(masks: list, cell: int) -> float:
    c = cell / 2.0
    best = 0.0
    for mask in masks:
        for yy in range(cell):
            for xx in range(cell):
                if mask[yy * cell + xx]:
                    best = max(best, math.hypot(xx + 0.5 - c, yy + 0.5 - c) + 0.5)
    return best
