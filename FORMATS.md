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
used for projectiles): frames left-to-right in one row, each cell
`cell` × `cell` px (32 = one tile, CORE-20), transparent background, RGBA8,
alpha strictly {0, 255}. Intended for Nearest filtering.

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
| `silhouette` | declared shape class — unique across the pack |
| `consumers` | roster entries firing this family (`weapon:*`, `enemy:*`, `elite:yard_warden:p*`) |
| `image` | sheet PNG |
| `frames` | frame count (1 = static) |
| `rateTicks` | sim ticks per frame; loop rate = 60 / (frames × rateTicks) Hz |
| `hitboxRadiusTiles` / `hitboxRadiusPx` | the §3.3/§3.4 collision radius this family is authored against |
| `inscribedRadiusPx` | largest centered circle fully opaque in EVERY frame |
| `crossHalfExtentPx` | max opaque |y| extent (cross-axis, travel = +X) |
| `halfExtentPx` | max opaque distance from center |
| `renderScale` | the precomputed scale below |
| `bodyColor` | redundant color channel — never load-bearing |

## Render-scale rules (Law 8 / Law 2)

- **hostile:** `scale = hitboxRadiusPx / inscribedRadiusPx`. At this scale
  the opaque body covers the collision circle exactly — hostile visuals
  never under-state the threat. Never render hostile below this scale.
  An oversize cap (scale ≤ 2.2) is enforced at export.
- **player:** `scale = min(1, hitboxRadiusPx / crossHalfExtentPx)` — the
  cross-axis never overstates the hitbox; the long axis is free (elongation
  along travel reads as motion; under-render is player-favorable).

`renderScale` in the manifest is precomputed from these rules; consumers can
either trust it or re-derive it from the published measurements. If the
game keeps its current convention (unit quad scaled to `radius * TILE`,
texture spanning the collision diameter), multiply that transform by
`renderScale × cell / (2 × hitboxRadiusPx)` — or simply draw the cell at
`cell × renderScale` px and rotate to velocity.

Animation timing: advance `frame = (ticks_since_spawn / rateTicks) % frames`
from sim ticks so replays render identically; the view may interpolate
position but frame selection stays tick-pure.

## validation-report.json

`pass` (the verdict) + `rows[]`, one row per check
(`alpha-binary`, `hostile-signature`, `silhouette-distinct`, `hitbox-cover`,
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
