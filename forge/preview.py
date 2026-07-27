"""preview.html generator: a self-contained visual audit page.

Robustness rules learned the hard way:
* ALL content is static HTML rendered here in Python — every family card and
  sheet image is visible with JavaScript disabled or blocked (sandboxed
  viewers often block scripts; a page whose DOM is script-built reads as
  broken there).
* The grayscale audit toggle is pure CSS (:checked sibling selector) so the
  Law 3 shape-first check works everywhere.
* Canvas animation is a progressive enhancement: hidden by default, shown
  when the script runs and stamps `js` on <html>.
* Nothing external is referenced (sheets inline as data URIs); no fixed
  pixel widths that could force horizontal overflow in narrow viewers.

Sheets are hitbox-native (renderScale 1.0): the animated canvases and the
stress field draw them 1:1 — exactly what the game's 640x360 buffer shows —
zoomed 2x for the eye via CSS.
"""

from __future__ import annotations

import base64
import json

_SECTIONS = (
    ("player", "core", "Player — core weapon frames (subordinate, Law 2)"),
    ("player", "extended", "Player — future frame candidates"),
    ("hostile", "core", "Hostile — Phase A roster (one shared signature, §2.6 / Law 3)"),
    ("hostile", "extended", "Hostile — extended vocabulary (one lane per role-grammar pressure)"),
)


def build_preview(manifest: dict, pngs: dict) -> str:
    metas = {}
    sections = {(role, tier): [] for role, tier, _ in _SECTIONS}
    for key in sorted(manifest["families"]):
        fam = manifest["families"][key]
        uri = "data:image/png;base64," + base64.b64encode(pngs[fam["image"]]).decode("ascii")
        metas[key] = {
            "role": fam["role"],
            "frames": fam["frames"],
            "rateTicks": fam["rateTicks"],
            "cellPx": fam["cellPx"],
        }
        sections[(fam["role"], fam["tier"])].append(_card(key, fam, uri))
    payload = json.dumps(
        {"tps": manifest["ticksPerSecond"], "families": metas}, sort_keys=True
    )
    body = []
    for role, tier, title in _SECTIONS:
        cards = sections[(role, tier)]
        if not cards:
            continue
        body.append(f"<h2>{title}</h2>\n<div class=\"cards\">\n" + "\n".join(cards) + "\n</div>")
    html = _TEMPLATE
    html = html.replace("__PAYLOAD__", payload)
    html = html.replace("__SECTIONS__", "\n".join(body))
    return html


def _card(key: str, fam: dict, uri: str) -> str:
    consumers = ", ".join(fam["consumers"])
    plural = "s" if fam["frames"] != 1 else ""
    cell = fam["cellPx"]
    return f"""<div class="card">
  <h3>{key}<span class="tag {fam['role']}">{fam['role']}</span></h3>
  <div class="meta">{fam['silhouette']} &middot; {fam['frames']}f @ {fam['rateTicks']}t
    &middot; hitbox r {fam['hitboxRadiusTiles']}t &middot; cell {cell}px<br>{consumers}</div>
  <img class="sheet" id="img-{key}" src="{uri}" alt="{key} sheet"
       width="{fam['frames'] * cell * 2}" height="{cell * 2}" draggable="false">
  <div class="lbl">sheet &middot; {fam['frames']} frame{plural} &middot; in-game size at 2x zoom</div>
  <div class="row anim">
    <div><canvas id="c-{key}" width="{cell}" height="{cell}"
         style="width:{cell * 2}px;height:{cell * 2}px"></canvas>
    <div class="lbl">animated</div></div>
  </div>
</div>"""


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Projectile Forge — pack preview</title>
<style>
  html, body { overflow-y: auto !important; height: auto !important; }
  body { background:#141618; color:#cfd4d8; font:14px/1.5 system-ui, sans-serif;
         margin:0; padding:24px; max-width:1200px; box-sizing:border-box; }
  h1 { font-size:18px; margin:0 0 4px; } h2 { font-size:15px; margin:24px 0 8px; }
  .note { color:#8a9299; max-width:70em; }
  .toggles { margin:12px 0; }
  .toggles label { margin-right:18px; user-select:none; cursor:pointer; }
  .cards { display:flex; flex-wrap:wrap; gap:12px; }
  .card { background:#1c1f22; border:1px solid #2a2e32; border-radius:6px;
          padding:10px 12px; width:250px; max-width:100%; box-sizing:border-box; }
  .card h3 { margin:0 0 2px; font-size:14px; }
  .tag { font-size:11px; padding:1px 6px; border-radius:3px; margin-left:6px; }
  .hostile { background:#4a1d1d; color:#ffb3a0; }
  .player  { background:#1d2f4a; color:#a0c8ff; }
  .meta { color:#8a9299; font-size:12px; margin:4px 0 8px; }
  #wrap { --floor:#a8a196; }
  #floorToggle:checked ~ #wrap { --floor:#101214; }
  img.sheet, canvas { image-rendering:pixelated; background:var(--floor);
                      border-radius:4px; display:block; }
  img.sheet { max-width:100%; height:auto; }
  .row { display:flex; gap:10px; align-items:flex-end; margin-top:8px; }
  .lbl { font-size:11px; color:#6f7880; }
  #stresswrap canvas { width:100%; max-width:1152px; height:auto;
                       border:1px solid #2a2e32; }
  /* Animation canvases appear only when the script actually runs. */
  .anim, #stresswrap, #freezelbl { display:none; }
  html.js .anim { display:flex; }
  html.js #stresswrap { display:block; }
  html.js #freezelbl { display:inline; }
  html.js .jsnote { display:none; }
  /* Pure-CSS grayscale audit — works with scripts blocked. */
  #grayToggle:checked ~ #wrap { filter:grayscale(1); }
</style>
</head>
<body>
<h1>Projectile Forge — pack preview</h1>
<p class="note">Light stone floor by default (toggle the dark floor to
audit both — the black contour + bright rim signature must read on either).
Nearest scaling. Sheets are
<b>hitbox-native</b>: every family is baked at its final on-screen size
(hostile: the inscribed circle equals the collision circle; player:
cross-axis capped at the hitbox) and the game draws them 1:1 — what you see
at 2x zoom here is exactly two screen pixels per game pixel. Shapes point +X;
the game rotates shots to their travel direction. Toggle grayscale to audit
the shape-first rule — every family must stay identifiable with color gone.
<span class="jsnote">(Static view: animation and the stress field appear when
scripts are allowed; the sheet strips are the full content.)</span></p>
<div class="toggles">
<input type="checkbox" id="grayToggle">
<label for="grayToggle">grayscale (colorblind / Law 3 audit)</label>
<input type="checkbox" id="floorToggle">
<label for="floorToggle">dark floor</label>
<input type="checkbox" id="pauseToggle" hidden>
<label for="pauseToggle" id="freezelbl">freeze animation</label>
<div id="wrap">
__SECTIONS__
<div id="stresswrap">
<h2>Live range (Law 2 in motion)</h2>
<p class="note">A deterministic firing-range demo (no RNG; demo patterns, not
game data): emplacements cycle through the hostile families — aimed shots,
fans, radials, spirals, volleys — at a strafing player marker that fires
back. Shots fly real trajectories, rotate to travel, and draw in the game's
order: player fire under hostile fire.</p>
<canvas id="stress" width="640" height="360"></canvas>
</div>
</div>
</div>
<script>
document.documentElement.classList.add('js');
document.getElementById('pauseToggle').hidden = false;
const PACK = __PAYLOAD__;
const TPS = PACK.tps;
const pause = document.getElementById('pauseToggle');
const fams = [];
for (const [key, fam] of Object.entries(PACK.families)) {
  fam.key = key;
  fam.img = document.getElementById('img-' + key);
  fams.push(fam);
}
function frameOf(fam, tick) {
  return Math.floor(tick / fam.rateTicks) % fam.frames;
}
function drawShot(ctx, fam, tick, x, y, angle) {
  const s = fam.cellPx;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(fam.img, frameOf(fam, tick) * s, 0, s, s, -s / 2, -s / 2, s, s);
  ctx.restore();
}
const cards = fams.map(fam => ({
  fam,
  ctx: document.getElementById('c-' + fam.key).getContext('2d'),
  lastFrame: -1,
}));
function drawCards(tick) {
  for (const c of cards) {
    const f = frameOf(c.fam, tick);
    if (c.lastFrame === f) continue;
    c.lastFrame = f;
    const s = c.fam.cellPx;
    c.ctx.clearRect(0, 0, s, s);
    drawShot(c.ctx, c.fam, tick, s / 2, s / 2, 0);
  }
}
// ---- Live range: a deterministic firing-range sim (no RNG anywhere) ----
// Speeds are tiles/s converted to px/tick at 32 px/tile, 60 t/s. Volley
// angles are authored offsets, CORE-32 style. Demo patterns, not game data.
const PX = 32 / 60;
const byKey = Object.fromEntries(fams.map(f => [f.key, f]));
const VOLLEYS = {
  husk_dart:   { cd: 90,  spd: 7.0,  angles: [0] },
  lead_needle: { cd: 120, spd: 9.5,  angles: [0] },
  fan_wedge:   { cd: 150, spd: 6.0,  angles: [-30, -15, 0, 15, 30] },
  ring_roundel:{ cd: 180, spd: 5.0,  radial: 12 },
  warden_star: { cd: 110, spd: 4.5,  radial: 4, spin: 0.35 },
  comet:       { cd: 70,  spd: 11.0, angles: [0] },
  crescent:    { cd: 130, spd: 5.5,  angles: [-20, 0, 20] },
  cross_plus:  { cd: 160, spd: 3.5,  angles: [-10, 10] },
  hex_star:    { cd: 200, spd: 4.0,  radial: 6, spin: 0.15 },
  bar_sweep:   { cd: 140, spd: 4.5,  angles: [0] },
  meteor:      { cd: 220, spd: 2.8,  angles: [0] },
  shard:       { cd: 100, spd: 9.0,  angles: [-18, -6, 6, 18] },
  twin_orb:    { cd: 150, spd: 5.0,  parallel: 9 },
  spark:       { cd: 90,  spd: 6.5,  radial: 8 },
};
const EMITTERS = [
  { x: 70, y: 60 }, { x: 570, y: 60 }, { x: 70, y: 300 },
  { x: 570, y: 300 }, { x: 320, y: 36 }, { x: 320, y: 324 },
  { x: 36, y: 180 }, { x: 604, y: 180 },
];
const hostileKeys = Object.keys(VOLLEYS).filter(k => byKey[k]);
const shots = [];
function playerPos(t) {
  return { x: 320 + 150 * Math.sin(t * 0.011), y: 180 + 92 * Math.sin(t * 0.017 + 1.3) };
}
function spawn(fam, x, y, ang, spd, ttl) {
  if (shots.length >= 400) return;
  shots.push({ fam, x, y, vx: Math.cos(ang) * spd * PX, vy: Math.sin(ang) * spd * PX,
               born: tick, ttl });
}
function fireVolley(key, ex, ey, t) {
  const v = VOLLEYS[key];
  const fam = byKey[key];
  const p = playerPos(t);
  const aim = Math.atan2(p.y - ey, p.x - ex);
  if (v.radial) {
    const base = (v.spin || 0) * t * 0.1;
    for (let i = 0; i < v.radial; i++)
      spawn(fam, ex, ey, base + i * 2 * Math.PI / v.radial, v.spd, 300);
  } else if (v.parallel) {
    const nx = -Math.sin(aim), ny = Math.cos(aim);
    spawn(fam, ex + nx * v.parallel, ey + ny * v.parallel, aim, v.spd, 300);
    spawn(fam, ex - nx * v.parallel, ey - ny * v.parallel, aim, v.spd, 300);
  } else {
    for (const a of v.angles)
      spawn(fam, ex, ey, aim + a * Math.PI / 180, v.spd, 300);
  }
}
function stepRange(t) {
  const p = playerPos(t);
  // emplacements cycle families every 4 s so every lane gets stage time
  EMITTERS.forEach((e, i) => {
    const key = hostileKeys[(i + Math.floor(t / 240)) % hostileKeys.length];
    if (t % VOLLEYS[key].cd === (i * 37) % VOLLEYS[key].cd) fireVolley(key, e.x, e.y, t);
  });
  // the player marker fires back at the nearest emplacement
  let best = EMITTERS[0], bd = 1e9;
  for (const e of EMITTERS) {
    const d = (e.x - p.x) ** 2 + (e.y - p.y) ** 2;
    if (d < bd) { bd = d; best = e; }
  }
  const aim = Math.atan2(best.y - p.y, best.x - p.x);
  if (t % 15 === 0 && byKey.longbolt) spawn(byKey.longbolt, p.x, p.y, aim, 14, 28);
  if (t % 30 === 7 && byKey.scattercast)
    for (const a of [-25, -12.5, 0, 12.5, 25])
      spawn(byKey.scattercast, p.x, p.y, aim + a * Math.PI / 180, 11, 22);
  if (t % 48 === 11 && byKey.wheelblade) spawn(byKey.wheelblade, p.x, p.y, aim, 8, 90);
  for (let i = shots.length - 1; i >= 0; i--) {
    const s = shots[i];
    const age = t - s.born;
    if (s.fam.key === 'wheelblade' && age === 45) { s.vx = -s.vx; s.vy = -s.vy; }
    s.x += s.vx; s.y += s.vy;
    if (age > s.ttl || s.x < -40 || s.x > 680 || s.y < -40 || s.y > 400) shots.splice(i, 1);
  }
}
function drawRange(ctx, t) {
  ctx.clearRect(0, 0, 640, 360);
  const p = playerPos(t);
  // emplacement posts
  for (const e of EMITTERS) {
    ctx.fillStyle = '#12100e';
    ctx.fillRect(e.x - 7, e.y - 7, 14, 14);
    ctx.fillStyle = '#4a4238';
    ctx.fillRect(e.x - 5, e.y - 5, 10, 10);
  }
  // player marker
  ctx.beginPath();
  ctx.arc(p.x, p.y, 7, 0, 2 * Math.PI);
  ctx.fillStyle = '#12100e';
  ctx.fill();
  ctx.beginPath();
  ctx.arc(p.x, p.y, 5.2, 0, 2 * Math.PI);
  ctx.fillStyle = '#7c94aa';
  ctx.fill();
  // Law 2 order: player shots under hostile shots
  for (const s of shots)
    if (s.fam.role === 'player')
      drawShot(ctx, s.fam, t - s.born, s.x, s.y, Math.atan2(s.vy, s.vx));
  for (const s of shots)
    if (s.fam.role === 'hostile')
      drawShot(ctx, s.fam, t - s.born, s.x, s.y, Math.atan2(s.vy, s.vx));
}
const stress = document.getElementById('stress').getContext('2d');
let tick = 0, last = 0;
function loop(now) {
  if (!pause.checked && now - last >= 1000 / TPS) {
    last = now;
    tick++;
    drawCards(tick);
    stepRange(tick);
    drawRange(stress, tick);
  }
  requestAnimationFrame(loop);
}
function start() {
  drawCards(0);
  // pre-roll so the range opens mid-action instead of empty
  for (let i = 0; i < 240; i++) { tick++; stepRange(tick); }
  drawRange(stress, tick);
  requestAnimationFrame(loop);
}
if (fams.every(f => f.img.complete)) start();
else Promise.all(fams.map(f => new Promise(res => {
  if (f.img.complete) res();
  else { f.img.onload = res; f.img.onerror = res; }
}))).then(start);
</script>
</body>
</html>
"""
