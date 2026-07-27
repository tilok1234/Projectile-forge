"""Pack assembly: render every family, emit sheets + manifest + validation
report + preview + checksums into the output directory.

The pack is a build artifact in the TileForge sense: regenerate, never
hand-edit. Same code + same catalog => byte-identical output (asserted by
the double-build determinism row in the report and by tests).
"""

from __future__ import annotations

import hashlib
import json
import os

from . import pngio, validate
from .families import CELL, FAMILIES, SIGNATURE, TICKS_PER_SECOND
from .preview import build_preview
from .render import render_family

GENERATOR = "projectile-forge 0.1.0"
FORMAT_VERSION = 1


def build_pack() -> tuple:
    """Render everything. Returns (manifest dict, sheets dict of
    filename -> (w, h, rgba), png dict of filename -> bytes)."""
    manifest = {
        "formatVersion": FORMAT_VERSION,
        "generator": GENERATOR,
        "cell": CELL,
        "orientation": "+x",
        "ticksPerSecond": TICKS_PER_SECOND,
        "hostileSignature": dict(SIGNATURE),
        "renderRules": {
            "baked": "sheets are HITBOX-NATIVE: each family is rasterized at "
                     "its final on-screen size (renderScale = 1.0). Draw cells "
                     "1:1 in the 640x360 buffer, rotated to travel — no "
                     "runtime scaling, crisp Nearest pixels, uniform 1px rim.",
            "hostile": "the centered inscribed opaque circle EQUALS the "
                       "collision circle (Law 8): the visual covers the hitbox "
                       "exactly; never render hostile smaller than authored",
            "player": "cross-axis capped at the hitbox (Law 2; under-render "
                      "is player-favorable), long-axis free — elongation "
                      "reads as motion",
        },
        "families": {},
    }
    sheets = {}
    pngs = {}
    for fam in FAMILIES:
        rendered = render_family(fam)
        image = f"{fam.key}.png"
        w, h, px = rendered.sheet_rgba()
        sheets[image] = (w, h, px)
        pngs[image] = pngio.write_rgba(w, h, px)
        manifest["families"][fam.key] = {
            "role": fam.role,
            "tier": fam.tier,
            "silhouette": fam.silhouette,
            "consumers": list(fam.consumers),
            "image": image,
            "frames": fam.frames,
            "rateTicks": fam.rate_ticks,
            "cellPx": rendered.cell,
            "hitboxRadiusTiles": fam.hitbox_radius_tiles,
            "hitboxRadiusPx": round(fam.hitbox_radius_px, 3),
            "inscribedRadiusPx": rendered.inscribed_px,
            "crossHalfExtentPx": rendered.cross_half_px,
            "halfExtentPx": round(rendered.half_extent_px, 3),
            "renderScale": 1.0,
            "bakeScale": round(rendered.bake_scale, 4),
            "bodyColor": "#%02X%02X%02X" % fam.body_rgb,
        }
    return manifest, sheets, pngs


def write_pack(out_dir: str) -> dict:
    """Full export. Returns the validation report (raises if it fails)."""
    manifest, sheets, pngs = build_pack()

    # Determinism proof: a second independent build must be byte-identical.
    manifest2, _, pngs2 = build_pack()
    identical = pngs == pngs2 and manifest == manifest2

    report = validate.validate_pack(manifest, sheets)
    report["rows"].append({
        "check": "determinism", "law": "reproducible build artifact",
        "pass": identical, "detail": {"doubleBuildIdentical": identical},
    })
    report["pass"] = report["pass"] and identical

    os.makedirs(out_dir, exist_ok=True)
    for name, blob in sorted(pngs.items()):
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(blob)
    _write_json(os.path.join(out_dir, "projectileforge-manifest.json"), manifest)
    _write_json(os.path.join(out_dir, "validation-report.json"), report)
    with open(os.path.join(out_dir, "preview.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(build_preview(manifest, pngs))

    sums = []
    for name in sorted(os.listdir(out_dir)):
        if name == "SHA256SUMS.txt":
            continue
        with open(os.path.join(out_dir, name), "rb") as f:
            sums.append(f"{hashlib.sha256(f.read()).hexdigest()}  {name}")
    with open(os.path.join(out_dir, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(sums) + "\n")
    return report


def load_pack(pack_dir: str) -> tuple:
    """Read a pack back from disk for auditing. Returns (manifest, sheets)."""
    with open(os.path.join(pack_dir, "projectileforge-manifest.json"), "r", encoding="utf-8") as f:
        manifest = json.load(f)
    sheets = {}
    for fam in manifest["families"].values():
        with open(os.path.join(pack_dir, fam["image"]), "rb") as f:
            sheets[fam["image"]] = pngio.read_rgba(f.read())
    return manifest, sheets


def _write_json(path: str, obj: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")
