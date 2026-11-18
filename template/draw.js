/* draw.js — 自由画面（shot.type = "draw"）：现成的件放不下这句话要演的东西时，用几样基本东西自己搭一个画面。
 * 怎么想出画面、画成什么样，见 references/07-画面怎么想出来.md；字段表在 references/03。
 *
 *   items：屏上的东西。kind 是 icon（1500+ 个图标）/ text / num / box（卡片、单据、通知）/ phone（手机，里面是列表或聊天）/
 *          crowd（一群人或一堆东西，标出其中几个）/ bar（一根进度条）/ arrow / line（连两样东西）
 *   每样东西写 at（这一镜第几句出场，从 0 数）和 beat（第几拍，1–4，默认 1）；不写 x / y 就自动排（一行三个，多了排成格子）。
 *   acts：之后对它做什么，同样落在第几句第几拍：strike 划掉 / cross 打叉 / check 打勾 / flash 闪 / dim 变暗 / hide 收走 /
 *         move 挪到 x y / grow 放大到 s 倍 / count 数字变到 to / fill 进度条走到 to / swap 换字 / color 换颜色 / mark 一群里标出 to 个 / shake 抖
 * 坐标：x、y 是内容区里的比例（0 左上 → 1 右下，内容区是 y 470–1390 这一块）；大小（size / w）是内容区宽度的比例。
 * scripts/check_film.py 用同一套排版算法算每样东西占的地方，查出界、互相压住、字太长。两边改一起改。
 */
(function () {
'use strict';
const { W, clamp, lerp, seg, E, rgba } = VK;
const X0 = 96, XR = W - 96, CW = XR - X0, ZT = 470, ZB = 1390, ZH = ZB - ZT;
const TEXT = { s: 40, m: 58, l: 86, xl: 140 };
const DEF = { icon: 0.26, phone: 0.46, box: 0.76, crowd: 0.86, bar: 0.80 };   // 默认就往大了画：标杆样片的主体占画面宽度六七成
const ROW = 66, TITLE = 78, PAD = 44;
const isCJK = ch => ch >= '㐀' && ch <= '鿿';
const estW = (s, size) => Array.from(String(s)).reduce((a, ch) => a + (isCJK(ch) ? 1 : ch === ' ' ? 0.3 : 0.6) * size, 0);

function colorOf(name, c, dflt) {
  const m = { main: c.col, alt: c.alt, white: INK.white, dim: INK.dim, red: NEON.red.main, green: NEON.green.main, gold: NEON.amber.main };
  return m[name] || dflt;
}
function fmtNum(v) {
  const n = Number(v); if (!isFinite(n)) return String(v);
  const dec = (String(v).split('.')[1] || '').length, s = Math.abs(n).toFixed(dec), [a, b] = s.split('.');
  return (n < 0 ? '-' : '') + a.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (b ? '.' + b : '');
}
const numStr = (it, v) => (it.prefix || '') + fmtNum(v) + (it.suffix || '');

/* 自动排：没写 x / y 的东西（连线除外）按出场顺序排成一行（≤ 3 个）或格子；最后一行不满就居中 */
function autoLayout(items) {
  const free = items.filter(it => it.kind !== 'arrow' && it.kind !== 'line' && (it.x == null || it.y == null));
  const n = free.length; if (!n) return;
  const cols = n <= 3 ? n : n === 4 ? 2 : 3, rows = Math.ceil(n / cols);
  free.forEach((it, i) => {
    const r = Math.floor(i / cols), inRow = r === rows - 1 ? n - r * cols : cols, cIdx = i - r * cols;
    if (it.x == null) it.x = (cIdx + 0.5 + (cols - inRow) / 2) / cols;
    if (it.y == null) it.y = (r + 0.5) / rows;
  });
}

/* 一样东西占多大（像素，中心在 x y）：画的时候和检查脚本都按这个算 */
function boxOf(it) {
  const k = it.kind;
  if (k === 'icon') { const s = (it.size || DEF.icon) * CW; return { w: Math.max(s, it.label ? estW(it.label, 40) : 0), h: s + (it.label ? 62 : 0), dy: it.label ? 31 : 0, s }; }
  if (k === 'text') { const z = TEXT[it.size] || TEXT.m; return { w: Math.min(CW, estW(it.text, z)), h: z * 1.25, z }; }
  if (k === 'num') { const z = TEXT[it.size] || TEXT.xl; return { w: Math.min(CW, estW(numStr(it, it.value), z) * 0.9), h: z * 1.15, z }; }
  if (k === 'box') { const w = (it.w || DEF.box) * CW, n = (it.rows || []).length; return { w, h: PAD + (it.title ? TITLE : 0) + n * ROW + (n ? 8 : 0) }; }
  if (k === 'phone') { const w = (it.size || DEF.phone) * CW; return { w, h: w * 1.95 }; }
  if (k === 'crowd') { const w = (it.w || DEF.crowd) * CW, g = crowdGrid(it, w); return { w, h: g.rows * g.cell, g }; }
  if (k === 'bar') { const w = (it.w || DEF.bar) * CW; return { w, h: it.label ? 112 : 50 }; }
  return { w: 0, h: 0 };
}
function crowdGrid(it, w) {
  const n = clamp(Math.round(it.n || 10), 1, 100), cols = Math.min(n, Math.max(1, Math.ceil(Math.sqrt(n * 1.6)))), cell = w / cols;
  return { n, cols, rows: Math.ceil(n / cols), cell };
}

/* 时间：这一镜第 at 句的第 beat 拍 */
const T = (c, at, beat) => (Number(at) || 0) * c.bar + (clamp(Number(beat) || 1, 1, 4) - 1) * c.beat;
const hit = (c, t, dur = 0.18) => E.out3(seg(c.lt, t, t + dur));

/* 这一刻这样东西的状态：出场 + 之前所有动作叠上去 */
function stateOf(it, acts, c) {
  const t0 = T(c, it.at, it.beat), st = { k: hit(c, t0), on: c.lt >= t0 - 0.001, x: it.x, y: it.y, s: 1, a: 1, col: null, text: it.text, value: it.value,
    fill: it.value, mark: it.mark || 0, strike: 0, cross: 0, check: 0, flash: 0, shake: 0, hide: 0 };
  if (it.kind === 'num' && st.on) { const from = it.from == null ? 0 : Number(it.from); st.value = lerp(from, Number(it.value), E.out3(seg(c.lt, t0, t0 + 0.25))); }
  if (it.kind === 'bar') st.fill = (it.value == null ? 0 : Number(it.value)) * E.out3(seg(c.lt, t0 + c.beat, t0 + c.beat + 0.25));   // 第 1 拍条出来，第 2 拍走到值
  for (const a of acts) {
    const t = T(c, a.at, a.beat); if (c.lt < t - 0.001) continue;
    const k = hit(c, t), kk = E.out3(seg(c.lt, t, t + 0.25));
    switch (a.do) {
      case 'strike': st.strike = k; break;
      case 'cross': st.cross = k; break;
      case 'check': st.check = k; break;
      case 'flash': st.flash = Math.max(st.flash, Math.exp(-(c.lt - t) / 0.18)); break;
      case 'dim': st.a = lerp(st.a, 0.28, k); break;
      case 'hide': st.hide = k; break;
      case 'move': st.x = lerp(st.x, a.x == null ? st.x : a.x, kk); st.y = lerp(st.y, a.y == null ? st.y : a.y, kk); break;
      case 'grow': st.s = lerp(st.s, a.s == null ? 1.3 : Number(a.s), kk); break;
      case 'count': st.value = lerp(Number(st.value), Number(a.to), kk); st.countTo = a.to; break;
      case 'fill': st.fill = lerp(Number(st.fill) || 0, Number(a.to), kk); if (a.text != null && k > 0.5) st.text = a.text; break;
      case 'swap': if (k > 0.5) st.text = a.text; st.swapK = k; break;
      case 'color': st.col = a.color; st.colK = k; break;
      case 'mark': st.mark = Math.round(lerp(st.mark, Number(a.to), k)); break;
      case 'shake': st.shake = Math.max(st.shake, Math.exp(-(c.lt - t) / 0.25) * (1 - seg(c.lt, t, t + 0.6))); break;
    }
  }
  return st;
}

/* ---------- 各种东西怎么画（中心在 0,0） ---------- */
function drawRows(fr, c, it, rows, x0, y0, w, t0, bubble, col) {
  rows.forEach((r, i) => {
    const t = t0 + (i + 1) * c.beat, k = hit(c, t); if (k <= 0) return;   // 卡片在这一拍出来，里面一行一拍往下写
    const y = y0 + i * ROW + ROW / 2, me = r && typeof r === 'object' && r.me != null, txt = r && typeof r === 'object' ? (r.me != null ? r.me : r.them != null ? r.them : r.text) : r;
    fr.g({ a: k, at: [0, (1 - k) * 10] }, () => {
      if (bubble || (r && typeof r === 'object' && (r.me != null || r.them != null))) {
        let z = 38; while (z > 26 && estW(txt, z) > w * 0.78) z -= 2;
        const bw = Math.min(w * 0.86, estW(txt, z) + 44), bx = me ? x0 + w - bw : x0;
        fr.rect(bx, y - 26, bw, 52, { r: 18, fill: me ? col : '#1B2038', fa: me ? 0.85 : 0.95 });
        fr.text(txt, bx + bw / 2, y, { font: 'sansh', size: z, color: me ? INK.base : INK.white });
      } else {
        let z = 40; while (z > 26 && estW(txt, z) > w - 40) z -= 2;
        fr.circle(x0 + 12, y, 6, { fill: col });
        fr.text(txt, x0 + 34, y, { font: 'sansh', size: z, color: INK.white, align: 'l' });
      }
    });
  });
}

function drawItem(fr, c, it, st, b, ids) {
  const col = st.col ? colorOf(st.col, c, c.col) : colorOf(it.color, c, it.kind === 'text' ? INK.white : c.col);
  const t0 = T(c, it.at, it.beat), k = st.k;
  switch (it.kind) {
    case 'icon': {
      const name = ICONS[it.icon] || (window.LUCIDE && LUCIDE[it.icon]) ? it.icon : 'box';
      drawIcon(fr, name, 0, -b.dy, b.s, col, k);
      if (it.label) fr.text(st.swapK != null ? String(st.text) : it.label, 0, b.s / 2 - b.dy + 34, { font: 'sansh', size: 40, color: INK.text, a: hit(c, t0 + (b.s ? 0.06 : 0)) });
      break;
    }
    case 'text': {
      const z = b.z; let size = z; const str = String(st.text); while (size > 30 && fr.measure(str, { font: 'sansh', size }) > CW) size -= 4;
      fr.text(str, 0, 0, { font: 'sansh', size, color: col, glow: size >= 80 ? 22 : 10, a: k * (st.swapK != null ? 0.4 + 0.6 * Math.abs(st.swapK * 2 - 1) : 1) });
      break;
    }
    case 'num': {
      const str = numStr(it, st.countTo != null && Math.abs(st.value - st.countTo) < 1e-9 ? st.countTo : Number.isInteger(Number(it.value)) && (st.countTo == null || Number.isInteger(Number(st.countTo))) ? Math.round(st.value) : Number(st.value).toFixed(1));
      let size = b.z; while (size > 40 && fr.measure(str, { font: 'sansh', size }) > CW) size -= 6;
      fr.text(str, 0, 0, { font: 'sansh', size, color: col, glow: 26, a: k });
      if (it.label) fr.text(it.label, 0, size * 0.62 + 10, { font: 'sansr', size: 36, color: INK.dim, a: hit(c, t0 + c.beat) });   // 第 2 拍：这个数是什么
      break;
    }
    case 'box': {
      const w = b.w, h = b.h, x0 = -w / 2, y0 = -h / 2;
      fr.rect(x0, y0, w, h, { r: 20, fill: INK.card, fa: 0.82 * k });
      fr.rect(x0, y0, w, h, { r: 20, color: col, w: 2.5, a: 0.7 * k, glow: 10 });
      let y = y0 + PAD / 2;
      if (it.title) {
        if (it.icon) drawIcon(fr, ICONS[it.icon] || (window.LUCIDE && LUCIDE[it.icon]) ? it.icon : 'box', x0 + 52, y + TITLE / 2 - 4, 54, col, k);
        fr.text(it.title, x0 + (it.icon ? 96 : 32), y + TITLE / 2 - 4, { font: 'sansh', size: 46, color: col, align: 'l', a: k, glow: 10 });
        fr.rect(x0 + 24, y + TITLE - 6, w - 48, 1.5, { fill: '#FFFFFF', a: 0.12 * k }); y += TITLE;
      }
      drawRows(fr, c, it, it.rows || [], x0 + 30, y + 4, w - 60, t0, false, col);
      break;
    }
    case 'phone': {
      const w = b.w, h = b.h, x0 = -w / 2, y0 = -h / 2, r = w * 0.13;
      fr.rect(x0, y0, w, h, { r, fill: '#070912', fa: 0.95 * k });
      fr.rect(x0, y0, w, h, { r, color: col, w: 5, a: k, glow: 16 });
      fr.rect(-w * 0.14, y0 + 18, w * 0.28, 14, { r: 7, fill: col, fa: 0.6 * k });
      const sx = x0 + 22, sw = w - 44; let y = y0 + 52;
      if (it.title) {
        fr.rect(sx, y, sw, 64, { r: 12, fill: col, fa: 0.16 * k });
        if (it.live) { fr.rect(sx + 12, y + 16, 82, 32, { r: 8, fill: NEON.red.main, fa: k }); fr.text('LIVE', sx + 53, y + 33, { font: 'sansh', size: 22, color: '#fff', a: k }); }
        fr.text(it.title, sx + sw / 2 + (it.live ? 40 : 0), y + 33, { font: 'sansh', size: 36, color: INK.white, a: k }); y += 84;
      }
      if (it.icon && !(it.rows || []).length) drawIcon(fr, ICONS[it.icon] || (window.LUCIDE && LUCIDE[it.icon]) ? it.icon : 'box', 0, (y + y0 + h - 40) / 2 - 0, sw * 0.6, col, k);
      drawRows(fr, c, it, it.rows || [], sx + 6, y, sw - 12, t0, !!it.chat, col);
      fr.rect(-w * 0.18, y0 + h - 26, w * 0.36, 7, { r: 4, fill: '#FFFFFF', fa: 0.35 * k });
      break;
    }
    case 'crowd': {
      const g = b.g, w = b.w, h = b.h, icon = it.icon && (ICONS[it.icon] || (window.LUCIDE && LUCIDE[it.icon])) ? it.icon : 'person';
      for (let i = 0; i < g.n; i++) {
        const batch = Math.min(3, Math.floor(i * 4 / g.n)), kk = hit(c, t0 + batch * c.beat, 0.16); if (kk <= 0) continue;   // 四拍分四批冒出来
        const r = Math.floor(i / g.cols), inRow = r === g.rows - 1 ? g.n - r * g.cols : g.cols;   // 最后一行不满就居中
        const cx = -w / 2 + (i % g.cols + 0.5 + (g.cols - inRow) / 2) * g.cell, cy = -h / 2 + (r + 0.5) * g.cell, on = i < st.mark;
        drawIcon(fr, icon, cx, cy, g.cell * 0.98, on ? col : INK.dim, kk * (on ? 1 : 0.6));
      }
      break;
    }
    case 'bar': {
      const w = b.w, by = it.label ? 22 : -18, x0 = -w / 2;
      if (it.label) fr.text(it.label, x0, -30, { font: 'sansh', size: 40, color: INK.text, align: 'l', a: k });
      fr.rect(x0, by, w, 36, { r: 18, fill: '#FFFFFF', fa: 0.08 * k });
      fr.rect(x0, by, w * clamp(Number(st.fill) || 0), 36, { r: 18, fill: col, fa: k, glow: 16 });
      if (st.text != null) fr.text(String(st.text), -x0, -30, { font: 'sansh', size: 44, color: col, align: 'r', a: hit(c, t0 + c.beat) });
      break;
    }
  }
}

/* 划掉 / 打叉 / 打勾：盖在这样东西占的那块地方上 */
function marks(fr, it, st, b) {
  const w = b.w / 2 + 10, h = b.h / 2 + 6, red = NEON.red.main;
  if (st.strike > 0) {
    if (it.kind === 'text' || it.kind === 'num' || it.kind === 'bar') fr.line(-w, 0, -w + 2 * w * st.strike, 0, { color: red, w: 8, glow: 14 });
    else fr.line(-w * 0.8, -h * 0.8, -w * 0.8 + 1.6 * w * st.strike, -h * 0.8 + 1.6 * h * st.strike, { color: red, w: 9, glow: 14 });
  }
  if (st.cross > 0) {
    const r = Math.min(w, h) * 0.8 * (0.6 + 0.4 * st.cross);
    fr.line(-r, -r, r, r, { color: red, w: 11, a: st.cross, glow: 16 }); fr.line(r, -r, -r, r, { color: red, w: 11, a: st.cross, glow: 16 });
  }
  if (st.check > 0) {
    const cx = w - 26, cy = -h + 26, s = lerp(1.6, 1, st.check);
    fr.g({ at: [cx, cy], s, a: st.check }, () => { fr.circle(0, 0, 30, { fill: NEON.green.main, glow: 16 }); fr.poly([[-14, 0], [-4, 11], [15, -11]], { color: INK.base, w: 7 }); });
  }
}

/* 连线的端点：贴着那样东西的边，不插进它中间 */
function anchor(ref, other, ids, c) {
  if (Array.isArray(ref)) return [X0 + ref[0] * CW, ZT + ref[1] * ZH, 0, 0];
  const e = ids[ref]; if (!e) return null;
  return [X0 + e.st.x * CW, ZT + e.st.y * ZH, e.b.w / 2 + 14, e.b.h / 2 + 14];
}
function drawLink(fr, c, it, ids) {
  const p = anchor(it.from, it.to, ids, c), q = anchor(it.to, it.from, ids, c); if (!p || !q) return;
  const t0 = T(c, it.at, it.beat), k = E.io3(seg(c.lt, t0, t0 + 0.25)); if (c.lt < t0 - 0.001) return;
  const dx = q[0] - p[0], dy = q[1] - p[1], L = Math.hypot(dx, dy) || 1, ux = dx / L, uy = dy / L;
  const cut = (hw, hh) => Math.min(hw / Math.max(Math.abs(ux), 1e-3), hh / Math.max(Math.abs(uy), 1e-3));   // 射线走出这块矩形的距离
  const a = cut(p[2], p[3]), z = cut(q[2], q[3]), x1 = p[0] + ux * a, y1 = p[1] + uy * a, x2 = q[0] - ux * z, y2 = q[1] - uy * z;
  const xe = lerp(x1, x2, k), ye = lerp(y1, y2, k), col = colorOf(it.color, c, c.col), st = stateOf(it, [], c);
  fr.line(x1, y1, xe, ye, { color: col, w: 6, glow: 14, dash: it.dash ? [18, 14] : null, a: st.a });
  if (it.kind === 'arrow' && k > 0.85) { const h = 26, ang = Math.atan2(uy, ux); fr.poly([[xe - h * Math.cos(ang - 0.45), ye - h * Math.sin(ang - 0.45)], [xe, ye], [xe - h * Math.cos(ang + 0.45), ye - h * Math.sin(ang + 0.45)]], { color: col, w: 6, glow: 14 }); }
  if (it.label) {   // 标签放在线的一侧（横着的线放上面，竖着的线放右边），第 2 拍出来
    const lk = hit(c, t0 + c.beat), nx = Math.abs(uy) > 0.5 ? 1 : 0, ny = Math.abs(uy) > 0.5 ? 0 : -1, lw = estW(it.label, 40);
    fr.text(it.label, (x1 + x2) / 2 + nx * (lw / 2 + 24), (y1 + y2) / 2 + ny * 50, { font: 'sansh', size: 40, color: col, a: lk, glow: 10 });
  }
}

SCENES.draw = function (fr, c) {
  const items = (c.d.items || []).map(x => Object.assign({}, x)); autoLayout(items);
  const acts = c.d.acts || [], ids = {};
  items.forEach((it, i) => { const id = it.id || ('#' + i); const st = stateOf(it, acts.filter(a => a.id === id), c); ids[id] = { it, st, b: boxOf(it) }; it._id = id; });
  // 先画连线（压在东西下面），再按出场顺序画东西
  items.filter(it => it.kind === 'arrow' || it.kind === 'line').forEach(it => drawLink(fr, c, it, ids));
  items.filter(it => it.kind !== 'arrow' && it.kind !== 'line').forEach(it => {
    const { st, b } = ids[it._id]; if (!st.on || st.hide >= 1) return;
    const x = X0 + st.x * CW + Math.sin(c.lt * 60) * 14 * st.shake, y = ZT + st.y * ZH;
    fr.g({ at: [x, y], s: st.s * (1 + 0.08 * st.flash) * (0.88 + 0.12 * st.k), a: st.a * (1 - st.hide) }, () => {
      if (st.flash > 0.02) fr.glow(0, 0, Math.max(b.w, b.h) * 0.7, colorOf(st.col || it.color, c, c.col), 0.35 * st.flash);
      drawItem(fr, c, it, st, b, ids); marks(fr, it, st, b);
    });
  });
};
/* 盖章放哪：右下 → 左下 → 右上 → 左上 → 正中下，第一个不压东西的地方（scripts/draw_check.py 的 stamp_spot 同一套） */
const STAMP_SPOTS = [[0.64, 1350], [0.36, 1350], [0.64, 560], [0.36, 560], [0.5, 1350]];
function stampSpot(d, w, h) {
  const items = (d.items || []).map(x => Object.assign({}, x)); autoLayout(items);
  const rs = items.filter(it => it.kind !== 'arrow' && it.kind !== 'line').map(it => { const b = boxOf(it), cx = X0 + it.x * CW, cy = ZT + it.y * ZH; return [cx - b.w / 2, cy - b.h / 2, cx + b.w / 2, cy + b.h / 2]; });
  for (const [fx, y] of STAMP_SPOTS) {
    const x = W * fx, r = [x - w / 2, y - h / 2, x + w / 2, y + h / 2];
    if (!rs.some(q => Math.min(r[2], q[2]) > Math.max(r[0], q[0]) && Math.min(r[3], q[3]) > Math.max(r[1], q[1]))) return [x, y];
  }
  return [W * 0.64, 1350];
}
window.DRAW = { autoLayout, boxOf, T, X0, CW, ZT, ZH, stampSpot };
})();
