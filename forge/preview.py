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
"""

from __future__ import annotations

import base64
import json


def build_preview(manifest: dict, pngs: dict) -> str:
    metas = {}
    cards = {"player": [], "hostile": []}
    for key in sorted(manifest["families"]):
        fam = manifest["families"][key]
        uri = "data:image/png;base64," + base64.b64encode(pngs[fam["image"]]).decode("ascii")
        metas[key] = {
            "role": fam["role"],
            "frames": fam["frames"],
            "rateTicks": fam["rateTicks"],
            "renderScale": fam["renderScale"],
        }
        cards[fam["role"]].append(_card(key, fam, uri))
    payload = json.dumps(
        {"cell": manifest["cell"], "tps": manifest["ticksPerSecond"], "families": metas},
        sort_keys=True,
    )
    html = _TEMPLATE
    html = html.replace("__PAYLOAD__", payload)
    html = html.replace("__PLAYER_CARDS__", "\n".join(cards["player"]))
    html = html.replace("__HOSTILE_CARDS__", "\n".join(cards["hostile"]))
    return html


def _card(key: str, fam: dict, uri: str) -> str:
    consumers = ", ".join(fam["consumers"])
    plural = "s" if fam["frames"] != 1 else ""
    return f"""<div class="card">
  <h3>{key}<span class="tag {fam['role']}">{fam['role']}</span></h3>
  <div class="meta">{fam['silhouette']} &middot; {fam['frames']}f @ {fam['rateTicks']}t
    &middot; hitbox r {fam['hitboxRadiusTiles']}t &middot; scale {fam['renderScale']}<br>{consumers}</div>
  <img class="sheet" id="img-{key}" src="{uri}" alt="{key} sheet"
       width="{fam['frames'] * 64}" height="64" draggable="false">
  <div class="lbl">sheet &middot; {fam['frames']} frame{plural} at 2x</div>
  <div class="row anim">
    <div><canvas id="a-{key}" width="48" height="48"></canvas><div class="lbl">authored 4x</div></div>
    <div><canvas id="g-{key}" width="48" height="48"></canvas><div class="lbl">in-game 2x</div></div>
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
          padding:10px 12px; width:240px; max-width:100%; box-sizing:border-box; }
  .card h3 { margin:0 0 2px; font-size:14px; }
  .tag { font-size:11px; padding:1px 6px; border-radius:3px; margin-left:6px; }
  .hostile { background:#4a1d1d; color:#ffb3a0; }
  .player  { background:#1d2f4a; color:#a0c8ff; }
  .meta { color:#8a9299; font-size:12px; margin:4px 0 8px; }
  img.sheet, canvas { image-rendering:pixelated; background:#101214;
                      border-radius:4px; display:block; }
  img.sheet { max-width:100%; height:auto; }
  canvas { width:96px; height:96px; }
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
<p class="note">Quiet dark floor, Nearest scaling. Each card shows the raw
sheet strip (frames left to right, shapes point +X — the game rotates shots
to their travel direction). <b>in-game</b> canvases apply the manifest render
scale: hostile visuals cover the collision circle; player cross-axis is
capped at the hitbox. Toggle grayscale to audit the shape-first rule — every
family must stay identifiable with color gone.
<span class="jsnote">(Static view: animation and the stress field appear when
scripts are allowed; the sheet strips above are the full content.)</span></p>
<div class="toggles">
<input type="checkbox" id="grayToggle">
<label for="grayToggle">grayscale (colorblind / Law 3 audit)</label>
<input type="checkbox" id="pauseToggle" hidden>
<label for="pauseToggle" id="freezelbl">freeze animation</label>
<div id="wrap">
<h2>Player families (subordinate — Law 2)</h2>
<div class="cards">
__PLAYER_CARDS__
</div>
<h2>Hostile families (one shared signature — §2.6, Law 3)</h2>
<div class="cards">
__HOSTILE_CARDS__
</div>
<div id="stresswrap">
<h2>Stress field (Law 2 at density)</h2>
<p class="note">Deterministic (no RNG): player spam underneath, hostile fire
over it — hostile must stay legible above all of it.</p>
<canvas id="stress" width="640" height="360"></canvas>
</div>
</div>
</div>
<script>
document.documentElement.classList.add('js');
document.getElementById('pauseToggle').hidden = false;
const PACK = __PAYLOAD__;
const CELL = PACK.cell, TPS = PACK.tps;
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
function drawShot(ctx, fam, tick, x, y, angle, scale) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  const s = CELL * scale;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(fam.img, frameOf(fam, tick) * CELL, 0, CELL, CELL,
                -s / 2, -s / 2, s, s);
  ctx.restore();
}
const cards = fams.map(fam => ({
  fam,
  authored: document.getElementById('a-' + fam.key).getContext('2d'),
  ingame: document.getElementById('g-' + fam.key).getContext('2d'),
  lastFrame: -1,
}));
function drawCards(tick) {
  for (const c of cards) {
    const f = frameOf(c.fam, tick);
    if (c.lastFrame === f) continue;
    c.lastFrame = f;
    c.authored.clearRect(0, 0, 48, 48);
    c.ingame.clearRect(0, 0, 48, 48);
    drawShot(c.authored, c.fam, tick, 24, 24, 0, 1);
    drawShot(c.ingame, c.fam, tick, 24, 24, 0, c.fam.renderScale);
  }
}
// Deterministic stress field: phases are pure functions of the emitter index
// (mirrors the game's authored-pattern rule).
function stressField(ctx, tick) {
  ctx.clearRect(0, 0, 640, 360);
  const hostiles = fams.filter(f => f.role === 'hostile');
  const players = fams.filter(f => f.role === 'player');
  for (let i = 0; i < 90; i++) {
    const fam = players[i % players.length];
    const a = (i * 2.399963) % (Math.PI * 2);
    const r = 30 + ((i * 53) % 130) + ((tick * 2.2 + i * 17) % 160);
    drawShot(ctx, fam, tick + i * 3,
             320 + Math.cos(a) * r, 180 + Math.sin(a) * r * 0.56,
             a, fam.renderScale);
  }
  for (let i = 0; i < 56; i++) {
    const fam = hostiles[i % hostiles.length];
    const a = i * 0.7 + tick * 0.012;
    const r = 40 + ((i * 37) % 110) + 34 * Math.sin(tick * 0.02 + i);
    drawShot(ctx, fam, tick + i * 5,
             320 + Math.cos(a) * r, 180 + Math.sin(a) * r * 0.56,
             a + Math.PI / 2, fam.renderScale);
  }
}
const stress = document.getElementById('stress').getContext('2d');
let tick = 0, last = 0;
function loop(now) {
  if (!pause.checked && now - last >= 1000 / TPS) {
    last = now;
    tick++;
    drawCards(tick);
    stressField(stress, tick);
  }
  requestAnimationFrame(loop);
}
function start() {
  drawCards(0);
  stressField(stress, 0);
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
