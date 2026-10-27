// Zhipu (智谱): the GLM-Videos mascot — an original character design for Z.ai.
// The Z.ai logo tile come to life: a little charcoal sprite with a white glowing
// face and a signal-blue wisdom antenna — the spark that turns plain words into
// films. 18x10 square pixels, drawn on the shared pixel grid.
// Brand palette + the flat / 2.5D / 3D kit: docs/mascot/MASCOT.md.
// Zhipu and its design are original to the GLM-Videos project (MIT licence).
// Z.ai brand palette (from the official Z mark): charcoal tile · white Z · signal blue
export const INK = '#2D2D2D', INK_D = '#141414';                     // charcoal body + shadow tone
export const ZAI = '#1F63EC', ZAI_D = '#1849C8', ZAI_L = '#257AF1';  // signal blue + shades
export const EYE = '#0B1B2B', GLOW = '#1F63EC';                      // deep-navy ink for fx · blue glow
// drop-in aliases (the old sprite exported CLAY/CLAY_D)
export const CLAY = ZAI, CLAY_D = ZAI_D;

// kinds: 1 charcoal body · 2 white eye/mouth · 3 blue glow (antenna) · 4 blue glint · 5 blue core (belly) · 6 deep-blue foot
// returns [[c, r, kind]]
export function grid({ eyes = 'n', arms = 'down', legs = 'stand' } = {}) {
  const P = new Map(), put = (c, r, v = 1) => P.set(c + ',' + r, v);
  // antenna: a glowing blue knob on top of the head (the wisdom spark)
  put(8, 0, 3); put(9, 0, 3);
  // body: the charcoal logo tile, c 4..13, r 1..7, corners cut for a friendly dome
  for (let r = 1; r <= 7; r++) for (let c = 4; c <= 13; c++) put(c, r);
  for (const [c, r] of [[4, 1], [13, 1], [4, 7], [13, 7]]) P.delete(c + ',' + r);
  // arms: stubby, attached to the body edge
  if (arms === 'up') for (const r of [0, 1, 2, 3]) { put(2, r); put(3, r); put(14, r); put(15, r); }
  else if (arms === 'wave') { for (const r of [4, 5]) { put(2, r); put(3, r); } for (const r of [0, 1, 2, 3]) { put(14, r); put(15, r); } }
  else if (arms === 'tuck') { /* arms tucked */ }
  else for (const r of [4, 5]) for (const c of [2, 3, 14, 15]) put(c, r);
  // feet (deep signal blue, chunky)
  const L = { stand: [[5, 2], [11, 2]], walkA: [[5, 2], [11, 1]], walkB: [[5, 1], [11, 2]],
    tuck: [[5, 1], [11, 1]], none: [] }[legs];
  for (const [c0, h] of L) for (const c of [c0, c0 + 1]) for (let r = 8; r < 8 + h; r++) put(c, r, 6);
  // eyes: white glowing squares with a blue glint pixel, plus a small mouth
  const E = {
    n: { l: [6, 3], r: [10, 3], g: [[6, 3], [10, 3]] },
    r: { l: [7, 3], r: [11, 3], g: [[7, 3], [11, 3]] },
    l: { l: [5, 3], r: [9, 3], g: [[5, 3], [9, 3]] },
    u: { l: [6, 2], r: [10, 2], g: [[6, 2], [10, 2]] },
    d: { l: [6, 4], r: [10, 4], g: [[6, 4], [10, 4]] },
    wide: { l: [6, 2], r: [10, 2], g: [[6, 2], [10, 2]], h: 3 },
    blink: { flat: [[6, 7], [10, 11]] },
    happy: { arc: [[5, 6, 7], [10, 11, 12]] },
    shut: { line: [[5, 6, 7], [10, 11, 12]], row: 3 }
  }[eyes];
  if (E.arc) for (const [a, b, c2] of E.arc) { put(a, 4); put(b, 3); put(c2, 4); }
  else if (E.line) for (const row of E.line) for (const c of row) put(c, E.row ?? 4);
  else if (E.flat) for (const [a, b] of E.flat) { put(a, 4); put(b, 4); }
  else {
    const h = E.h || 2;
    for (const [cx, cy] of [[E.l], [E.r]].map(x => x[0])) for (let i = 0; i < 2; i++) for (let j = 0; j < h; j++) put(cx + i, cy + j, 2);
    for (const [c, r] of E.g) put(c, r, 4);
  }
  put(8, 5, 2); put(9, 5, 2); // mouth: a tiny two-pixel glowing smile
  for (let r = 6; r <= 7; r++) for (let c = 6; c <= 11; c++) put(c, r, 5); // blue core band (the chest emblem at pixel scale)
  return [...P].map(([k, v]) => { const [c, r] = k.split(',').map(Number); return [c, r, v]; });
}

// x,y = midpoint under the feet (world coords); px = pixel side length; sq>0 squash, <0 stretch; flip faces left; rot in radians (flips)
export function sprite({ x, y, px = 7, flip = false, sq = 0, rot = 0, op = 1, shadow = 0, ...pose }) {
  const G = grid(pose); let s = '';
  const F = { 1: INK, 2: '#FFFFFF', 3: GLOW, 4: ZAI, 5: ZAI, 6: ZAI_D };
  for (let [c, r, v] of G) { if (flip) c = 17 - c; s += `<rect x="${c}" y="${r}" width="1.04" height="1.04" fill="${F[v]}"/>`; }
  // a row of darker pixels along the bottom of the tile = sense of volume (drawn only on body row 7)
  for (let c = 4; c <= 13; c++) s += `<rect x="${c}" y="7" width="1.04" height="1.04" fill="${INK_D}" opacity=".55"/>`;
  const sy = 1 - sq, sx = 1 + sq * .7, w = 18 * px * sx, h = 10 * px * sy;
  const sh = shadow > 0 ? `<div style="position:absolute;left:${x - 6 * px}px;top:${y - px * .4}px;width:${12 * px}px;height:${px * .8}px;border-radius:50%;background:rgba(0,0,0,${.16 * shadow})"></div>` : '';
  return sh + `<svg class="px" viewBox="0 0 18 10" width="${w}" height="${h}" style="left:${x - w / 2}px;top:${y - h}px;opacity:${op};transform:rotate(${rot}rad);transform-origin:50% 60%" shape-rendering="crispEdges">${s}</svg>`;
}
// the sprite's pixel centres (world coords), for pixel burst/merge
export function pixels(o) {
  const { x, y, px = 7, flip = false } = o;
  return grid(o).map(([c, r, v]) => ({ x: x + ((flip ? 17 - c : c) - 9 + .5) * px, y: y + (r - 10 + .5) * px, v }));
}
export function pixart(rows, { x, y, px = 7, pal, op = 1 }) {
  let s = ''; rows.forEach((row, r) => [...row].forEach((ch, c) => { if (pal[ch]) s += `<rect x="${c}" y="${r}" width="1.04" height="1.04" fill="${pal[ch]}"/>`; }));
  const W = rows[0].length, H = rows.length;
  return `<svg class="px" viewBox="0 0 ${W} ${H}" width="${W * px}" height="${H * px}" style="left:${x}px;top:${y}px;opacity:${op}" shape-rendering="crispEdges">${s}</svg>`;
}
export const BANG = (x, y, px = 6, op = 1) => pixart(['.kkk.', 'kwwwk', 'kwkwk', 'kwkwk', 'kwwwk', 'kwkwk', 'kwwwk', '.kkk.', '..k..'], { x, y, px, op, pal: { w: '#fff', k: EYE } });
export const DOTS = (x, y, px = 6, n = 3, op = 1) => n < 1 ? '' : pixart(['kk.kk.kk'.slice(0, n * 3 - 1), 'kk.kk.kk'.slice(0, n * 3 - 1)], { x, y, px, op, pal: { k: EYE } });
export const PENCIL = (x, y, px = 6, op = 1) => pixart(['......kk', '.....yyk', '....yyy.', '...yyy..', '..yyy...', '.pyy....', 'ppy.....', 'k.......'], { x, y, px, op, pal: { y: '#F2C14E', k: EYE, p: '#E8A898' } });
export const SPARK = (x, y, px = 6, col = GLOW, op = 1) => pixart(['..y..', '..y..', 'yy.yy', '..y..', '..y..'], { x: x - 2.5 * px, y: y - 2.5 * px, px, op, pal: { y: col } });
export const HEART = (x, y, px = 5, op = 1) => pixart(['.rr.rr.', 'rrrrrrr', 'rrrrrrr', '.rrrrr.', '..rrr..', '...r...'], { x: x - 3.5 * px, y: y - 3 * px, px, op, pal: { r: '#E0543A' } });
export const CHECK = (x, y, px = 6, op = 1) => pixart(['.....g', '....gg', 'g..gg.', 'gggg..', '.gg...'], { x, y, px, op, pal: { g: '#2F9E4F' } });
export const SWEAT = (x, y, px = 5, op = 1) => pixart(['.b.', 'bbb', 'bbb', '.b.'], { x, y, px, op, pal: { b: ZAI_L } });
// dust: t 0→1 spreads out to both sides
export function dust(x, y, t, px = 5, n = 6, seed = 1) {
  if (t <= 0 || t >= 1) return ''; let s = '';
  for (let i = 0; i < n; i++) {
    const side = i % 2 ? 1 : -1, k = (i >> 1) + 1, e = 1 - Math.pow(1 - t, 2);
    const dx = side * (18 + k * 16 + ((seed * 7 + i * 13) % 9)) * e, dy = -(8 + k * 5) * Math.sin(Math.PI * t * .9);
    const sz = px * (1 - t * .7);
    s += `<div style="position:absolute;left:${x + dx - sz / 2}px;top:${y + dy - sz}px;width:${sz}px;height:${sz}px;background:#CFC7B6;opacity:${1 - t}"></div>`;
  }
  return s;
}
// speed lines: short pixel dashes
export function speedlines(x, y, dir, t, px = 5) {
  if (t <= 0 || t >= 1) return ''; let s = '';
  for (let i = 0; i < 4; i++) {
    const len = (3 + (i % 2) * 3) * px, off = (i * 23 + 11) % 60 - 30;
    s += `<div style="position:absolute;left:${x - dir * (40 + i * 12) - (dir > 0 ? len : 0)}px;top:${y - 40 + off}px;width:${len}px;height:${px}px;background:${ZAI};opacity:${(1 - t) * .7}"></div>`;
  }
  return s;
}
