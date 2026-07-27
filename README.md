# Projectile Forge

Deterministic projectile sprite pack generator for **Wildshot Adventures** —
a top-down 2D bullet-hell open-world game. The forge's whole job is three
words: **readable, simple, consistent**. Every projectile the game fires
comes out of one generator that has the readability laws compiled into it,
so the projectile language cannot drift, and every export proves its own
compliance in a validation report.

This is a sibling tool to TileForge: it produces a **pack** (sprite sheets +
machine-readable manifest + validation report + preview) that the game repo
imports. The pack is a build artifact — regenerate it, never hand-edit it.

## Relationship to the other repos

- **Game repo** (`Wildshot-Adventures`) — consumes the pack. Read-only from
  here; the game-side importer/EffectLibrary wiring is game-repo work
  (M-FX/M6 scope). Today its `projectile_view.gd` renders placeholder
  spheres and explicitly defers the per-family split to "the M-FX effects
  language" — this pack is a candidate source for exactly that. The retired
  spriteforge pack took the old projectile sheets with it; the assembler
  pack ships actors only, so projectile sheets currently have no source but
  this one.
- **Planning repo** (`Wildshot_adventures_pmanning`) — design authority.
  This forge implements the projectile-visual constraints recorded there
  (docs/12 §2.6, §3.3–3.5; CORE-50/51). On any conflict between this repo
  and the planning docs: **stop and flag — the planning repo wins.**
  Numeric thresholds invented by this forge (IoU limits, rim luminance,
  photosensitivity caps) are forge-owned calibration, documented in
  `FORMATS.md`, and are offered to — not imposed on — the planning repo.

## Quickstart

```
python3 -m forge build              # render pack into dist/projectileforge/
python3 -m forge validate           # re-audit the pack from disk
python3 -m unittest discover tests  # good pack passes + canaries fail
```

Stdlib-only Python 3; no dependencies. Same code + same catalog =>
byte-identical output (a determinism row in the report double-builds and
compares; `SHA256SUMS.txt` pins the export).

Open `dist/projectileforge/preview.html` in a browser for the human half:
animated cards per family, a grayscale toggle (the colorblind / Law 3
shape-first audit), and a deterministic stress field (player spam under
hostile fire — hostile must stay legible above all of it).

## The rules the forge enforces

Every export writes `validation-report.json`; the build fails if any row
fails. The same checks run in CI-style tests with MUST-FAIL canaries
(a validator that never fails proves nothing).

| Row | Rule (source) |
|---|---|
| `hostile-signature` | One shared hostile signature — bright 1px rim + hard bright core — on **every** hostile family, on **no** player family (docs/12 §2.6 v0; Laws 2/3). |
| `silhouette-distinct` | Families differ by shape/pattern, never color alone (CORE-50). Declared silhouette classes are unique **and** pairwise mask overlap (IoU at in-game relative scale) stays under limits — measured, not self-described. |
| `hitbox-cover` | Hostile visuals may never render smaller than their hitboxes (Law 8). Sheets are baked **hitbox-native**: the centered inscribed opaque circle equals the collision circle (small documented slack), player cross-axis never exceeds its hitbox, and the game draws everything 1:1 — no runtime scaling, crisp pixels, uniform 1px rim. |
| `photosensitivity` | The 9-row acceptance's ninth row: per-frame mean-luminance delta capped, loop flash rate ≤ 3 Hz at 60 ticks/s. |
| `alpha-hygiene` | Anti-aliasing is edge-only: a 1px analytic AA fringe at the silhouette boundary, fully opaque interiors — smooth edges that can never decay into mushy translucent sprites. |
| `roster-coverage` | Every shot-firing roster entry (§3.3 weapons, §3.4 enemies, §3.5 elite phases) has a family; catalog drift fails loudly. |
| `determinism` | Double-build byte-identity. |

Design decisions living in code rather than checks:

- **Solid silhouettes.** The Ringer roundel paints its ring pattern inside
  a solid disc — a hollow visual over a solid circular hitbox invites
  standing in the hole and dying to it (an unexplainable death, Law 8).
- **No RNG anywhere.** Every pixel is a pure function of the catalog.
  Animation is gentle rotation or a small core pulse, authored per family.
- **Player shots subordinate** (Law 2): muted flat bodies, darker edges,
  cross-axis capped at the hitbox (under-rendering friendly visuals is
  player-favorable and Law-8-benign; elongation along travel is free).
- **Hitbox-native bake.** Every family is measured (radial marching — SDF
  center values lie on union seams) and re-rasterized at its final
  on-screen size, so the pack needs no runtime scaling and the signature
  rim stays exactly one pixel on every family.
- **Color is redundant coding only.** Hostile bodies sit in a warm range,
  player in a cool muted range — but the grayscale toggle in the preview is
  the real test, and the IoU check doesn't look at color at all.

## The families

**Core tier** — 1:1 with the Phase A roster; this is what the game imports
for M-FX:

| key | role | silhouette | fires it |
|---|---|---|---|
| `longbolt` | player | bolt | Longbolt weapon frame |
| `scattercast` | player | pellet | Scattercast weapon frame |
| `wheelblade` | player | tri-blade | Wheelblade weapon frame (spins) |
| `husk_dart` | hostile | teardrop | Husk Archer aimed shot |
| `lead_needle` | hostile | needle | Leadshot predictive shot |
| `fan_wedge` | hostile | wedge | Fanmaw fan; Yard Warden P1 |
| `ring_roundel` | hostile | roundel | Ringer radial; Yard Warden P2 |
| `warden_star` | hostile | star4 | Yard Warden P3 chase bursts (spins) |

**Extended tier** — the broad vocabulary for content beyond Phase A, one
silhouette lane per CORE-44 role-grammar pressure. The game imports ONLY
what curation picks (the same scope guard as the actor pack — the rest
stays in the forge):

| key | role | silhouette | grammar lane |
|---|---|---|---|
| `comet` | hostile | comet (head leads, tail trails) | predictive-fast |
| `crescent` | hostile | crescent, horns forward | wave |
| `cross_plus` | hostile | cross, saltire rest pose (spins) | spinner |
| `hex_star` | hostile | six-point star (spins) | radial-heavy |
| `bar_sweep` | hostile | cross-axis bar | sweeper |
| `boulder` | hostile | large disc | siege |
| `shard` | hostile | tiny point-forward sliver | volley |
| `twin_orb` | hostile | binary pair (counter-rotates) | paired |
| `spark` | hostile | tiny five-point star | swarm |
| `lance` | player | long thin lance | frame candidate |
| `plate` | player | square slab | frame candidate |
| `sliver` | player | tiny sliver | frame candidate |

Blightcaster is deliberately absent: it fires no projectile (delayed ground
hazard — telegraph vocabulary, which this forge does not own). Telegraph
rings, arm-progress indicators, muzzle/impact effects, and the audio cue map
are the remaining M-FX/M6 items and are out of scope here by design.

## Pack format

See `FORMATS.md` for the manifest schema, sheet layout, and the exact
render-scale rules an importer should apply.
