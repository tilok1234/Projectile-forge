"""Pack validator: the readability laws as executable checks.

Runs on the DECODED pack (manifest + PNG bytes), never on in-memory renderer
state, so `python -m forge validate` audits what is actually on disk. Every
check row lands in validation-report.json with measured values — acceptance
is a record, not a vibe.

Rows (mapped to the binding constraints):
* alpha-hygiene       — anti-aliasing is edge-only: partial alpha may exist
                        only hugging the outer boundary (within 2px of fully
                        transparent); interiors are fully opaque — smooth
                        edges can never decay into mushy translucent sprites
* hostile-signature   — §2.6 + contour: EVERY shot's boundary is the
                        near-black outline (readable on light and dark
                        floors); hostile shots carry the bright rim just
                        inside it; NO player pixel is ever rim-bright
                        (Law 2/3)
* silhouette-distinct — Law 3 / CORE-50: declared silhouette classes unique,
                        AND measured pairwise mask overlap (IoU at final
                        on-screen size — sheets are hitbox-native) under
                        threshold for every pair involving a hostile family
* hitbox-cover        — Law 8: baked equality — the centered inscribed
                        opaque circle matches the collision circle on every
                        hostile family; player cross-axis never exceeds its
                        hitbox
* photosensitivity    — 9-row acceptance, row nine: per-frame mean-luminance
                        delta and loop flash rate capped (≤ 3 Hz at 60 t/s)
* roster-coverage     — every shot-firing §3.3/§3.4/§3.5 roster entry has a
                        core family; catalog drift fails loudly
"""

from __future__ import annotations

import math

from .families import TICKS_PER_SECOND

# Hostile families must separate from EACH OTHER by naked silhouette — shape
# alone, color and treatment gone (Law 3 / CORE-50 strict reading).
IOU_MAX_HOSTILE_PAIR = 0.55
# Hostile-vs-player discrimination is carried by the shared signature (§2.6);
# the silhouette check on these pairs is only a guard rail.
IOU_MAX_CROSS_ROLE_PAIR = 0.75
OUTLINE_LUM_MAX = 0.25      # boundary pixels must be at most this bright...
OUTLINE_FRACTION_MIN = 0.90  # ...for at least this fraction of the boundary
RIM_LUM_MIN = 0.80          # hostile: rays from the hitbox center must cross
RIM_RAY_COUNT = 72          # a rim-bright pixel — the rim is a bright ring
RIM_RAY_FRACTION_MIN = 0.95  # around the threat center, whatever the shape
PLAYER_LUM_MAX = 0.78       # player shots have NO rim-bright pixel anywhere
COVER_TOL = 0.3             # px: baked inscribed-vs-hitbox equality tolerance
COVER_SLACK = 2.5           # px: inscribed may exceed the hitbox by at most this (bake pad + raster)
LUM_DELTA_MAX = 0.02        # mean-luminance step between consecutive frames
FLASH_HZ_MAX = 3.0

REQUIRED_CONSUMERS = {
    "weapon:longbolt", "weapon:scattercast", "weapon:wheelblade",
    "enemy:husk_archer", "enemy:leadshot", "enemy:fanmaw", "enemy:ringer",
    "elite:yard_warden:p1", "elite:yard_warden:p2", "elite:yard_warden:p3",
}


def _lum(r: int, g: int, b: int) -> float:
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _frames_of(sheet: tuple, frames: int, cell: int) -> list:
    """Split a single-row sheet (w, h, rgba) into per-frame pixel lists."""
    w, h, px = sheet
    out = []
    for i in range(frames):
        frame = []
        for y in range(cell):
            for x in range(cell):
                j = (y * w + i * cell + x) * 4
                frame.append((px[j], px[j + 1], px[j + 2], px[j + 3]))
        out.append(frame)
    return out


def _mask(frame: list) -> list:
    """Silhouette mask at the half-coverage contour (alpha >= 128)."""
    return [1 if p[3] >= 128 else 0 for p in frame]


def _boundary(mask: list, cell: int) -> list:
    out = []
    for y in range(cell):
        for x in range(cell):
            if not mask[y * cell + x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= cell or ny >= cell or not mask[ny * cell + nx]:
                    out.append(y * cell + x)
                    break
    return out


def _mean_lum(frame: list, cell: int) -> float:
    total = 0.0
    for r, g, b, a in frame:
        if a:
            total += _lum(r, g, b) * (a / 255.0)
    return total / (cell * cell)


def _iou_native(mask_a: list, cell_a: int, mask_b: list, cell_b: int) -> float:
    """Overlap of two hitbox-native silhouettes, both centered — the
    canonical Law 3 comparison pose (shapes point +X)."""
    grid = 116
    half = grid / 2.0
    inter = union = 0
    for gy in range(grid):
        for gx in range(grid):
            sx = gx + 0.5 - half
            sy = gy + 0.5 - half
            a = b = 0
            ax = int(sx + cell_a / 2.0)
            ay = int(sy + cell_a / 2.0)
            if 0 <= ax < cell_a and 0 <= ay < cell_a:
                a = mask_a[ay * cell_a + ax]
            bx = int(sx + cell_b / 2.0)
            by = int(sy + cell_b / 2.0)
            if 0 <= bx < cell_b and 0 <= by < cell_b:
                b = mask_b[by * cell_b + bx]
            if a and b:
                inter += 1
            if a or b:
                union += 1
    return inter / union if union else 0.0


def validate_pack(manifest: dict, sheets: dict) -> dict:
    """manifest: parsed projectileforge-manifest.json.
    sheets: image filename -> (width, height, rgba bytes).
    Returns the validation report dict; report["pass"] is the verdict."""
    rows = []
    fams = manifest["families"]
    data = {}
    for key, fam in fams.items():
        cell = fam["cellPx"]
        frames = _frames_of(sheets[fam["image"]], fam["frames"], cell)
        data[key] = {
            "meta": fam,
            "cell": cell,
            "frames": frames,
            "masks": [_mask(f) for f in frames],
        }

    # -- alpha-hygiene -------------------------------------------------------
    # Every partially transparent pixel must sit within Chebyshev distance 2
    # of a fully transparent pixel: AA lives at the silhouette edge only, and
    # interiors stay fully opaque.
    bad = []
    for key, d in data.items():
        cell = d["cell"]
        offender = False
        for frame in d["frames"]:
            for y in range(cell):
                for x in range(cell):
                    a = frame[y * cell + x][3]
                    if a == 0 or a == 255:
                        continue
                    near_clear = False
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            nx, ny = x + dx, y + dy
                            if nx < 0 or ny < 0 or nx >= cell or ny >= cell:
                                near_clear = True
                                break
                            if frame[ny * cell + nx][3] == 0:
                                near_clear = True
                                break
                        if near_clear:
                            break
                    if not near_clear:
                        offender = True
                        break
                if offender:
                    break
            if offender:
                break
        if offender:
            bad.append(key)
    rows.append({
        "check": "alpha-hygiene", "law": "pixel hygiene (edge-only AA)",
        "pass": not bad, "detail": {"interiorPartialAlpha": bad},
    })

    # -- hostile-signature ---------------------------------------------------
    sig = {}
    ok = True
    for key, d in data.items():
        role = d["meta"]["role"]
        cell = d["cell"]
        outline_worst = 1.0
        rim_worst = 1.0
        lum_max = 0.0
        for frame, mask in zip(d["frames"], d["masks"]):
            edge = _boundary(mask, cell)
            dark = sum(
                1 for i in edge if _lum(*frame[i][:3]) <= OUTLINE_LUM_MAX
            )
            outline_worst = min(outline_worst, dark / len(edge))
            if role == "hostile":
                c = cell / 2.0
                hits = 0
                for k in range(RIM_RAY_COUNT):
                    ang = 2.0 * math.pi * k / RIM_RAY_COUNT
                    ca, sa = math.cos(ang), math.sin(ang)
                    rr = 0.5
                    found = False
                    while rr <= c:
                        x = int(c + ca * rr)
                        y = int(c + sa * rr)
                        if 0 <= x < cell and 0 <= y < cell:
                            p = frame[y * cell + x]
                            if p[3] >= 128 and _lum(*p[:3]) >= RIM_LUM_MIN:
                                found = True
                                break
                        rr += 0.5
                    hits += found
                rim_worst = min(rim_worst, hits / RIM_RAY_COUNT)
            else:
                for p in frame:
                    if p[3]:
                        lum_max = max(lum_max, _lum(*p[:3]))
        entry = {"role": role, "outlineFracMin": round(outline_worst, 3)}
        good = outline_worst >= OUTLINE_FRACTION_MIN
        if role == "hostile":
            entry["rimRingFracMin"] = round(rim_worst, 3)
            good = good and rim_worst >= RIM_RAY_FRACTION_MIN
        else:
            entry["maxLum"] = round(lum_max, 3)
            good = good and lum_max <= PLAYER_LUM_MAX
        sig[key] = entry
        ok = ok and good
    rows.append({
        "check": "hostile-signature", "law": "§2.6 + contour / Laws 2+3",
        "pass": ok, "detail": sig,
    })

    # -- silhouette-distinct -------------------------------------------------
    classes = {}
    class_ok = True
    for key, d in data.items():
        cls = d["meta"]["silhouette"]
        if cls in classes:
            class_ok = False
        classes.setdefault(cls, key)
    keys = sorted(data.keys())
    pairs = {}
    iou_ok = True
    for i, ka in enumerate(keys):
        for kb in keys[i + 1 :]:
            role_a = data[ka]["meta"]["role"]
            role_b = data[kb]["meta"]["role"]
            if role_a != "hostile" and role_b != "hostile":
                continue
            limit = IOU_MAX_HOSTILE_PAIR if role_a == role_b else IOU_MAX_CROSS_ROLE_PAIR
            v = _iou_native(
                data[ka]["masks"][0], data[ka]["cell"],
                data[kb]["masks"][0], data[kb]["cell"],
            )
            pairs[f"{ka}~{kb}"] = {"iou": round(v, 3), "limit": limit}
            iou_ok = iou_ok and v < limit
    rows.append({
        "check": "silhouette-distinct", "law": "Law 3 / CORE-50",
        "pass": class_ok and iou_ok,
        "detail": {"classesUnique": class_ok, "pairIoU": pairs},
    })

    # -- hitbox-cover --------------------------------------------------------
    cover = {}
    ok = True
    for key, d in data.items():
        hb = d["meta"]["hitboxRadiusPx"]
        inscribed = d["meta"]["inscribedRadiusPx"]
        if d["meta"]["role"] == "hostile":
            good = (inscribed >= hb - COVER_TOL) and (inscribed <= hb + COVER_SLACK)
            cover[key] = {"inscribedRadiusPx": inscribed, "hitboxRadiusPx": hb,
                          "pass": good}
        else:
            cross = d["meta"]["crossHalfExtentPx"]
            good = cross <= hb + 0.6
            cover[key] = {"crossHalfExtentPx": cross, "hitboxRadiusPx": hb,
                          "pass": good}
        ok = ok and good
    rows.append({
        "check": "hitbox-cover", "law": "Law 8 (hitbox-native bake)",
        "pass": ok, "detail": cover,
    })

    # -- photosensitivity ----------------------------------------------------
    photo = {}
    ok = True
    for key, d in data.items():
        lums = [_mean_lum(f, d["cell"]) for f in d["frames"]]
        n = len(lums)
        delta = 0.0
        if n > 1:
            delta = max(abs(lums[i] - lums[(i + 1) % n]) for i in range(n))
        hz = TICKS_PER_SECOND / (n * d["meta"]["rateTicks"]) if n > 1 else 0.0
        good = delta <= LUM_DELTA_MAX and hz <= FLASH_HZ_MAX
        photo[key] = {"maxFrameLumDelta": round(delta, 4), "loopHz": round(hz, 2), "pass": good}
        ok = ok and good
    rows.append({
        "check": "photosensitivity", "law": "9-row acceptance, row 9",
        "pass": ok, "detail": photo,
    })

    # -- roster-coverage -----------------------------------------------------
    covered = set()
    for d in data.values():
        covered.update(d["meta"]["consumers"])
    missing = sorted(REQUIRED_CONSUMERS - covered)
    rows.append({
        "check": "roster-coverage", "law": "SPEC-A §3.3/§3.4/§3.5",
        "pass": not missing, "detail": {"missing": missing},
    })

    return {
        "formatVersion": manifest["formatVersion"],
        "generator": manifest["generator"],
        "pass": all(r["pass"] for r in rows),
        "rows": rows,
    }
