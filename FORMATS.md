# Projectile Forge package — format reference

Lookup material for writing an importer against `dist/projectileforge/`.
(As of formatVersion 1, 2026-07.)

## Files

    <family>.png                  one sheet per family
    projectileforge-manifest.json the machine-readable authority
    validation-report.json        the forge's own audit of this export
    preview.html                  self-contained visual audit page
    SHA256SUMS.txt                checksums of everything above

## Sheets

Single-loop-row layout (the same convention the retired spriteforge pack
used for projectiles): frames left-to-right in one row, transparent
background, RGBA8. Edges carry a one-pixel analytic anti-aliasing fringe;
interiors are fully opaque (the `alpha-hygiene` check enforces that partial
alpha exists only within 2px of fully transparent). Silhouette measurements
use the half-coverage contour (alpha >= 128).

Cells are **per-family and hitbox-native** (`families.<key>.cellPx`): each
family is rasterized at its final on-screen size, `renderScale` is always
1.0, and the game draws cells 1:1 in its 640x360 buffer — no runtime
scaling, so pixels stay crisp and the hostile rim is a uniform 1px
everywhere. Top-level `cell` (32) is the px-per-tile constant hitbox math
uses, not the sheet cell size.

**Orientation: shapes point +X.** Rotate the instance to the travel
direction; there are no per-direction rows. Rotation-symmetric families
(pellet, roundel) are rotation-safe trivially; spinning families
(`wheelblade`, `warden_star`) animate one symmetry period per loop so
rotation + animation compose without a visible seam.

## projectileforge-manifest.json

Top level: `formatVersion` (1), `generator`, `cell` (32), `orientation`
("+x"), `ticksPerSecond` (60), `hostileSignature`, `renderRules`,
`families`.

`hostileSignature` — the shared treatment parameters (`rimWidthPx`,
`rimColor`, `coreColor`, `coreRadiusFrac`). It is baked into the hostile
sheets, and shipped here so an EffectLibrary that prefers to apply the
signature as a runtime treatment (shader/outline pass) can reproduce it
exactly and stay pixel-consistent with the pack.

Per family (`families.<key>`):

| field | meaning |
|---|---|
| `role` | `player` \| `hostile` — picks the render rule and draw band (§2.5: hostile projectiles render in their own band above all friendly VFX, from a separate node) |
| `tier` | `core` (Phase A roster — what the game imports) \| `extended` (curation vocabulary) |
| `silhouette` | declared shape class — unique across the pack |
| `consumers` | roster entries firing this family (`weapon:*`, `enemy:*`, `elite:yard_warden:p*`) |
| `image` | sheet PNG |
| `frames` | frame count (1 = static) |
| `rateTicks` | sim ticks per frame; loop rate = 60 / (frames × rateTicks) Hz |
| `cellPx` | this family's (square) frame cell size |
| `hitboxRadiusTiles` / `hitboxRadiusPx` | the §3.3/§3.4 collision radius this family is authored against |
| `inscribedRadiusPx` | largest centered circle fully opaque in EVERY frame |
| `crossHalfExtentPx` | max opaque |y| extent (cross-axis, travel = +X) |
| `halfExtentPx` | max opaque distance from center |
| `renderScale` | always 1.0 — the scale is baked into the sheet |
| `bakeScale` | provenance: authoring-space -> screen factor used by the bake |
| `bodyColor` | redundant color channel — never load-bearing |

## Render rules (Law 8 / Law 2) — baked at export

- **hostile:** baked so the centered inscribed opaque circle EQUALS the
  collision circle (validator tolerance −0.3 px / +2.5 px, the slack coming
  from the raster pad). The visual covers the hitbox exactly; never render
  hostile smaller than authored.
- **player:** baked with the cross-axis capped at the hitbox — the visual
  never overstates the collision circle; the long axis is free (elongation
  along travel reads as motion; under-render is player-favorable).

Consumers draw each frame cell at `cellPx` screen px, centered on the
projectile's sim position, rotated to the travel direction. That's the whole
integration: no scale math at runtime.

Animation timing: advance `frame = (ticks_since_spawn / rateTicks) % frames`
from sim ticks so replays render identically; the view may interpolate
position but frame selection stays tick-pure.

## validation-report.json

`pass` (the verdict) + `rows[]`, one row per check
(`alpha-hygiene`, `hostile-signature`, `silhouette-distinct`, `hitbox-cover`,
`photosensitivity`, `roster-coverage`, `determinism`), each with `law`,
`pass`, and measured `detail`. Thresholds live in `forge/validate.py`:

- silhouette IoU (at in-game relative scale, canonical +X pose, frame 0):
  hostile~hostile < 0.55; hostile~player < 0.75 (hostile-vs-friendly
  discrimination is the signature's job — §2.6 — the IoU there is only a
  guard rail against near-identical outlines).
- hostile boundary luminance ≥ 0.80 on ≥ 85% of edge pixels; player
  boundary luminance ≤ 0.75 everywhere.
- per-frame mean-luminance delta ≤ 0.02; loop rate ≤ 3 Hz (flash safety).

These calibration numbers are forge-owned (not planning-repo law); tighten
them here, never loosen them to make a shape fit — reshape the family
instead (see the tuning history in git).

## Determinism

Everything is a pure function of `forge/families.py`: no RNG, no
timestamps, fixed zlib settings, filter-0 PNG rows. The build double-renders
and byte-compares as a report row; `SHA256SUMS.txt` pins the export. Treat
the package as a build artifact — regenerate rather than hand-edit.
