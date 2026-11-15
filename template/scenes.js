/* scenes.js — 霓虹风格的画面件。每个件是 SCENES[type](fr, c)：
 *   c.d    这一镜在 film.json 里的数据（shot）
 *   c.lt   这一镜开始后过了几秒；c.step 这一镜走到第几句（0 起）；c.st 当前这句开始后几秒
 *   c.span 这一镜一共几句；c.bar 一小节几秒；c.beat 一拍几秒；c.col / c.alt 章节主色 / 辅色
 * 规矩：画面只由 t 决定（不用 Math.random、不跨帧存状态）；一镜一个主体，一句一步往上加东西；
 *      内容放在 y 400–1400 之间（上面是顶栏和小标题，下面是字幕和平台遮挡区）。
 * 新写一个件：照下面的样子加一个函数，再到 references/03 的件表里登记它吃哪些字段。
 */
(function () {
'use strict';
const { W, H, clamp, lerp, seg, ss, fade, E, hash, rgba, mix } = VK;
const CX = W / 2, X0 = 96, XR = W - 96, CW = XR - X0;

/* 第 i 个（共 n 个）东西什么时候出场：一句一个；比句子多的，挤在最后一句里按拍子出 */
function at(c, i, n) {
  if (n <= c.span || i < c.span - 1) return i * c.bar;
  return (c.span - 1) * c.bar + (i - (c.span - 1)) * c.beat;
}
/* 到现在为止出场的最后一个是第几个 */
function current(c, n) { let k = -1; for (let i = 0; i < n; i++) if (c.lt >= at(c, i, n) - 0.001) k = i; return k; }

function fmt(v, dec) {
  const s = Math.abs(v).toFixed(dec || 0), [a, b] = s.split('.');
  return (v < 0 ? '-' : '') + a.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (b ? '.' + b : '');
}
function decimalsOf(vals) { return Math.max(0, ...vals.map(v => (String(v).split('.')[1] || '').length)); }

/* 卡片：深色半透明底 + 章节色描边 + 外发光 */
function card(fr, x, y, w, h, col, o = {}) {
  const a = o.a == null ? 1 : o.a; if (a <= 0) return;
  fr.rect(x, y, w, h, { r: o.r || 22, fill: INK.card, fa: 0.78 * a });
  fr.rect(x, y, w, h, { r: o.r || 22, color: col, w: o.lw || 2, a: (o.edge == null ? 0.55 : o.edge) * a, glow: o.glow || 0 });
}
/* 一行大字自动缩到放得下 */
function fit(fr, str, font, max, width, track = 0) {
  let s = max; while (s > 24 && fr.measure(str, { font, size: s, track }) > width) s -= 4; return s;
}

const SCENES = {

  /* 片名卡：{kicker?, top, big, bottom} —— 左对齐，big 是全片最大的字 */
  title(fr, c) {
    const d = c.d, lt = c.lt, Y = 860;
    const k1 = E.out3(seg(lt, 0.0, 0.35)), k2 = E.out5(seg(lt, 0.12, 0.55)), k3 = E.out3(seg(lt, 0.45, 0.85));
    if (d.kicker) fr.g({ a: k1 }, () => {
      fr.rect(X0, Y - 300, 48, 3, { fill: c.col });
      fr.text(String(d.kicker).toUpperCase(), X0 + 64, Y - 300, { font: 'sans', size: 26, track: 8, color: c.col, align: 'l', glow: 12 });
    });
    if (d.top) fr.text(d.top, X0, Y - 210 + (1 - k1) * 20, { font: 'sansh', size: 72, track: 6, color: INK.text, align: 'l', a: k1 * 0.9 });
    const big = String(d.big || ''), size = fit(fr, big, 'sansh', 300, CW, 4);
    fr.g({ at: [X0, Y], s: lerp(1.18, 1, k2) }, () => {
      fr.text(big, 0, 0, { font: 'sansh', size, track: 4, align: 'l', a: k2, grad: [[0, '#FFFFFF'], [0.55, mix('#FFFFFF', c.col, 0.35)], [1, c.col]], glow: 40, glowColor: c.col, glowA: 0.55 });
    });
    if (d.bottom) fr.g({ a: k3 }, () => {
      fr.rect(X0, Y + size * 0.62 + 10, 90 * k3, 6, { fill: c.col, glow: 16 });
      fr.text(d.bottom, X0 + 120, Y + size * 0.62 + 12, { font: 'sansh', size: 70, track: 3, color: INK.white, align: 'l' });
    });
    if (c.step > 0) fr.glow(X0 + 200, Y, 420, c.col, 0.06 * Math.sin(c.lt * 2));
  },

  /* 一句话立住：{top?, big, sub?} —— 提问、结论、片尾都用它，居中 */
  statement(fr, c) {
    const d = c.d, lt = c.lt, Y = 860;
    const k = E.out5(seg(lt, 0.0, 0.5)), k2 = E.out3(seg(lt, 0.3, 0.7));
    if (d.top) fr.text(d.top, CX, Y - 190, { font: 'sansh', size: 46, track: 10, color: INK.text, a: k * 0.9 });
    const big = String(d.big || ''), size = fit(fr, big, 'sansh', 240, CW, 6);
    fr.text(big, CX, Y, { font: 'sansh', size, track: lerp(40, 6, k), a: k, grad: [[0, '#FFFFFF'], [1, c.col]], glow: 46, glowColor: c.col, glowA: 0.6 });
    if (d.sub) fr.text(d.sub, CX, Y + size * 0.5 + 90, { font: 'sansh', size: 50, track: 3, color: INK.white, a: k2 });
    fr.line(CX - 160 * k2, Y + size * 0.5 + 30, CX + 160 * k2, Y + size * 0.5 + 30, { color: c.col, w: 3, a: 0.8 * k2, glow: 12 });
  },

  /* 大数字：{values:[199, 39], prefix:'¥', suffix:'', unit:'今天', units:['三年前','今天'], bar?:{label, pct, tag}}
   * 每句换到下一个值，旧值留一个虚影；bar 是下面一条"钱去哪了"的条 */
  number(fr, c) {
    const d = c.d, vals = (d.values || [d.value || 0]).map(Number), dec = decimalsOf(vals);
    const n = vals.length, i = Math.max(0, current(c, n)), prev = i > 0 ? vals[i - 1] : (d.from != null ? Number(d.from) : 0);
    const ti = at(c, i, n), packed = n > c.span && i >= c.span - 1;   // 比句子多的值挤在最后一句里按拍子换
    const k = E.out3(seg(c.lt, ti, ti + (i === 0 && d.from == null ? 0.05 : packed ? 0.4 : 0.7)));
    const v = lerp(prev, vals[i], k), Y = 720;
    const str = fmt(v, dec), u = (d.units && d.units[i]) || d.unit || '';
    const groupW = sz => (d.prefix ? fr.measure(d.prefix, { font: 'sansh', size: sz * 0.45 }) + 14 : 0) + fr.measure(fmt(vals[i], dec) + (d.suffix || ''), { font: 'sansh', size: sz, track: -4 }) + (u ? 16 + fr.measure(u, { font: 'sansm', size: 36 }) : 0);
    let size = 300; while (size > 60 && groupW(size) > CW - 20) size -= 6;
    if (i > 0) fr.text((d.prefix || '') + fmt(prev, dec) + (d.suffix || ''), CX + 30, Y - 40, { font: 'sansh', size, track: -4, color: c.alt, a: 0.18 * (1 - 0.5 * k), blur: 3 });
    const ent = E.out3(seg(c.lt, 0, 0.35));
    fr.g({ at: [CX, Y], s: lerp(0.86, 1, ent) * (1 + 0.04 * (1 - seg(c.lt, ti, ti + 0.25)) * (i > 0 ? 1 : 0)) }, () => {
      const pw = d.prefix ? fr.measure(d.prefix, { font: 'sansh', size: size * 0.45 }) + 14 : 0;
      const nw = fr.measure(str + (d.suffix || ''), { font: 'sansh', size, track: -4 }), uw = u ? 16 + fr.measure(u, { font: 'sansm', size: 36 }) : 0, x0 = -(pw + nw + uw) / 2;
      if (d.prefix) fr.text(d.prefix, x0, -size * 0.12, { font: 'sansh', size: size * 0.45, color: c.col, align: 'l', a: ent, glow: 20 });
      fr.text(str + (d.suffix || ''), x0 + pw, 0, { font: 'sansh', size, track: -4, align: 'l', a: ent, grad: [[0, '#FFFFFF'], [1, mix('#FFFFFF', c.col, 0.45)]], glow: 34, glowColor: c.col, glowA: 0.5 });
      if (u) fr.text(u, x0 + pw + nw + 16, size * 0.22, { font: 'sansm', size: 36, color: INK.dim, align: 'l', a: ent });
    });
    if (d.bar) {
      const b = d.bar, by = 1080, kb = E.out3(seg(c.lt, 0.3, 1.1));
      fr.text(b.label || '', X0, by - 46, { font: 'sans', size: 32, track: 2, color: INK.text, align: 'l', a: kb });
      if (b.tag) fr.text(b.tag, XR, by - 46, { font: 'sansh', size: 34, color: NEON.green.main, align: 'r', a: kb, glow: 12 });
      card(fr, X0, by, CW, 66, c.col, { a: kb, r: 12, edge: 0.3 });
      const p = clamp(Number(b.pct || 0) / 100) * kb;
      fr.rect(X0 + 8, by + 8, (CW - 16) * p, 50, { r: 8, fill: c.col, fa: 0.85, glow: 18 });
    }
  },

  /* 横条对比：{rows:[{label, value, tag?}], unit?:'%', max?} —— 一句亮一条，最新的那条最亮 */
  bars(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n);
    const max = Number(d.max) || Math.max(...rows.map(r => Number(r.value) || 0), 1);
    const gap = Math.min(170, 900 / Math.max(n, 1)), y0 = 470 + (900 - gap * n) / 2;
    rows.forEach((r, i) => {
      const a0 = at(c, i, n), k = E.out3(seg(c.lt, a0, a0 + 0.45)); if (k <= 0) return;
      const y = y0 + i * gap, hot = i === cur, dim = hot ? 1 : 0.5;
      fr.text(r.label, X0, y, { font: 'sansh', size: 40, color: INK.white, align: 'l', a: k * dim });
      const val = (Number(r.value) || 0) * E.out3(seg(c.lt, a0 + 0.1, a0 + 0.8));
      fr.text(fmt(val, decimalsOf([r.value])) + (d.unit || ''), XR, y, { font: 'sansh', size: 46, color: hot ? c.col : INK.text, align: 'r', a: k, glow: hot ? 18 : 0 });
      fr.rect(X0, y + 46, CW, 16, { r: 8, fill: '#FFFFFF', fa: 0.07 * k });
      fr.rect(X0, y + 46, CW * clamp(val / max), 16, { r: 8, fill: hot ? c.col : mix(c.col, '#444', 0.5), fa: k, glow: hot ? 16 : 0 });
      if (r.tag) fr.text(r.tag, X0, y + 96, { font: 'sansr', size: 26, color: INK.dim, align: 'l', a: k * dim });
    });
  },

  /* 环形占比：{value:40, suffix:'%', label:'利润被吃掉', rows:[{text, tag?}]} —— 环先转满，再一句点一条原因 */
  ring(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n), cy = 720, R = 230;
    const k = E.out3(seg(c.lt, 0, 0.9)), v = Number(d.value || 0) * k;
    for (let j = 0; j < 3; j++) fr.arc(CX, cy, R + 38 + j * 22, c.lt * (0.3 + j * 0.2) + j, c.lt * (0.3 + j * 0.2) + j + 1.2 + j * 0.6, { color: j === 1 ? c.alt : c.col, w: 2, a: 0.25 * k });
    fr.circle(CX, cy, R, { color: '#FFFFFF', w: 18, a: 0.07 * k });
    fr.arc(CX, cy, R, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * clamp(v / 100), { color: c.col, w: 18, a: k, glow: 26 });
    if (d.label) fr.text(d.label, CX, cy - 82, { font: 'sans', size: 30, track: 4, color: INK.text, a: k });
    fr.text(fmt(v, decimalsOf([d.value])) + (d.suffix == null ? '%' : d.suffix), CX, cy + 14, { font: 'sansh', size: 128, color: INK.white, a: k, glow: 30, glowColor: c.col, glowA: 0.6 });
    rows.forEach((r, i) => {
      const a0 = at(c, i, n) + (c.span > 1 && i === 0 ? 0.6 : 0), kk = E.out3(seg(c.lt, a0, a0 + 0.4)); if (kk <= 0) return;
      const y = 1060 + i * 82, hot = i === cur;
      card(fr, X0, y - 32, CW, 64, c.col, { a: kk * (hot ? 1 : 0.6), r: 14, edge: hot ? 0.7 : 0.25, glow: hot ? 14 : 0 });
      fr.circle(X0 + 34, y, 9, { fill: hot ? c.col : INK.dim, a: kk, glow: hot ? 12 : 0 });
      fr.text(r.text, X0 + 62, y, { font: 'sansh', size: 36, color: hot ? INK.white : INK.text, align: 'l', a: kk });
      if (r.tag) fr.text(r.tag, XR - 24, y, { font: 'sans', size: 28, color: hot ? c.col : INK.dim, align: 'r', a: kk });
    });
  },

  /* 人生节点：{nodes:[{label, sub}], breakAt?: 2, breakStep?: 1} —— 第一句节点按拍子一个个亮；
   * breakStep 那一句，第 breakAt 个节点之后裂开、变灰（breakAt 不写就不裂） */
  timeline(fr, c) {
    const d = c.d, nodes = d.nodes || [], n = nodes.length, y = 820, red = NEON.red.main;
    const xs = nodes.map((_, i) => n === 1 ? CX : X0 + 40 + (CW - 80) * i / (n - 1));
    const brk = d.breakAt != null ? Number(d.breakAt) : -1, bs = d.breakStep != null ? Number(d.breakStep) : 1;
    const bt = bs * c.bar, kb = brk >= 0 ? E.out3(seg(c.lt, bt, bt + 0.3)) : 0;
    const shake = kb > 0 ? Math.sin(c.lt * 70) * 10 * (1 - seg(c.lt, bt, bt + 0.4)) : 0;
    const per = Math.min(c.beat, (c.bar * 0.9) / Math.max(n, 1));
    fr.g({ at: [shake, 0] }, () => {
      const kl = E.out3(seg(c.lt, 0, per * n));
      fr.line(xs[0], y, lerp(xs[0], xs[n - 1], kl), y, { color: c.col, w: 4, a: 0.8, glow: 14 });
      if (kb > 0 && brk < n - 1) {
        const xa = xs[brk] + 30, xb = xs[brk + 1] - 30, mid = (xa + xb) / 2;
        fr.rect(xa, y - 14, xb - xa, 28, { fill: INK.base, fa: kb });
        fr.poly([[mid - 30, y - 50], [mid + 8, y - 12], [mid - 10, y + 10], [mid + 30, y + 54]], { color: red, w: 5, a: kb, glow: 22, k: kb });
        fr.line(xb, y, xs[n - 1], y, { color: '#5A6075', w: 4, a: kb });
      }
      nodes.forEach((nd, i) => {
        const a0 = i * per, k = E.out3(seg(c.lt, a0, a0 + 0.3)); if (k <= 0) return;
        const lost = kb > 0 && i > brk, colr = lost ? mix(c.col, '#5A6075', kb) : c.col, up = i % 2 === 0;
        fr.circle(xs[i], y, 22 * k, { fill: INK.base, color: colr, w: 5, glow: lost ? 0 : 20 });
        fr.circle(xs[i], y, 8 * k, { fill: colr });
        fr.line(xs[i], y + (up ? -30 : 30), xs[i], y + (up ? -70 : 70), { color: colr, w: 2, a: 0.5 * k });
        fr.text(nd.label, xs[i], y + (up ? -110 : 110), { font: 'sansh', size: fit(fr, nd.label, 'sansh', 58, (CW / Math.max(n - 1, 1)) * 1.6), color: lost ? '#6A7088' : INK.white, a: k });
        if (nd.sub) fr.text(nd.sub, xs[i], y + (up ? -178 : 176), { font: 'mono', size: 38, color: lost ? '#555A70' : c.col, a: k, glow: lost ? 0 : 10 });
      });
    });
    if (kb > 0) fr.flash(0.18 * (1 - seg(c.lt, bt, bt + 0.3)), red);
  },

  /* 岔路：{paths:[{label, sub}], pick: 2} —— 第一句路长出来，之后每句划掉一条，最后一句点亮 pick */
  fork(fr, c) {
    const d = c.d, paths = d.paths || [], n = paths.length, pick = d.pick != null ? Number(d.pick) : n - 1;
    const ox = CX, oy = 1300, cy = 640, cw = Math.min(300, (CW - 30 * (n - 1)) / n), ch = 170;
    const xs = paths.map((_, i) => X0 + cw / 2 + i * (CW - cw) / Math.max(n - 1, 1));
    const kills = paths.map((_, i) => i).filter(i => i !== pick);
    const killAt = i => { const j = kills.indexOf(i); if (j < 0) return 1e9; const steps = Math.max(c.span - 2, 1); return c.span <= 1 ? 0.5 + j * c.beat : (1 + Math.min(j, steps - 1)) * c.bar + Math.max(0, j - (steps - 1)) * c.beat; };
    const pickAt = c.span <= 1 ? 0.5 + kills.length * c.beat : Math.max(c.span - 1, 1) * c.bar;
    fr.spark(ox, oy, 8, c.col, E.out3(seg(c.lt, 0, 0.3)));
    paths.forEach((p, i) => {
      const k = E.out3(seg(c.lt, 0.05 + i * 0.12, 0.6 + i * 0.12)), kx = ss(c.lt, killAt(i), killAt(i) + 0.3), kp = i === pick ? E.out3(seg(c.lt, pickAt, pickAt + 0.4)) : 0;
      const pts = []; for (let s = 0; s <= 24; s++) { const u = s / 24; pts.push([lerp(ox, xs[i], E.io3(u)), lerp(oy, cy + ch / 2, u)]); }
      fr.poly(pts, { color: kp > 0 ? c.col : '#8A90A8', w: kp > 0 ? 5 : 2.5, a: (0.7 - 0.45 * kx) * (kp > 0 ? 1 : 1), k, glow: kp > 0 ? 18 : 0 });
      if (k <= 0) return;
      const x = xs[i] - cw / 2, y = cy - ch / 2;
      fr.g({ at: [xs[i], cy], s: 1 + 0.08 * kp }, () => {
        card(fr, -cw / 2, -ch / 2, cw, ch, kp > 0 ? c.col : '#8A90A8', { a: k * (1 - 0.55 * kx), edge: kp > 0 ? 0.9 : 0.4, glow: kp > 0 ? 24 : 0 });
        const ls = fit(fr, p.label, 'sansh', 48, cw - 30);
        fr.text(p.label, 0, -22, { font: 'sansh', size: ls, color: kp > 0 ? c.col : INK.white, a: k * (1 - 0.55 * kx), glow: kp > 0 ? 18 : 0 });
        if (p.sub) fr.text(p.sub, 0, 40, { font: 'sans', size: Math.min(28, fit(fr, p.sub, 'sans', 28, cw - 30)), color: INK.dim, a: k * (1 - 0.4 * kx) });
      });
      if (kx > 0) fr.line(x + 18, cy, x + 18 + (cw - 36) * kx, cy, { color: NEON.red.main, w: 6, glow: 14 });
    });
  },

  /* 一组对比：{left:{label, value, sub?}, right:{label, value, sub?}, badge?:{label, value}}
   * 第一句只出左边；第二句（只有一句就第三拍）箭头走过去，出右边和角标 */
  compare(fr, c) {
    const d = c.d, L = d.left || {}, R = d.right || {}, y = 560, h = 440;
    const tr = c.span > 1 ? c.bar : c.beat * 2;
    const k1 = E.out3(seg(c.lt, 0, 0.4)), ka = E.out3(seg(c.lt, tr, tr + 0.5)), k2 = E.out3(seg(c.lt, tr + 0.25, tr + 0.7)), kb = E.out5(seg(c.lt, tr + 0.6, tr + 1.0));
    card(fr, X0, y, CW, h, c.col, { a: k1, edge: 0.35 });
    fr.text(L.label || '', X0 + 50, y + 80, { font: 'sans', size: 32, track: 3, color: INK.dim, align: 'l', a: k1 });
    const ls = fit(fr, String(L.value), 'sansh', 110, CW * 0.4);
    fr.text(String(L.value || ''), X0 + 50, y + 190, { font: 'sansh', size: ls, color: INK.white, align: 'l', a: k1 });
    if (L.sub) fr.text(L.sub, X0 + 50, y + 280, { font: 'sansr', size: 28, color: INK.dim, align: 'l', a: k1 });
    const ax0 = X0 + 60, ax1 = XR - 60, ay = y + 360;
    fr.line(ax0, ay, lerp(ax0, ax1, ka), ay, { color: c.col, w: 3, a: 0.9, glow: 12 });
    if (ka > 0 && ka < 1) fr.spark(lerp(ax0, ax1, ka), ay, 7, c.col, 1);
    if (ka >= 1) fr.poly([[ax1 - 18, ay - 12], [ax1, ay], [ax1 - 18, ay + 12]], { color: c.col, w: 3, glow: 10 });
    fr.text(R.label || '', XR - 50, y + 80, { font: 'sans', size: 32, track: 3, color: INK.dim, align: 'r', a: k2 });
    const rs = fit(fr, String(R.value), 'sansh', 130, CW * 0.45);
    fr.text(String(R.value || ''), XR - 50, y + 190 + (1 - k2) * 20, { font: 'sansh', size: rs, color: c.col, align: 'r', a: k2, glow: 30 });
    if (R.sub) fr.text(R.sub, XR - 50, y + 280, { font: 'sansr', size: 28, color: INK.dim, align: 'r', a: k2 });
    if (d.badge && kb > 0) fr.g({ at: [CX, y + h + 120], s: lerp(1.3, 1, kb) }, () => {
      card(fr, -170, -70, 340, 140, NEON.green.main, { a: kb, edge: 0.9, glow: 20, r: 18 });
      fr.text(d.badge.label || '', 0, -28, { font: 'sans', size: 28, color: NEON.green.alt, a: kb });
      fr.text(String(d.badge.value || ''), 0, 26, { font: 'sansh', size: 60, color: NEON.green.main, a: kb, glow: 18 });
    });
  },

  /* 打勾清单：{title?, rows:[{text, ok?:true|false, note?}]} —— 一句勾一条；ok:false 画一道横线、发灰 */
  checklist(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n);
    const gap = Math.min(150, 760 / Math.max(n, 1)), y0 = 560 + (760 - gap * n) / 2;
    if (d.title) fr.text(d.title, X0, y0 - 90, { font: 'sansh', size: 44, color: INK.text, align: 'l', a: E.out3(seg(c.lt, 0, 0.3)) });
    rows.forEach((r, i) => {
      const a0 = at(c, i, n), k = E.out3(seg(c.lt, a0, a0 + 0.35)); if (k <= 0) return;
      const y = y0 + i * gap, ok = r.ok !== false, hot = i === cur, kt = E.out3(seg(c.lt, a0 + 0.15, a0 + 0.5));
      const col = ok ? c.col : '#6A7088';
      fr.rect(X0, y - 34, 68, 68, { r: 14, color: col, w: 3, a: k, glow: ok && hot ? 16 : 0, fill: INK.card, fa: 0.7 * k });
      if (ok) fr.poly([[X0 + 16, y + 2], [X0 + 30, y + 18], [X0 + 54, y - 16]], { color: col, w: 6, k: kt, glow: 14 });
      else fr.line(X0 + 18, y, X0 + 18 + 32 * kt, y, { color: col, w: 6 });
      fr.text(r.text, X0 + 100, y, { font: 'sansh', size: 46, color: ok ? (hot ? INK.white : INK.text) : '#6A7088', align: 'l', a: k });
      if (!ok) fr.line(X0 + 96, y, X0 + 104 + fr.measure(r.text, { font: 'sansh', size: 46 }) * kt, y, { color: '#6A7088', w: 3, a: k });
      if (r.note) fr.text(r.note, XR, y, { font: 'sans', size: 30, color: ok ? c.col : '#6A7088', align: 'r', a: k * (hot ? 1 : 0.7) });
    });
  },

  /* 一步一步：{rows:[{text, note?}]} —— 01 02 03 竖排，连线往下长；片尾给"下一步"用 */
  steps(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n);
    const gap = Math.min(190, 820 / Math.max(n, 1)), y0 = 560 + (820 - gap * n) / 2, x = X0 + 50;
    rows.forEach((r, i) => {
      const a0 = at(c, i, n), k = E.out3(seg(c.lt, a0, a0 + 0.4)); if (k <= 0) return;
      const y = y0 + i * gap, hot = i === cur;
      if (i < n - 1) fr.line(x, y + 46, x, y + 46 + (gap - 92) * E.out3(seg(c.lt, a0 + 0.3, a0 + 0.8)), { color: c.col, w: 3, a: 0.5 });
      fr.circle(x, y, 44, { fill: hot ? c.col : INK.card, fa: hot ? 0.95 : 0.8, color: c.col, w: 3, a: k, glow: hot ? 22 : 0 });
      fr.text(String(i + 1).padStart(2, '0'), x, y + 2, { font: 'sansh', size: 34, color: hot ? INK.base : c.col, a: k });
      fr.text(r.text, x + 84, y - (r.note ? 18 : 0), { font: 'sansh', size: 48, color: hot ? INK.white : INK.text, align: 'l', a: k });
      if (r.note) fr.text(r.note, x + 84, y + 38, { font: 'sansr', size: 28, color: INK.dim, align: 'l', a: k });
    });
  },

  /* 飞轮 / 循环：{center?:'越滚越大', nodes:[{label, sub?}]} —— 节点围一圈，一句亮一个，光点一直绕 */
  cycle(fr, c) {
    const d = c.d, nodes = d.nodes || [], n = nodes.length, cy = 790, R = 300;
    const k = E.out3(seg(c.lt, 0, 0.6)), act = current(c, n);
    fr.circle(CX, cy, R, { color: c.col, w: 3, a: 0.35 * k });
    const ang = -Math.PI / 2 + c.lt * 1.4;
    fr.comet(CX + Math.cos(ang) * R, cy + Math.sin(ang) * R, 120, 7, c.col, k, ang + Math.PI / 2);
    if (d.center) fr.text(d.center, CX, cy, { font: 'sansh', size: fit(fr, d.center, 'sansh', 76, R * 1.4), color: INK.white, a: k, glow: 24, glowColor: c.col });
    nodes.forEach((nd, i) => {
      const a0 = at(c, i, n), kk = E.out3(seg(c.lt, a0, a0 + 0.4)); if (kk <= 0) return;
      const t = -Math.PI / 2 + Math.PI * 2 * i / n, x = CX + Math.cos(t) * R, y = cy + Math.sin(t) * R, hot = i === act;
      fr.circle(x, y, 78 * lerp(0.6, 1, kk) * (hot ? 1.08 : 1), { fill: INK.card, fa: 0.95, color: hot ? c.col : c.alt, w: 3, a: kk, glow: hot ? 26 : 0 });
      fr.text(nd.label, x, y - (nd.sub ? 14 : 0), { font: 'sansh', size: fit(fr, nd.label, 'sansh', 40, 130), color: hot ? c.col : INK.white, a: kk });
      if (nd.sub) fr.text(nd.sub, x, y + 28, { font: 'sansr', size: 22, color: INK.dim, a: kk });
    });
  },

  /* 卡片墙：{items:[{name, tag?, rows?:['…']}], pick?} —— 两列，一句亮一张；pick 最后一直亮着 */
  cards(fr, c) {
    const d = c.d, items = d.items || [], n = items.length, act = current(c, n);
    const cols = n <= 3 ? 1 : 2, rowsN = Math.ceil(n / cols), gw = cols === 1 ? CW : (CW - 30) / 2, gh = Math.min(260, (860 - 30 * (rowsN - 1)) / rowsN);
    const y0 = 470 + (900 - (gh * rowsN + 30 * (rowsN - 1))) / 2;
    items.forEach((it, i) => {
      const a0 = at(c, i, n), k = E.out3(seg(c.lt, a0, a0 + 0.4)); if (k <= 0) return;
      const x = X0 + (i % cols) * (gw + 30), y = y0 + Math.floor(i / cols) * (gh + 30), hot = i === act || i === d.pick;
      card(fr, x, y, gw, gh, hot ? c.col : '#5A6075', { a: k * (hot ? 1 : 0.5), edge: hot ? 0.9 : 0.4, glow: hot ? 22 : 0 });
      fr.text(it.name, x + 34, y + 58, { font: 'sansh', size: fit(fr, it.name, 'sansh', 46, gw - 140), color: hot ? c.col : INK.text, align: 'l', a: k, glow: hot ? 14 : 0 });
      if (it.tag) fr.text(it.tag, x + gw - 30, y + 58, { font: 'sans', size: 26, color: INK.dim, align: 'r', a: k });
      (it.rows || []).slice(0, 3).forEach((r, j) => fr.text(r, x + 34, y + 122 + j * 44, { font: 'sansr', size: 30, color: hot ? INK.text : INK.dim, align: 'l', a: k * (hot ? 1 : 0.6) }));
    });
  },
};

window.SCENES = SCENES;
})();
