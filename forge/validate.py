"""Pack validator: the readability laws as executable checks.

Runs on the DECODED pack (manifest + PNG bytes), never on in-memory renderer
state, so `python -m forge validate` audits what is actually on disk. Every
check row lands in validation-report.json with measured values — acceptance
is a record, not a vibe.

Rows (mapped to the binding constraints):
* alpha-binary        — crisp Nearest-friendly pixels; alpha strictly {0,255}
* hostile-signature   — §2.6: every hostile silhouette edge wears the bright
                        rim; NO friendly edge is bright (Law 2/3)
* silhouette-distinct — Law 3 / CORE-50: declared silhouette classes unique,
                        AND measured pairwise mask overlap (IoU at in-game
                        relative scale) under threshold for every pair
                        involving a hostile family — shape first, color never
* hitbox-cover        — Law 8: hostile inscribed radius supports the
                        scale = hitbox/inscribed rule without exceeding the
                        oversize cap (visuals may not dwarf their hitboxes)
* photosensitivity    — 9-row acceptance, row nine: per-frame mean-luminance
                        delta and loop flash rate capped (≤ 3 Hz at 60 t/s)
* roster-coverage     — every shot-firing §3.3/§3.4/§3.5 roster entry has a
                        family; catalog drift fails loudly
"""

from __future__ import annotations

from .families import CELL, TICKS_PER_SECOND

# Hostile families must separate from EACH OTHER by naked silhouette — shape
# alone, color and treatment gone (Law 3 / CORE-50 strict reading).
IOU_MAX_HOSTILE_PAIR = 0.55
# Hostile-vs-friendly discrimination is carried by the shared signature (§2.6
# — that is what it is FOR; the M6 Law 3 acceptance row tests it with the
# treatment applied at stress density). The silhouette check on these pairs
# is only a guard rail against near-identical outlines.
IOU_MAX_CROSS_ROLE_PAIR = 0.75
RIM_LUM_MIN = 0.80          # hostile boundary pixels must be at least this bright
RIM_FRACTION_MIN = 0.85     # ...for at least this fraction of the boundary
FRIENDLY_EDGE_LUM_MAX = 0.75
OVERSIZE_CAP = 2.2          # hostile render scale (hitbox/inscribed) ceiling
LUM_DELTA_MAX = 0.02        # mean-luminance step between consecutive frames
FLASH_HZ_MAX = 3.0

REQUIRED_CONSUMERS = {
    "weapon:longbolt", "weapon:scattercast", "weapon:wheelblade",
    "enemy:husk_archer", "enemy:leadshot", "enemy:fanmaw", "enemy:ringer",
    "elite:yard_warden:p1", "elite:yard_warden:p2", "elite:yard_warden:p3",
}


def _lum(r: int, g: int, b: int) -> float:
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _frames_of(sheet: tuple, frames: int) -> list:
    """Split a single-row sheet (w, h, rgba) into per-frame pixel lists."""
    w, h, px = sheet
    out = []
    for i in range(frames):
        frame = []
        for y in range(CELL):
            for x in range(CELL):
                j = (y * w + i * CELL + x) * 4
                frame.append((px[j], px[j + 1], px[j + 2], px[j + 3]))
        out.append(frame)
    return out


def _mask(frame: list) -> list:
    return [1 if p[3] == 255 else 0 for p in frame]


def _boundary(mask: list) -> list:
    out = []
    for y in range(CELL):
        for x in range(CELL):
            if not mask[y * CELL + x]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if nx < 0 or ny < 0 or nx >= CELL or ny >= CELL or not mask[ny * CELL + nx]:
                    out.append(y * CELL + x)
                    break
    return out


def _mean_lum(frame: list) -> float:
    total = 0.0
    for r, g, b, a in frame:
        if a:
            total += _lum(r, g, b)
    return total / (CELL * CELL)


def _iou_at_scale(mask_a: list, scale_a: float, mask_b: list, scale_b: float) -> float:
    """Overlap of two silhouettes rendered at their in-game scales, both
    centered — the canonical Law 3 comparison pose."""
    grid = 96
    half = grid / 2.0
    c = CELL / 2.0
    inter = union = 0
    for gy in range(grid):
        for gx in range(grid):
            sx = gx + 0.5 - half
            sy = gy + 0.5 - half
            a = b = 0
            ax = int(sx / scale_a + c)
            ay = int(sy / scale_a + c)
            if 0 <= ax < CELL and 0 <= ay < CELL:
                a = mask_a[ay * CELL + ax]
            bx = int(sx / scale_b + c)
            by = int(sy / scale_b + c)
            if 0 <= bx < CELL and 0 <= by < CELL:
                b = mask_b[by * CELL + bx]
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
        sheet = sheets[fam["image"]]
        frames = _frames_of(sheet, fam["frames"])
        data[key] = {
            "meta": fam,
            "frames": frames,
            "masks": [_mask(f) for f in frames],
        }

    # -- alpha-binary --------------------------------------------------------
    bad = []
    for key, d in data.items():
        for frame in d["frames"]:
            if any(p[3] not in (0, 255) for p in frame):
                bad.append(key)
                break
    rows.append({
        "check": "alpha-binary", "law": "pixel hygiene",
        "pass": not bad, "detail": {"nonBinaryAlpha": bad},
    })

    # -- hostile-signature ---------------------------------------------------
    sig = {}
    ok = True
    for key, d in data.items():
        role = d["meta"]["role"]
        worst = 1.0 if role == "hostile" else 0.0
        for frame, mask in zip(d["frames"], d["masks"]):
            edge = _boundary(mask)
            lums = [_lum(*frame[i][:3]) for i in edge]
            if role == "hostile":
                frac = sum(1 for v in lums if v >= RIM_LUM_MIN) / len(lums)
                worst = min(worst, frac)
            else:
                worst = max(worst, max(lums))
        if role == "hostile":
            sig[key] = {"role": role, "rimFractionMin": round(worst, 3)}
            ok = ok and worst >= RIM_FRACTION_MIN
        else:
            sig[key] = {"role": role, "edgeLumMax": round(worst, 3)}
            ok = ok and worst <= FRIENDLY_EDGE_LUM_MAX
    rows.append({
        "check": "hostile-signature", "law": "§2.6 / Laws 2+3",
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
            v = _iou_at_scale(
                data[ka]["masks"][0], data[ka]["meta"]["renderScale"],
                data[kb]["masks"][0], data[kb]["meta"]["renderScale"],
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
        if d["meta"]["role"] != "hostile":
            continue
        inscribed = d["meta"]["inscribedRadiusPx"]
        scale = d["meta"]["renderScale"]
        good = inscribed > 0 and scale <= OVERSIZE_CAP
        cover[key] = {
            "inscribedRadiusPx": inscribed,
            "hitboxRadiusPx": d["meta"]["hitboxRadiusPx"],
            "renderScale": scale, "pass": good,
        }
        ok = ok and good
    rows.append({
        "check": "hitbox-cover", "law": "Law 8",
        "pass": ok, "detail": cover,
    })

    # -- photosensitivity ----------------------------------------------------
    photo = {}
    ok = True
    for key, d in data.items():
        lums = [_mean_lum(f) for f in d["frames"]]
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
