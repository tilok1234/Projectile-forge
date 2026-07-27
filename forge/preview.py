"""preview.html generator: a self-contained visual audit page.

Everything is inlined (sheets as data URIs, no external requests) so the file
works from file:// and can be attached to a devlog post as-is. It is an
EYEBALL tool — the numbers live in validation-report.json; this page exists
for the human half: grayscale toggle (colorblind / Law 3 shape-first check)
and a deterministic stress-field view (Law 2 at density).
"""

from __future__ import annotations

import base64
import json


def build_preview(manifest: dict, pngs: dict) -> str:
    fams = {}
    for key, fam in manifest["families"].items():
        entry = dict(fam)
        entry["dataUri"] = "data:image/png;base64," + base64.b64encode(pngs[fam["image"]]).decode("ascii")
        fams[key] = entry
    payload = json.dumps(
        {"cell": manifest["cell"], "tps": manifest["ticksPerSecond"], "families": fams},
        sort_keys=True,
    )
    return _TEMPLATE.replace("__PAYLOAD__", payload)


_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Projectile Forge — pack preview</title>
<style>
  html { overflow-y:auto; }
  body { background:#141618; color:#cfd4d8; font:14px/1.5 system-ui, sans-serif;
         margin:0; padding:24px; max-width:1200px; }
  h1 { font-size:18px; margin:0 0 4px; } h2 { font-size:15px; margin:24px 0 8px; }
  .note { color:#8a9299; max-width:70em; }
  .controls { margin:12px 0; }
  .controls label { margin-right:18px; user-select:none; }
  .gray { filter:grayscale(1); }
  .cards { display:flex; flex-wrap:wrap; gap:12px; }
  .card { background:#1c1f22; border:1px solid #2a2e32; border-radius:6px;
          padding:10px 12px; width:240px; }
  .card h3 { margin:0 0 2px; font-size:14px; }
  .tag { font-size:11px; padding:1px 6px; border-radius:3px; margin-left:6px; }
  .hostile { background:#4a1d1d; color:#ffb3a0; }
  .player  { background:#1d2f4a; color:#a0c8ff; }
  .meta { color:#8a9299; font-size:12px; margin:4px 0 8px; }
  canvas { image-rendering:pixelated; background:#101214; border-radius:4px; }
  .row { display:flex; gap:10px; align-items:center; }
  .lbl { font-size:11px; color:#6f7880; }
  /* Responsive: never wider than the page — wide canvases must not force
     horizontal overflow or break scrolling in embedded viewers. */
  #stress { border:1px solid #2a2e32; width:100%; max-width:1152px; height:auto; }
</style>
</head>
<body>
<h1>Projectile Forge — pack preview</h1>
<p class="note">Quiet dark floor, Nearest scaling. <b>authored</b> is the raw
32px cell at 4x; <b>in-game</b> applies the manifest render scale (hostile:
visual covers the collision circle; player: cross-axis capped at the hitbox).
Toggle grayscale to audit the shape-first rule — every family must stay
identifiable with color gone. The stress field is deterministic (no RNG),
player spam under hostile fire — hostile must stay legible above all of it.</p>
<div class="controls">
  <label><input type="checkbox" id="grayToggle"> grayscale (colorblind / Law 3 audit)</label>
  <label><input type="checkbox" id="pauseToggle"> freeze animation</label>
</div>
<div id="wrap">
<h2>Player families (subordinate — Law 2)</h2>
<div class="cards" id="playerCards"></div>
<h2>Hostile families (one shared signature — §2.6, Law 3)</h2>
<div class="cards" id="hostileCards"></div>
<h2>Stress field (Law 2 at density)</h2>
<canvas id="stress" width="640" height="360"></canvas>
</div>
<script>
const PACK = __PAYLOAD__;
const CELL = PACK.cell, TPS = PACK.tps;
const imgs = {}, ready = [];
for (const [key, fam] of Object.entries(PACK.families)) {
  const im = new Image();
  im.src = fam.dataUri;
  imgs[key] = im;
  ready.push(new Promise(res => { im.onload = res; }));
}
const gray = document.getElementById('grayToggle');
const pause = document.getElementById('pauseToggle');
gray.onchange = () => document.getElementById('wrap').classList.toggle('gray', gray.checked);

function frameOf(fam, tick) {
  return Math.floor(tick / fam.rateTicks) % fam.frames;
}
function drawShot(ctx, fam, tick, x, y, angle, scale) {
  const f = frameOf(fam, tick);
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(angle);
  const s = CELL * scale;
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(imgs[fam._key], f * CELL, 0, CELL, CELL, -s / 2, -s / 2, s, s);
  ctx.restore();
}

const cards = [];
for (const [key, fam] of Object.entries(PACK.families)) {
  fam._key = key;
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML =
    '<h3>' + key + '<span class="tag ' + fam.role + '">' + fam.role + '</span></h3>' +
    '<div class="meta">' + fam.silhouette + ' · ' + fam.frames + 'f @ ' + fam.rateTicks +
    't · hitbox r ' + fam.hitboxRadiusTiles + 't · scale ' + fam.renderScale +
    '<br>' + fam.consumers.join(', ') + '</div>' +
    '<div class="row"><div><canvas width="48" height="48" style="width:96px;height:96px"></canvas>' +
    '<div class="lbl">authored 4x</div></div>' +
    '<div><canvas width="48" height="48" style="width:96px;height:96px"></canvas>' +
    '<div class="lbl">in-game 2x</div></div></div>';
  document.getElementById(fam.role === 'hostile' ? 'hostileCards' : 'playerCards').appendChild(card);
  const [authored, ingame] = card.querySelectorAll('canvas');
  cards.push({ fam, authored: authored.getContext('2d'), ingame: ingame.getContext('2d') });
}

// Deterministic stress field: no RNG anywhere, phases are pure functions of
// the emitter index (mirrors the game's authored-pattern rule).
function stressField(ctx, tick) {
  ctx.clearRect(0, 0, 640, 360);
  const hostiles = Object.values(PACK.families).filter(f => f.role === 'hostile');
  const players = Object.values(PACK.families).filter(f => f.role === 'player');
  // player spam underneath (Law 2: must NOT bury hostile fire)
  for (let i = 0; i < 90; i++) {
    const fam = players[i % players.length];
    const a = (i * 2.399963) % (Math.PI * 2);          // golden-angle spread
    const r = 30 + ((i * 53) % 130) + ((tick * 2.2 + i * 17) % 160);
    const x = 320 + Math.cos(a) * r, y = 180 + Math.sin(a) * r * 0.56;
    drawShot(ctx, fam, tick + i * 3, x, y, a, fam.renderScale);
  }
  // hostile rings over it
  for (let i = 0; i < 56; i++) {
    const fam = hostiles[i % hostiles.length];
    const a = i * 0.7 + tick * 0.012;
    const r = 40 + ((i * 37) % 110) + 34 * Math.sin(tick * 0.02 + i);
    const x = 320 + Math.cos(a) * r, y = 180 + Math.sin(a) * r * 0.56;
    drawShot(ctx, fam, tick + i * 5, x, y, a + Math.PI / 2, fam.renderScale);
  }
}

// requestAnimationFrame + dirty-frame card redraws: the page must stay
// light enough that scrolling never fights the animation, including in
// embedded viewers.
let tick = 0;
let last = 0;
Promise.all(ready).then(() => {
  const stress = document.getElementById('stress').getContext('2d');
  function loop(now) {
    if (!pause.checked && now - last >= 1000 / TPS) {
      last = now;
      tick++;
      for (const c of cards) {
        const f = frameOf(c.fam, tick);
        if (c.lastFrame !== f) {
          c.lastFrame = f;
          c.authored.clearRect(0, 0, 48, 48);
          c.ingame.clearRect(0, 0, 48, 48);
          drawShot(c.authored, c.fam, tick, 24, 24, 0, 1);
          drawShot(c.ingame, c.fam, tick, 24, 24, 0, c.fam.renderScale);
        }
      }
      stressField(stress, tick);
    }
    requestAnimationFrame(loop);
  }
  for (const c of cards) {
    drawShot(c.authored, c.fam, 0, 24, 24, 0, 1);
    drawShot(c.ingame, c.fam, 0, 24, 24, 0, c.fam.renderScale);
  }
  stressField(stress, 0);
  requestAnimationFrame(loop);
});
</script>
</body>
</html>
"""
