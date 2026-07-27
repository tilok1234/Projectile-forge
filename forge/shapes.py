"""2D signed-distance silhouettes, in pixels, centered on the cell origin.

Every projectile silhouette is an analytic SDF (negative inside). Shapes are
authored pointing +X — the game rotates instances to the travel direction, so
"forward" is always +X in the sheet. SDFs give the renderer exact coverage,
give the hostile-signature treatment an exact edge band, and make every
frame a pure function of its parameters (no RNG anywhere — patterns are
deterministic and authored, CORE-32 spirit applied to art).

Formulas adapted from the standard Inigo Quilez 2D SDF set.
"""

from __future__ import annotations

import math


def sd_circle(x: float, y: float, r: float) -> float:
    return math.hypot(x, y) - r


def sd_capsule_x(x: float, y: float, half_len: float, r: float) -> float:
    """Capsule along the X axis: segment (-half_len,0)-(+half_len,0), radius r."""
    cx = min(max(x, -half_len), half_len)
    return math.hypot(x - cx, y) - r


def sd_teardrop_x(x: float, y: float, back_x: float, back_r: float, nose_x: float, nose_r: float) -> float:
    """Uneven capsule: round back circle at (back_x, 0) tapering to a small
    nose circle at (nose_x, 0). Reads as a dart — point forward, mass at the
    back. Requires nose_x > back_x and back_r > nose_r."""
    u = abs(y)            # perpendicular to the axis
    v = x - back_x        # along the axis
    h = nose_x - back_x
    b = (back_r - nose_r) / h
    a = math.sqrt(max(1.0 - b * b, 0.0))
    k = -b * u + a * v
    if k < 0.0:
        return math.hypot(u, v) - back_r
    if k > a * h:
        return math.hypot(u, v - h) - nose_r
    return a * u + b * v - back_r


def sd_rhombus_x(x: float, y: float, bx: float, by: float) -> float:
    """Rhombus with half-diagonals bx (along X) and by (along Y)."""
    px, py = abs(x), abs(y)
    ndot = bx * (bx - 2.0 * px) - by * (by - 2.0 * py)
    h = max(min(ndot / (bx * bx + by * by), 1.0), -1.0)
    dx = px - 0.5 * bx * (1.0 - h)
    dy = py - 0.5 * by * (1.0 + h)
    d = math.hypot(dx, dy)
    sign = 1.0 if (px * by + py * bx - bx * by) > 0.0 else -1.0
    return d * sign


def sd_triangle_isosceles_back(x: float, y: float, apex_x: float, base_x: float, half_base: float) -> float:
    """Isosceles triangle: apex at (apex_x, 0), flat base (leading edge) at
    x = base_x spanning ±half_base. Authored blunt-face-forward so fan shots
    read as a widening wall, unmistakable next to the dart's round back."""
    # Triangle vertices: A=(apex_x,0), B=(base_x, half_base), C=(base_x,-half_base)
    py = abs(y)
    bx_, by_ = base_x, half_base
    # Edge apex->base corner
    ex, ey = bx_ - apex_x, by_ - 0.0
    qx, qy = x - apex_x, py
    t = max(0.0, min(1.0, (qx * ex + qy * ey) / (ex * ex + ey * ey)))
    d1 = math.hypot(qx - ex * t, qy - ey * t)
    # Base edge (vertical segment at x=base_x from 0..half_base in the folded half-plane)
    cy = min(max(py, 0.0), by_)
    d2 = math.hypot(x - bx_, py - cy)
    d = min(d1, d2)
    # Inside test (folded): left of base plane, and below the apex-corner edge line
    inside = (x <= bx_) and (ex * qy - ey * qx) <= 0.0
    return -d if inside else d


def sd_roundel(x: float, y: float, r: float) -> float:
    """Solid disc. The Ringer roundel is a SOLID circle — a hollow ring visual
    over a solid circular hitbox would invite standing in the hole and dying
    to it (an unexplainable death, Law 8), so the ring pattern is painted
    INSIDE a solid silhouette by the treatment, never cut out of it."""
    return sd_circle(x, y, r)


def sd_star(x: float, y: float, r: float, n: float, m: float) -> float:
    """n-point star. r = outer radius, m in (2, n) controls point sharpness
    (closer to n = sharper, m = 2 degenerates to a convex polygon)."""
    an = math.pi / n
    en = math.pi / m
    # fold into the first sector (no abs pre-fold — it would force 4-fold
    # symmetry and mangle odd point counts)
    ang = math.atan2(x, y) % (2.0 * an) - an
    plen = math.hypot(x, y)
    px2 = plen * math.cos(ang)
    py2 = abs(plen * math.sin(ang))
    # edge
    acs_x, acs_y = math.cos(an), math.sin(an)
    ecs_x, ecs_y = math.cos(en), math.sin(en)
    px3 = px2 - r * acs_x
    py3 = py2 - r * acs_y
    t = max(0.0, min((-px3 * ecs_x - py3 * ecs_y), r * acs_y / ecs_y))
    px4 = px3 + ecs_x * t
    py4 = py3 + ecs_y * t
    d = math.hypot(px4, py4)
    return d if px4 > 0.0 else -d


def sd_star4(x: float, y: float, r: float, m: float) -> float:
    return sd_star(x, y, r, 4.0, m)


def sd_capsule_y(x: float, y: float, half_len: float, r: float) -> float:
    """Capsule along the Y axis — a bar spanning the cross-axis (sweeper)."""
    return sd_capsule_x(y, x, half_len, r)


def sd_union(a: float, b: float) -> float:
    return min(a, b)


def sd_subtract(a: float, b: float) -> float:
    """Approximate subtraction (exact inside, conservative near corners) —
    good enough for rasterizing; the validator judges the rendered result."""
    return max(a, -b)


def sd_crescent_x(x: float, y: float, r: float, bite_x: float, bite_r: float) -> float:
    """Solid crescent, horns forward (+X): disc of radius r at the origin
    minus a bite disc ahead of it. The waist stays over the cell center so
    the centered hitbox circle fits inside opaque body (Law 8)."""
    return sd_subtract(sd_circle(x, y, r), sd_circle(x - bite_x, y, bite_r))


def sd_cross(x: float, y: float, half_len: float, r: float, rot: float) -> float:
    """Plus-cross: two perpendicular capsules, rotated by `rot` radians."""
    c, s = math.cos(rot), math.sin(rot)
    rx = x * c - y * s
    ry = x * s + y * c
    return sd_union(sd_capsule_x(rx, ry, half_len, r), sd_capsule_y(rx, ry, half_len, r))


def sd_twin_orb(x: float, y: float, lobe_r: float, offset: float) -> float:
    """Two overlapping lobes across the travel axis; the overlap waist covers
    the cell center (solid, Law 8)."""
    return sd_union(sd_circle(x, y - offset, lobe_r), sd_circle(x, y + offset, lobe_r))


def sd_triangle_point_forward(x: float, y: float, apex_x: float, base_x: float, half_base: float) -> float:
    """Sliver/shard: apex leads (+X), base trails — the point-forward
    counterpart of the blunt-forward wedge."""
    return sd_triangle_isosceles_back(-x, y, -apex_x, -base_x, half_base)


def sd_box(x: float, y: float, half_w: float, half_h: float) -> float:
    """Axis-aligned rectangle (the player plate)."""
    dx = abs(x) - half_w
    dy = abs(y) - half_h
    ox = max(dx, 0.0)
    oy = max(dy, 0.0)
    return math.hypot(ox, oy) + min(max(dx, dy), 0.0)
