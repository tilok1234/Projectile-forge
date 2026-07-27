"""The projectile family catalog.

Two tiers:

* **core** — 1:1 with the Phase A roster (planning docs/12 §3.3 weapon
  frames, §3.4 enemy roster, §3.5 elite). These are the families the game
  imports for M-FX; the roster-coverage check pins them. Blightcaster is
  absent on purpose: it fires no projectile (ground hazard — telegraph
  vocabulary this forge does not own).
* **extended** — the broad vocabulary for content beyond Phase A, one
  silhouette lane per CORE-44 role-grammar pressure (predictive, wave,
  spinner, radial, sweeper, siege, volley, paired, swarm) plus player
  frame candidates. The game imports ONLY what curation picks (same scope
  guard as the actor pack: the rest stays in the forge).

Design rules encoded here, enforced by forge.validate:

* Law 3 / CORE-50 — families differ by SHAPE/PATTERN first, never color
  alone. Silhouette classes are globally unique AND pairwise mask overlap
  (IoU at final on-screen size) stays under limits for every pair involving
  a hostile family.
* §2.6 hostile signature — ALL hostile families carry one shared treatment
  (bright 1px rim + hard bright core) and NO player family may carry it.
* Law 8 — sheets are baked hitbox-native: the centered inscribed opaque
  circle EQUALS the collision circle, silhouettes are solid, and the game
  draws them 1:1 with no runtime scaling (crisp pixels, uniform rim).
* Photosensitivity — animation is a gentle pulse or rotation; luminance
  deltas and loop rates are capped (≤ 3 Hz at 60 ticks/s).

Colors are REDUNDANT coding only: hostile bodies sit in a warm/danger range
and player in a cool muted range, but nothing may rely on it.

Shape parameters are authored in a nominal 32px/tile space; the renderer
measures each shape and re-rasterizes it at final size (see render.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import shapes

CELL = 32              # authoring space: px per tile (CORE-20)
TICKS_PER_SECOND = 60  # game sim rate — flash-rate math uses this

# The shared hostile signature (docs/12 §2.6 v0 rim+core, extended with a
# black contour): every shot wears a near-black 1px outline — the frame that
# keeps shots readable on light AND dark floors — and hostile shots
# additionally carry the bright rim just inside it plus the hard core.
# No player family may carry the rim or core.
SIGNATURE = {
    "outlineWidthPx": 1.1,
    "outlineColor": "#12100E",
    "rimWidthPx": 1.1,
    "rimColor": "#FFF3D6",
    "coreColor": "#FFE3A0",
    "coreRadiusFrac": 0.42,  # of the hitbox radius (the core marks the hit circle)
}

RIM_RGB = (255, 243, 214)
CORE_RGB = (255, 227, 160)
OUTLINE_RGB = (18, 16, 14)
PLAYER_EDGE = (62, 79, 96)


@dataclass(frozen=True)
class Family:
    key: str
    role: str                    # "player" | "hostile"
    tier: str                    # "core" | "extended"
    silhouette: str              # declared silhouette class — globally unique
    consumers: tuple             # roster entries (core) or grammar/reserved tags
    hitbox_radius_tiles: float
    body_rgb: tuple              # redundant color channel, never load-bearing
    frames: int = 4
    rate_ticks: int = 10         # sim ticks per frame
    spin_symmetry: int = 0       # >0: rotation over one symmetry period/loop
    pulse_px: float = 0.0        # core-radius pulse amplitude (hostile shimmer)
    pattern: str = ""            # interior paint: "" | "rings"
    edge_rgb: tuple = PLAYER_EDGE
    sdf: object = field(default=None, compare=False)  # (x, y, phase) -> distance

    @property
    def hitbox_radius_px(self) -> float:
        return self.hitbox_radius_tiles * CELL


# --- core player ------------------------------------------------------------

def _longbolt(x, y, _p):
    return shapes.sd_capsule_x(x, y, 10.5, 2.4)

def _scattercast(x, y, _p):
    return shapes.sd_circle(x, y, 4.6)

def _wheelblade(x, y, p):
    rot = p * (2.0 * math.pi / 3.0)
    c, s = math.cos(rot), math.sin(rot)
    return shapes.sd_star(x * c - y * s, x * s + y * c, 10.5, 3.0, 2.3)

# --- core hostile -----------------------------------------------------------

def _husk_dart(x, y, _p):
    return shapes.sd_teardrop_x(x, y, -5.5, 7.5, 6.0, 1.5)

def _lead_needle(x, y, _p):
    return shapes.sd_rhombus_x(x, y, 13.0, 3.5)

def _fan_wedge(x, y, _p):
    # Swallowtail: a shallow notch in the blunt leading face. Distinctive in
    # its own right, and it removes silhouette area exactly where the
    # boulder disc and the needle overlap the wedge (both pairs sat at the
    # 0.55 IoU limit with a plain triangle).
    body = shapes.sd_triangle_isosceles_back(x, y, -11.0, 8.0, 7.85)
    notch = shapes.sd_triangle_isosceles_back(x, y, 3.8, 8.6, 2.9)
    return shapes.sd_subtract(body, notch)

def _ring_roundel(x, y, _p):
    return shapes.sd_roundel(x, y, 9.2)

def _warden_star(x, y, p):
    # Rest pose offset 22.5 deg: a spinning shot has no privileged
    # orientation, and the offset keeps the canonical frame-0 silhouette off
    # the needle/cross axes.
    rot = p * (math.pi / 2.0) + math.pi / 8.0
    c, s = math.cos(rot), math.sin(rot)
    return shapes.sd_star4(x * c - y * s, x * s + y * c, 10.5, 3.2)

# --- extended hostile (one lane per role-grammar pressure) ------------------

def _comet(x, y, _p):
    # Small round head leading, long thin tail trailing — the fast
    # predictive shot reads direction instantly, and the slim profile keeps
    # it out of the wedge/dart mass lanes.
    return shapes.sd_teardrop_x(-x, y, -4.5, 5.2, 10.0, 1.0)

def _crescent(x, y, _p):
    return shapes.sd_crescent_x(x, y, 9.0, 10.0, 6.3)

def _cross_plus(x, y, p):
    # Rest pose is the saltire (45 deg): arms diagonal, unmistakable next to
    # the axial star4 points at every phase.
    rot = p * (math.pi / 2.0) + math.pi / 4.0
    return shapes.sd_cross(x, y, 9.5, 3.5, rot)

def _hex_star(x, y, p):
    rot = p * (math.pi / 3.0)
    c, s = math.cos(rot), math.sin(rot)
    # Sharp points (m close to n): long spikes, small body — nothing like
    # the boulder/roundel disc lane.
    return shapes.sd_star(x * c - y * s, x * s + y * c, 10.0, 6.0, 4.2)

def _bar_sweep(x, y, _p):
    return shapes.sd_capsule_y(x, y, 7.5, 3.2)

def _meteor(x, y, _p):
    # Tri-lobed heavy rock. A plain disc was the aggressor in most measured
    # pairs (any convex blob CONTAINS the mid-size shapes and their IoU
    # saturates); the three fat lobes keep the siege identity and break the
    # containment.
    return shapes.sd_star(x, y, 11.0, 3.0, 2.2)

def _shard(x, y, _p):
    return shapes.sd_triangle_point_forward(x, y, 7.5, -5.5, 1.8)

def _twin_orb(x, y, p):
    # A slowly counter-rotating binary pair, diagonal at rest: the vertical
    # lane belongs to bar/crescent and the horizontal mass lanes to
    # dart/wedge/comet, so the pair lives between the axes and its rotation
    # makes "paired" readable in motion too.
    rot = p * math.pi + math.pi / 4.0  # 2-fold symmetry period per loop
    c, s = math.cos(rot), math.sin(rot)
    return shapes.sd_twin_orb(x * c - y * s, x * s + y * c, 4.5, 3.5)

def _spark(x, y, _p):
    # Tiny five-point spark: the swarm shot — a plain circle would mirror
    # the player pellet at equal size (measured IoU 1.0, a real catch).
    return shapes.sd_star(x, y, 7.0, 5.0, 3.8)



# --- extended player (future frame candidates) ------------------------------

def _lance(x, y, _p):
    return shapes.sd_rhombus_x(x, y, 12.0, 2.2)

def _plate(x, y, _p):
    # A square slab: a third player circle had no free size lane between the
    # roundel and boulder discs (measured IoU said so), so the heavy-frame
    # candidate is a plate instead.
    return shapes.sd_box(x, y, 4.5, 4.5)

def _sliver(x, y, _p):
    return shapes.sd_rhombus_x(x, y, 6.5, 1.8)


FAMILIES: tuple = (
    # ---- core player (Law 2: subordinate; no signature) --------------------
    Family(key="longbolt", role="player", tier="core", silhouette="bolt",
           consumers=("weapon:longbolt",), hitbox_radius_tiles=0.15,
           body_rgb=(110, 135, 160), frames=1, sdf=_longbolt),
    Family(key="scattercast", role="player", tier="core", silhouette="pellet",
           consumers=("weapon:scattercast",), hitbox_radius_tiles=0.12,
           body_rgb=(124, 148, 170), frames=1, sdf=_scattercast),
    Family(key="wheelblade", role="player", tier="core", silhouette="tri-blade",
           consumers=("weapon:wheelblade",), hitbox_radius_tiles=0.20,
           body_rgb=(138, 160, 180), frames=4, rate_ticks=8, spin_symmetry=3,
           sdf=_wheelblade),
    # ---- core hostile ------------------------------------------------------
    Family(key="husk_dart", role="hostile", tier="core", silhouette="teardrop",
           consumers=("enemy:husk_archer",), hitbox_radius_tiles=0.18,
           body_rgb=(170, 50, 22), pulse_px=0.4, sdf=_husk_dart),
    Family(key="lead_needle", role="hostile", tier="core", silhouette="needle",
           consumers=("enemy:leadshot",), hitbox_radius_tiles=0.18,
           body_rgb=(148, 30, 150), frames=1, sdf=_lead_needle),
    Family(key="fan_wedge", role="hostile", tier="core", silhouette="wedge",
           consumers=("enemy:fanmaw", "elite:yard_warden:p1"),
           hitbox_radius_tiles=0.20, body_rgb=(184, 100, 16), pulse_px=0.4,
           sdf=_fan_wedge),
    Family(key="ring_roundel", role="hostile", tier="core", silhouette="roundel",
           consumers=("enemy:ringer", "elite:yard_warden:p2"),
           hitbox_radius_tiles=0.20, body_rgb=(174, 24, 48), pulse_px=0.4,
           pattern="rings", sdf=_ring_roundel),
    Family(key="warden_star", role="hostile", tier="core", silhouette="star4",
           consumers=("elite:yard_warden:p3",), hitbox_radius_tiles=0.20,
           # 8 frames / 11.25-degree steps: sharp points alias more per step,
           # so the slower rotation keeps luminance deltas under the cap.
           body_rgb=(118, 46, 160), frames=8, spin_symmetry=4, sdf=_warden_star),
    # ---- extended hostile --------------------------------------------------
    Family(key="comet", role="hostile", tier="extended", silhouette="comet",
           consumers=("grammar:predictive-fast",), hitbox_radius_tiles=0.11,
           body_rgb=(200, 88, 14), pulse_px=0.4, sdf=_comet),
    Family(key="crescent", role="hostile", tier="extended", silhouette="crescent",
           consumers=("grammar:wave",), hitbox_radius_tiles=0.15,
           body_rgb=(172, 20, 110), pulse_px=0.4, sdf=_crescent),
    Family(key="cross_plus", role="hostile", tier="extended", silhouette="cross",
           consumers=("grammar:spinner",), hitbox_radius_tiles=0.24,
           body_rgb=(148, 42, 42), frames=12, rate_ticks=8, spin_symmetry=4,
           sdf=_cross_plus),
    Family(key="hex_star", role="hostile", tier="extended", silhouette="star6",
           consumers=("grammar:radial-heavy",), hitbox_radius_tiles=0.22,
           body_rgb=(190, 62, 20), frames=8, rate_ticks=10, spin_symmetry=6,
           sdf=_hex_star),
    Family(key="bar_sweep", role="hostile", tier="extended", silhouette="bar",
           consumers=("grammar:sweeper",), hitbox_radius_tiles=0.20,
           body_rgb=(136, 20, 62), pulse_px=0.4, sdf=_bar_sweep),
    Family(key="meteor", role="hostile", tier="extended", silhouette="meteor",
           consumers=("grammar:siege",), hitbox_radius_tiles=0.28,
           body_rgb=(130, 80, 34), pulse_px=0.4, sdf=_meteor),
    Family(key="shard", role="hostile", tier="extended", silhouette="shard",
           consumers=("grammar:volley",), hitbox_radius_tiles=0.08,
           body_rgb=(200, 38, 30), frames=1, sdf=_shard),
    Family(key="twin_orb", role="hostile", tier="extended", silhouette="twin",
           consumers=("grammar:paired",), hitbox_radius_tiles=0.18,
           body_rgb=(144, 38, 118), frames=8, rate_ticks=12, spin_symmetry=2,
           sdf=_twin_orb),
    Family(key="spark", role="hostile", tier="extended", silhouette="spark",
           consumers=("grammar:swarm",), hitbox_radius_tiles=0.10,
           body_rgb=(184, 50, 18), frames=1, sdf=_spark),
    # ---- extended player ---------------------------------------------------
    Family(key="lance", role="player", tier="extended", silhouette="lance",
           consumers=("reserved:frame-candidate",), hitbox_radius_tiles=0.15,
           body_rgb=(100, 130, 150), frames=1, sdf=_lance),
    Family(key="plate", role="player", tier="extended", silhouette="plate",
           consumers=("reserved:frame-candidate",), hitbox_radius_tiles=0.14,
           body_rgb=(120, 140, 155), frames=1, sdf=_plate),
    Family(key="sliver", role="player", tier="extended", silhouette="sliver",
           consumers=("reserved:frame-candidate",), hitbox_radius_tiles=0.10,
           body_rgb=(90, 115, 135), frames=1, sdf=_sliver),
)
