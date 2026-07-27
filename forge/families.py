"""The projectile family catalog.

One entry per shot family in the Wildshot Phase A roster (planning docs/12
§3.3 weapon frames, §3.4 enemy roster, §3.5 elite). Blightcaster is absent
on purpose: it fires no projectile (delayed ground hazard — that is telegraph
territory, a different vocabulary this forge does not own).

Design rules encoded here, enforced by forge.validate:

* Law 3 / CORE-50 — families differ by SHAPE/PATTERN first, never color
  alone. Every family declares a silhouette class; the validator additionally
  measures pairwise silhouette overlap (IoU at in-game relative scale) so two
  families can never quietly converge.
* §2.6 hostile signature — ALL hostile families carry one shared treatment
  (bright 1px rim + hard bright core, the v0 signature from the build plan)
  and NO friendly family may carry it. Baked into the sheets here; the same
  parameters ship in the manifest so the game can re-apply it as a shader
  treatment instead if EffectLibrary prefers.
* Law 2 — player shots are visually subordinate: muted flat bodies, darker
  edges, no rim, no hot core.
* Law 8 honesty — every hostile family publishes its centered inscribed
  opaque radius; rendering at scale = hitbox_radius_px / inscribed_radius_px
  guarantees the visual fully covers the collision circle. Silhouettes are
  SOLID (the Ringer roundel paints its ring pattern inside a solid disc —
  a hollow visual over a solid hitbox would manufacture unexplainable
  deaths).
* Photosensitivity (the 9-row acceptance's ninth row) — animation is a
  gentle pulse or rotation; the validator caps per-frame luminance delta and
  the loop's effective flash rate (≤ 3 Hz at 60 ticks/s).

Colors are REDUNDANT coding only: hostile bodies sit in a warm/danger range
and friendly in a cool muted range, but nothing may rely on it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import shapes

CELL = 32              # px per frame cell; 32 px = 1 tile (CORE-20)
TICKS_PER_SECOND = 60  # game sim rate — flash-rate math uses this

# The shared hostile signature (docs/12 §2.6, v0): bright 1px rim + hard core.
# One signature across every hostile family and the elite; absent from every
# friendly family. Shipped in the manifest verbatim.
SIGNATURE = {
    "rimWidthPx": 1.0,
    "rimColor": "#FFF3D6",
    "coreColor": "#FFE3A0",
    "coreRadiusFrac": 0.42,  # of the family's inscribed radius
}

RIM_RGB = (255, 243, 214)
CORE_RGB = (255, 227, 160)


@dataclass(frozen=True)
class Family:
    key: str
    role: str                    # "player" | "hostile"
    silhouette: str              # declared silhouette class — must be unique per role
    consumers: tuple             # which roster entries fire this family
    hitbox_radius_tiles: float   # from the §3.3/§3.4 tables
    body_rgb: tuple              # redundant color channel, never load-bearing
    edge_rgb: tuple              # friendly edge shade (hostile edge = signature rim)
    frames: int = 4
    rate_ticks: int = 10         # sim ticks per frame => 60/(frames*rate) loops/s
    spin_symmetry: int = 0       # >0: rotation animation over one symmetry period
    pulse_px: float = 0.0        # core-radius pulse amplitude (hostile shimmer)
    sdf: object = field(default=None, compare=False)  # (x, y, frame_phase) -> distance

    @property
    def hitbox_radius_px(self) -> float:
        return self.hitbox_radius_tiles * CELL


def _longbolt(x: float, y: float, _p: float) -> float:
    return shapes.sd_capsule_x(x, y, 10.5, 2.4)


def _scattercast(x: float, y: float, _p: float) -> float:
    return shapes.sd_circle(x, y, 4.6)


def _wheelblade(x: float, y: float, p: float) -> float:
    # Tri-point shuriken: reads as a spinning blade, not a puff (the earlier
    # notched-disc draft read as a cloud at 32px).
    rot = p * (2.0 * math.pi / 3.0)  # one 3-fold symmetry period per loop
    c, s = math.cos(rot), math.sin(rot)
    return shapes.sd_star(x * c - y * s, x * s + y * c, 10.5, 3.0, 2.3)


def _husk_dart(x: float, y: float, _p: float) -> float:
    # Stubby: mass at the round back, short point — the long-thin lane
    # belongs to lead_needle (silhouette-distinct by proportion AND class).
    return shapes.sd_teardrop_x(x, y, -5.5, 7.5, 6.0, 1.5)


def _lead_needle(x: float, y: float, _p: float) -> float:
    return shapes.sd_rhombus_x(x, y, 13.0, 3.0)


def _fan_wedge(x: float, y: float, _p: float) -> float:
    # Blunt face forward: fan shots read as a widening wall, and the straight
    # leading edge is unmistakable next to the dart's point.
    return shapes.sd_triangle_isosceles_back(x, y, -10.0, 8.0, 8.0)


def _ring_roundel(x: float, y: float, _p: float) -> float:
    return shapes.sd_roundel(x, y, 9.2)


def _warden_star(x: float, y: float, p: float) -> float:
    rot = p * (math.pi / 2.0)  # one 4-fold symmetry period per loop
    c, s = math.cos(rot), math.sin(rot)
    return shapes.sd_star4(x * c - y * s, x * s + y * c, 12.0, 2.8)


FAMILIES: tuple = (
    # -- player (Law 2: subordinate; no signature) ---------------------------
    Family(
        key="longbolt", role="player", silhouette="bolt",
        consumers=("weapon:longbolt",), hitbox_radius_tiles=0.15,
        body_rgb=(110, 135, 160), edge_rgb=(62, 79, 96),
        frames=1, rate_ticks=10, sdf=_longbolt,
    ),
    Family(
        key="scattercast", role="player", silhouette="pellet",
        consumers=("weapon:scattercast",), hitbox_radius_tiles=0.12,
        body_rgb=(124, 148, 170), edge_rgb=(62, 79, 96),
        frames=1, rate_ticks=10, sdf=_scattercast,
    ),
    Family(
        key="wheelblade", role="player", silhouette="tri-blade",
        consumers=("weapon:wheelblade",), hitbox_radius_tiles=0.20,
        body_rgb=(138, 160, 180), edge_rgb=(62, 79, 96),
        frames=4, rate_ticks=8, spin_symmetry=3, sdf=_wheelblade,
    ),
    # -- hostile (one shared signature; shapes pairwise distinct) ------------
    Family(
        key="husk_dart", role="hostile", silhouette="teardrop",
        consumers=("enemy:husk_archer",), hitbox_radius_tiles=0.18,
        body_rgb=(140, 44, 26), edge_rgb=(0, 0, 0),
        frames=4, rate_ticks=10, pulse_px=0.6, sdf=_husk_dart,
    ),
    Family(
        key="lead_needle", role="hostile", silhouette="needle",
        consumers=("enemy:leadshot",), hitbox_radius_tiles=0.18,
        body_rgb=(122, 30, 122), edge_rgb=(0, 0, 0),
        # Static: on a 6px-wide lance the core pulse reads as strobing, and a
        # dead-steady shot fits the predictive sniper's character.
        frames=1, rate_ticks=10, sdf=_lead_needle,
    ),
    Family(
        key="fan_wedge", role="hostile", silhouette="wedge",
        consumers=("enemy:fanmaw", "elite:yard_warden:p1"), hitbox_radius_tiles=0.20,
        body_rgb=(150, 84, 20), edge_rgb=(0, 0, 0),
        frames=4, rate_ticks=10, pulse_px=0.6, sdf=_fan_wedge,
    ),
    Family(
        key="ring_roundel", role="hostile", silhouette="roundel",
        consumers=("enemy:ringer", "elite:yard_warden:p2"), hitbox_radius_tiles=0.20,
        body_rgb=(148, 26, 44), edge_rgb=(0, 0, 0),
        frames=4, rate_ticks=10, pulse_px=0.6, sdf=_ring_roundel,
    ),
    Family(
        key="warden_star", role="hostile", silhouette="star4",
        consumers=("elite:yard_warden:p3",), hitbox_radius_tiles=0.20,
        body_rgb=(96, 40, 128), edge_rgb=(0, 0, 0),
        # 6 frames / 15° steps: the slower rotation keeps the per-frame
        # luminance delta under the photosensitivity cap.
        frames=6, rate_ticks=10, spin_symmetry=4, sdf=_warden_star,
    ),
)
