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

/* 第 i 个（共 n 个）东西什么时候出场：一句一个；比句子多的，挤在最后一句的前 55% 里出完
 * （按拍子出，太多就再密一点）——这样这句播到一半多一点时，所有条目都已经站稳了 */
function at(c, i, n) {
  if (n <= c.span || i < c.span - 1) return i * c.bar;
  const k = n - (c.span - 1), step = Math.min(c.beat, (c.bar * 0.55) / Math.max(k - 1, 1));
  return (c.span - 1) * c.bar + (i - (c.span - 1)) * step;
}
/* 一拍一动（11-18 照教程第 02 条"画面每变一次都落在重拍上"，逐帧量标杆样片：四拍都在变，不只是第一拍）：
 * 第 i 个东西（共 n 个）在 a0 = at(c, i, n) 出场，它的第 k 部分（0 名字 / 1 数 / 2 补充 / 3 强调）落在第 k 拍。
 * 一句里挤了好几个东西（下一个不到一小节就来）时，各部分压缩成紧挨着出 */
function bt(c, i, n, k) {
  const a0 = at(c, i, n), next = i < n - 1 ? at(c, i + 1, n) : c.span * c.bar;
  return next - a0 >= c.bar * 0.99 ? a0 + k * c.beat : a0 + k * Math.min(0.08, (next - a0) / 4);
}
/* 落在拍子上的快速出场：在 t 这一拍开始，0.18 秒内到位（变化要压在鼓点上，不能拖到两拍之间） */
function hit(c, t, dur = 0.18) { return E.out3(seg(c.lt, t, t + dur)); }
/* 第四拍的强调：这一拍上闪一下再落回去 */
function flash4(c, t) { return c.lt >= t ? Math.exp(-(c.lt - t) / 0.16) : 0; }
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

/* 岔路卡片的标签：一行放得下就一行（≥ 44 号字），否则从空格或中间折成两行，字号不小于一行时 */
function pathLabel(fr, p, cw, col, a, glow) {
  const s = String(p.label || ''), maxW = cw - 30; let parts = [s], sz = fit(fr, s, 'sansh', 52, maxW);
  if (sz < 44 && s.length >= 5) {
    const sp = s.indexOf(' '), h = sp > 0 ? sp : Math.ceil(s.length / 2);
    parts = [s.slice(0, h).trim(), s.slice(h).trim()]; sz = Math.min(52, ...parts.map(x => fit(fr, x, 'sansh', 52, maxW)));
  }
  const top = parts.length > 1 ? -sz * 0.95 : -22;
  parts.forEach((x, i) => fr.text(x, 0, top + i * sz * 1.1 - (p.sub && parts.length > 1 ? 14 : 0), { font: 'sansh', size: sz, color: col, a, glow }));
  return parts.length > 1 ? top + sz * 1.1 + sz * 0.5 + 26 : 40;   // sub 的 y
}
function forkFocus(fr, c, paths, f) {
  const n = paths.length, ox = CX, oy = 960, cy = 640, cw = Math.min(300, (CW - 30 * (n - 1)) / n), ch = 210;   // 路收短一点，下面留给放大的那行字
  const xs = paths.map((_, i) => X0 + cw / 2 + i * (CW - cw) / Math.max(n - 1, 1)), k = hit(c, 0, 0.2), kf = hit(c, c.beat, 0.2);   // 第 1 拍几条路 → 第 2 拍这一条亮起来
  fr.spark(ox, oy, 8, c.col, k);
  paths.forEach((p, i) => {
    const on = i === f, pts = []; for (let s = 0; s <= 24; s++) { const u = s / 24; pts.push([lerp(ox, xs[i], E.io3(u)), lerp(oy, cy + ch / 2, u)]); }
    fr.poly(pts, { color: on ? c.col : '#8A90A8', w: on ? 5 : 2, a: on ? kf : 0.35 * k, glow: on ? 18 : 0 });
    fr.g({ at: [xs[i], cy], s: on ? lerp(1, 1.12, kf) : 1 }, () => {
      card(fr, -cw / 2, -ch / 2, cw, ch, on ? c.col : '#8A90A8', { a: k * (on ? 1 : 0.4), edge: on ? 0.9 : 0.3, glow: on ? 24 : 0 });
      const sy = pathLabel(fr, p, cw, on ? c.col : INK.text, k * (on ? 1 : 0.5), on ? 18 : 0);
      if (p.sub) fr.text(p.sub, 0, sy, { font: 'sans', size: Math.min(30, fit(fr, p.sub, 'sans', 30, cw - 30)), color: INK.dim, a: k * (on ? 1 : 0.4) });
    });
  });
  const p = paths[f] || {};   // 下方放大讲这一条
  if (p.sub) {
    const sz = fit(fr, p.sub, 'sansh', 72, CW - 120), w = fr.measure(p.sub, { font: 'sansh', size: sz }) + 100, y = 1130 + (1 - kf) * 20;
    card(fr, CX - w / 2, y - sz * 0.9, w, sz * 1.8, c.col, { a: kf, edge: 0.6, glow: 16, r: 20 });
    fr.text(p.sub, CX, y, { font: 'sansh', size: sz, color: INK.white, a: kf, glow: 20, glowColor: c.col });
  }
}

const SCENES = {

  /* 一个东西：{icon, label?, sub?, count?: 30, unit?: '份', state?: 'no'|'ok'}
   * 不写 count：一个大图标，下面名字；写了 count：一片小图标一个个冒出来，旁边数字跟着数（"投了 30 份简历"） */
  object(fr, c) {
    const d = c.d, total = Math.max(0, Number(d.count) || 0), n = Math.min(60, total), k = hit(c, 0, 0.2);   // 超过 60 只画 60 个，下面的数照样数到真实数量
    if (!n) {
      const fl = Math.sin(c.lt * 2.2) * 8;
      fr.glow(CX, 760, 340, c.col, 0.12 * k);
      drawIcon(fr, d.icon, CX, 740 + fl, 480, c.col, k, c.lt >= 3 * c.beat ? d.state : null);   // 第 1 拍图标 → 第 2 拍名字 → 第 3 拍补充 → 第 4 拍打勾 / 盖红杠
      if (d.label) fr.text(d.label, CX, 1100, { font: 'sansh', size: fit(fr, d.label, 'sansh', 80, CW), color: INK.white, a: hit(c, c.beat), glow: 16, glowColor: c.col });
      if (d.sub) fr.text(d.sub, CX, 1195, { font: 'sansh', size: 44, color: INK.text, a: hit(c, 2 * c.beat) });
      return;
    }
    const cols = n <= 4 ? n : n <= 12 ? 4 : n <= 30 ? 6 : 8, rows = Math.ceil(n / cols);
    const cell = Math.min(CW / cols, 640 / rows), x0 = CX - (cols - 1) * cell / 2, y0 = 760 - (rows - 1) * cell / 2;
    const g4 = i => Math.min(3, Math.floor(i * 4 / n)) * c.beat;   // 一片东西分四批，一拍冒一批（每批都踩在拍上）
    let shownN = 0; for (let i = 0; i < n; i++) if (c.lt >= g4(i)) shownN++;
    for (let i = 0; i < n; i++) {
      const ki = hit(c, g4(i), 0.15);
      drawIcon(fr, d.icon, x0 + (i % cols) * cell, y0 + Math.floor(i / cols) * cell, cell * 0.78, c.col, ki, i === n - 1 && c.lt >= 3 * c.beat + 0.1 ? d.state : null);
    }
    const lab = String(Math.round(total * shownN / Math.max(n, 1))) + (d.unit || '');
    fr.text(lab, CX, y0 + rows * cell - cell / 2 + 130, { font: 'sansh', size: 110, color: INK.white, a: k, glow: 26, glowColor: c.col });
    if (d.label) fr.text(d.label, CX, y0 + rows * cell - cell / 2 + 230, { font: 'sansh', size: 44, color: INK.text, a: k });
  },

  /* 从 A 到 B：{from:{icon,label,sub}, to:{icon,label,sub}, via?:{icon,label}} —— 第一句出 A，第二句（只有一句就第三拍）
   * 光点带着 via 沿弧线走到 B（"工厂 → 轮船 → 越南""国内 → 海外"） */
  flow(fr, c) {
    const d = c.d, A = d.from || {}, Bp = d.to || {}, V = d.via, tr = c.span > 1 ? c.bar : c.beat, dur = 2 * c.beat;   // 出发在拍上、走两拍、到达也在拍上
    const ax = 280, ay = 640, bx = 800, by = 1080;
    const ka = hit(c, 0), km = E.io3(seg(c.lt, tr, tr + dur)), kb = hit(c, tr + dur, 0.2);
    const pt = u => [lerp(ax, bx, u) + Math.sin(u * Math.PI) * 140, lerp(ay, by, u) - Math.sin(u * Math.PI) * 60];
    const pts = []; for (let i = 0; i <= 40; i++) pts.push(pt(i / 40));
    fr.poly(pts, { color: c.col, w: 3, a: 0.25 * ka, dash: [10, 12] });
    fr.poly(pts, { color: c.col, w: 4, k: km, glow: 14 });
    drawIcon(fr, A.icon, ax, ay, 220, c.col, ka);
    if (A.label) fr.text(A.label, ax, ay + 160, { font: 'sansh', size: 50, color: INK.white, a: ka });
    if (A.sub) fr.text(A.sub, ax, ay + 220, { font: 'sans', size: 32, color: INK.dim, a: ka });
    if (km > 0 && km < 1) { const [x, y] = pt(km); if (V && V.icon) drawIcon(fr, V.icon, x, y - 70, 130, c.alt, 1); fr.spark(x, y, 8, c.col, 1); }
    if (V && V.label && km > 0) fr.text(V.label, pt(0.5)[0] + 150, pt(0.5)[1] - 20, { font: 'sansh', size: 36, color: c.alt, a: Math.min(1, km * 3) });
    drawIcon(fr, Bp.icon, bx, by, 240, c.col, kb);
    if (Bp.label) fr.text(Bp.label, bx, by + 170, { font: 'sansh', size: 54, color: c.col, a: kb, glow: 16 });
    if (Bp.sub) fr.text(Bp.sub, bx, by + 232, { font: 'sans', size: 32, color: INK.dim, a: kb });
  },

  /* 片名卡：{kicker?, top, big, bottom} —— 左对齐，big 是全片最大的字 */
  title(fr, c) {
    const d = c.d, lt = c.lt, Y = 860;
    const k1 = hit(c, c.beat), k2 = hit(c, 0, 0.22), k3 = hit(c, 2 * c.beat);   // 第 1 拍大字砸下来 → 第 2 拍上面一行 → 第 3 拍下面一行
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
    const k = hit(c, 0, 0.25), k2 = hit(c, 2 * c.beat);   // 第 1 拍大字 → 第 3 拍下面一行
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
    const k = E.out3(seg(c.lt, ti, ti + (i === 0 && d.from == null ? 0.05 : 0.25)));   // 数在这一拍上 0.25 秒内滚到位（原来 0.7 秒，落点拖到两拍之间）
    const v = lerp(prev, vals[i], k), Y = d.bar ? 720 : 830;   // 下面没有条就往下放，别让主体挤在上半截
    const str = fmt(v, dec), u = (d.units && d.units[i]) || d.unit || '';
    const P = j => Array.isArray(d.prefix) ? String(d.prefix[j] || '') : String(d.prefix || ''), U = j => Array.isArray(d.suffix) ? String(d.suffix[j] || '') : String(d.suffix || '');   // 几个值单位不同（12 万、30 块）时 prefix / suffix 写成列表
    const groupW = sz => (P(i) ? fr.measure(P(i), { font: 'sansh', size: sz * 0.45 }) + 14 : 0) + fr.measure(fmt(vals[i], dec) + U(i), { font: 'sansh', size: sz, track: -4 }) + (u ? 18 + fr.measure(u, { font: 'sansh', size: 46 }) : 0);
    let size = 300; while (size > 60 && groupW(size) > CW - 20) size -= 6;
    if (n > 1) size = Math.min(size, 260);   // 上面要给旧值留一行
    if (i > 0) {   // 旧值缩小放在上面、划一道：读得出"从 A 变成了 B"，不和新值叠成重影
      const gs = Math.min(110, size * 0.36), gt = P(i - 1) + fmt(prev, dec) + U(i - 1) + ((d.units && d.units[i - 1]) ? ' ' + d.units[i - 1] : ''), gy = Y - size * 0.62 - gs * 0.6;
      const gw = fr.measure(gt, { font: 'sansh', size: gs }), ga = 0.55 * hit(c, ti), tg = packed ? ti + 0.08 : ti + c.beat;   // 第 2 拍把旧值划掉
      fr.text(gt, CX, gy, { font: 'sansh', size: gs, color: c.alt, a: ga });
      fr.line(CX - gw / 2 - 8, gy, CX - gw / 2 - 8 + (gw + 16) * hit(c, tg, 0.2), gy, { color: c.alt, w: 5, a: ga });
    }
    const ent = hit(c, 0, 0.2), fl = packed ? 0 : flash4(c, ti + 3 * c.beat);   // 第 4 拍数字闪一下
    fr.g({ at: [CX, Y], s: lerp(0.86, 1, ent) * (1 + 0.06 * (1 - seg(c.lt, ti, ti + 0.2)) * (i > 0 ? 1 : 0)) * (1 + 0.05 * fl) }, () => {
      const pw = P(i) ? fr.measure(P(i), { font: 'sansh', size: size * 0.45 }) + 14 : 0;
      const nw = fr.measure(str + U(i), { font: 'sansh', size, track: -4 }), uw = u ? 18 + fr.measure(u, { font: 'sansh', size: 46 }) : 0, x0 = -(pw + nw + uw) / 2;
      if (P(i)) fr.text(P(i), x0, -size * 0.12, { font: 'sansh', size: size * 0.45, color: c.col, align: 'l', a: ent, glow: 20 });
      fr.text(str + U(i), x0 + pw, 0, { font: 'sansh', size, track: -4, align: 'l', a: ent, grad: [[0, '#FFFFFF'], [1, mix('#FFFFFF', c.col, 0.45)]], glow: 34, glowColor: c.col, glowA: 0.5 });
      if (u) fr.text(u, x0 + pw + nw + 18, size * 0.22, { font: 'sansh', size: 46, color: INK.text, align: 'l', a: ent });
    });
    if (d.bar) {
      const b = d.bar, by = 1080, kb = hit(c, 2 * c.beat, 0.35);   // 第 3 拍下面那条长出来
      fr.text(b.label || '', X0, by - 50, { font: 'sansh', size: 40, track: 2, color: INK.text, align: 'l', a: kb });
      if (b.tag) fr.text(b.tag, XR, by - 50, { font: 'sansh', size: 40, color: NEON.green.main, align: 'r', a: kb, glow: 12 });
      card(fr, X0, by, CW, 66, c.col, { a: kb, r: 12, edge: 0.3 });
      const p = clamp(Number(b.pct || 0) / 100) * kb;
      fr.rect(X0 + 8, by + 8, (CW - 16) * p, 50, { r: 8, fill: c.col, fa: 0.85, glow: 18 });
    }
  },

  /* 算账：{rows:[{label, value, op?:'+'|'-'}], prefix?:'¥', suffix?:'元', total?:'每对赚'}
   * 一句记一笔（加的绿、减的红），写了 total 就再多一句：画一道线，合计按上面几笔自动算出来——合计不用模型算，也编不出来 */
  ledger(fr, c) {
    const d = c.d, rows = d.rows || [], hasT = !!d.total, n = rows.length + (hasT ? 1 : 0), cur = current(c, n);
    const one = v => String(Array.isArray(v) ? (v[0] || '') : (v || '')), pre = one(d.prefix), suf = one(d.suffix), sign = r => (r.op === '-' || r.op === '−' ? -1 : 1);
    const total = rows.reduce((a, r) => a + sign(r) * (Number(r.value) || 0), 0), dec = decimalsOf(rows.map(r => r.value));
    const gap = rows.length <= 3 ? 165 : 140, y0 = 640 + (4 - Math.min(rows.length, 4)) * 30;   // 整组压在画面中部偏下，别全挤在上半截
    rows.forEach((r, i) => {
      const k = hit(c, bt(c, i, n, 0)); if (k <= 0) return;   // 第 1 拍名目 → 第 2 拍金额落下 → 第 4 拍闪一下
      const y = y0 + i * gap, hot = i === cur, neg = sign(r) < 0, colr = neg ? NEON.red.main : NEON.green.main, kv = hit(c, bt(c, i, n, 1)), fl = hot ? flash4(c, bt(c, i, n, 3)) : 0;
      fr.text(r.label, X0, y, { font: 'sansh', size: 62, color: INK.white, align: 'l', a: k * (hot ? 1 : 0.7) });
      fr.g({ at: [XR, y], s: lerp(1.25, 1, kv) * (1 + 0.1 * fl) }, () => fr.text((i === 0 && !neg ? '' : neg ? '− ' : '+ ') + pre + fmt(Number(r.value) || 0, dec) + suf, 0, 0, { font: 'sansh', size: 68, color: hot ? colr : mix(colr, '#888', 0.4), align: 'r', a: kv, glow: hot ? 18 + 30 * fl : 0 }));
      fr.line(X0, y + 52, X0 + CW * hit(c, bt(c, i, n, 2), 0.25), y + 52, { color: '#FFFFFF', w: 1, a: 0.12 * k });
    });
    if (hasT) {
      const k = hit(c, bt(c, n - 1, n, 0), 0.25); if (k <= 0) return;   // 第 1 拍划线 → 第 2 拍合计砸下来 → 第 4 拍闪
      const y = y0 + rows.length * gap + 40, colr = total < 0 ? NEON.red.main : NEON.green.main, kv = hit(c, bt(c, n - 1, n, 1), 0.22), fl = flash4(c, bt(c, n - 1, n, 3));
      fr.line(X0, y - 50, X0 + CW * k, y - 50, { color: c.col, w: 4, glow: 12 });
      fr.text(String(d.total), X0, y + 34, { font: 'sansh', size: 64, color: INK.white, align: 'l', a: k });
      const v = total * kv;
      fr.text((total < 0 ? '− ' : '') + pre + fmt(Math.abs(v), dec) + suf, XR, y + 44, { font: 'sansh', size: 150 * (1 + 0.08 * fl), color: colr, align: 'r', a: Math.max(kv, 0.001), glow: 30 + 30 * fl });
    }
  },

  /* 横条对比：{rows:[{label, value, tag?}], unit?:'%', max?} —— 一句亮一条，最新的那条最亮 */
  bars(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n);
    const max = Number(d.max) || Math.max(...rows.map(r => Number(r.value) || 0), 1);
    const gap = Math.min(170, 900 / Math.max(n, 1)), y0 = 470 + (900 - gap * n) / 2;
    rows.forEach((r, i) => {
      const k = hit(c, bt(c, i, n, 0)); if (k <= 0) return;   // 第 1 拍名字 → 第 2 拍数和条一下长满 → 第 3 拍补充 → 第 4 拍闪一下
      const y = y0 + i * gap, hot = i === cur, dim = hot ? 1 : 0.5, kv = hit(c, bt(c, i, n, 1), 0.25), fl = hot ? flash4(c, bt(c, i, n, 3)) : 0;
      fr.text(r.label, X0, y, { font: 'sansh', size: 46, color: INK.white, align: 'l', a: k * dim });
      const val = (Number(r.value) || 0) * kv;
      fr.text(fmt(val, decimalsOf([r.value])) + (d.unit || ''), XR, y, { font: 'sansh', size: 46 * (1 + 0.12 * fl), color: hot ? c.col : INK.text, align: 'r', a: Math.max(kv, 0.001) * k, glow: hot ? 18 + 30 * fl : 0 });
      fr.rect(X0, y + 46, CW, 16, { r: 8, fill: '#FFFFFF', fa: 0.07 * k });
      fr.rect(X0, y + 46, CW * clamp(val / max), 16, { r: 8, fill: hot ? c.col : mix(c.col, '#444', 0.5), fa: k, glow: hot ? 16 + 24 * fl : 0 });
      if (r.tag) fr.text(r.tag, X0, y + 98, { font: 'sans', size: 30, color: INK.dim, align: 'l', a: hit(c, bt(c, i, n, 2)) * dim });
    });
  },

  /* 环形占比：{value:40, suffix:'%', label:'利润被吃掉', rows:[{text, tag?}]} —— 环先转满，再一句点一条原因 */
  ring(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n), cy = 720, R = 230;
    const k = hit(c, 0, 0.2), v = Number(d.value || 0) * hit(c, c.beat, 0.5);   // 第 1 拍环出来 → 第 2 拍起转到那个占比
    for (let j = 0; j < 3; j++) fr.arc(CX, cy, R + 38 + j * 22, c.lt * (0.3 + j * 0.2) + j, c.lt * (0.3 + j * 0.2) + j + 1.2 + j * 0.6, { color: j === 1 ? c.alt : c.col, w: 2, a: 0.25 * k });
    fr.circle(CX, cy, R, { color: '#FFFFFF', w: 18, a: 0.07 * k });
    fr.arc(CX, cy, R, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * clamp(v / 100), { color: c.col, w: 18, a: k, glow: 26 });
    if (d.label) fr.text(d.label, CX, cy - 82, { font: 'sans', size: 30, track: 4, color: INK.text, a: k });
    fr.text(fmt(v, decimalsOf([d.value])) + (d.suffix == null ? '%' : d.suffix), CX, cy + 14, { font: 'sansh', size: 128, color: INK.white, a: k, glow: 30, glowColor: c.col, glowA: 0.6 });
    rows.forEach((r, i) => {
      const a0 = c.span > 1 && i === 0 ? at(c, i, n) + 2 * c.beat : at(c, i, n), kk = hit(c, a0); if (kk <= 0) return;   // 第一条等环转满（第 3 拍）再出
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
    const tb = bs * c.bar, kb = brk >= 0 ? hit(c, tb, 0.15) : 0;   // 断开正好砸在小节第一拍
    const shake = kb > 0 ? Math.sin(c.lt * 70) * 10 * (1 - seg(c.lt, tb, tb + 0.4)) : 0;
    const per = Math.min(c.beat, (c.bar * 0.9) / Math.max(n, 1));
    const t0 = i => c.span > 1 ? at(c, i, n) : i * per;   // 一镜撑几句：一句亮一个节点（多的挤在最后一句）；只有一句：按拍子一口气亮完
    fr.g({ at: [shake, 0] }, () => {
      const kl = E.out3(seg(c.lt, 0, t0(n - 1) + 0.3));
      fr.line(xs[0], y, lerp(xs[0], xs[n - 1], kl), y, { color: c.col, w: 4, a: 0.8, glow: 14 });
      if (kb > 0 && brk < n - 1) {
        const xa = xs[brk] + 30, xb = xs[brk + 1] - 30, mid = (xa + xb) / 2;
        fr.rect(xa, y - 14, xb - xa, 28, { fill: INK.base, fa: kb });
        fr.poly([[mid - 30, y - 50], [mid + 8, y - 12], [mid - 10, y + 10], [mid + 30, y + 54]], { color: red, w: 5, a: kb, glow: 22, k: kb });
        fr.line(xb, y, xs[n - 1], y, { color: '#5A6075', w: 4, a: kb });
      }
      nodes.forEach((nd, i) => {
        const a0 = t0(i), k = hit(c, a0), ks = c.span > 1 ? hit(c, bt(c, i, n, 1)) : k, ki = c.span > 1 ? hit(c, bt(c, i, n, 2)) : k; if (k <= 0) return;   // 一句一个节点时：第 1 拍点和名字 → 第 2 拍年份 → 第 3 拍图标
        const lost = kb > 0 && i > brk, colr = lost ? mix(c.col, '#5A6075', kb) : c.col, up = i % 2 === 0;
        fr.circle(xs[i], y, 22 * k, { fill: INK.base, color: colr, w: 5, glow: lost ? 0 : 20 });
        fr.circle(xs[i], y, 8 * k, { fill: colr });
        fr.line(xs[i], y + (up ? -30 : 30), xs[i], y + (up ? -70 : 70), { color: colr, w: 2, a: 0.5 * k });
        const ls = fit(fr, nd.label, 'sansh', 58, Math.min((CW / Math.max(n - 1, 1)) * 1.6, CW * 0.6)), lw = fr.measure(nd.label, { font: 'sansh', size: ls });
        const sw = nd.sub ? fr.measure(nd.sub, { font: 'mono', size: 38 }) : 0, tx = clamp(xs[i], 48 + Math.max(lw, sw) / 2, W - 48 - Math.max(lw, sw) / 2);   // 两头的节点字长时往里挪，别贴边
        fr.text(nd.label, tx, y + (up ? -110 : 110), { font: 'sansh', size: ls, color: lost ? '#6A7088' : INK.white, a: k });
        if (nd.sub) fr.text(nd.sub, tx, y + (up ? -178 : 176), { font: 'mono', size: 38, color: lost ? '#555A70' : c.col, a: ks, glow: lost ? 0 : 10 });
        if (nd.icon) drawIcon(fr, nd.icon, xs[i], y + (up ? -280 : 280), 110, lost ? '#5A6075' : c.col, ki);
      });
    });
    if (kb > 0) fr.flash(0.18 * (1 - seg(c.lt, tb, tb + 0.3)), red);
  },

  /* 岔路：{paths:[{label, sub}], pick: 2} —— 第一句路长出来，之后每句划掉一条，最后一句点亮 pick
   * {paths, focus: 1} —— 只是"现在讲这一条"：这一条亮、其他变暗，不划掉（逐条讲几条路时，每句一镜用 focus） */
  fork(fr, c) {
    const d = c.d, paths = d.paths || [], n = paths.length, none = d.pick === -1 || d.pick === 'none', pick = none ? -1 : d.pick != null ? Number(d.pick) : n - 1;   // pick: -1 = 一条都不留（几条全是死路）
    if (d.focus != null) return forkFocus(fr, c, paths, Number(d.focus));
    const ox = CX, oy = 1300, cy = 660, cw = Math.min(300, (CW - 30 * (n - 1)) / n), ch = 210;
    const xs = paths.map((_, i) => X0 + cw / 2 + i * (CW - cw) / Math.max(n - 1, 1));
    const kills = paths.map((_, i) => i).filter(i => i !== pick);
    const killAt = i => { const j = kills.indexOf(i); if (j < 0) return 1e9; const steps = Math.max(c.span - (none ? 1 : 2), 1); return c.span <= 1 ? (j + 1) * c.beat : (1 + Math.min(j, steps - 1)) * c.bar + Math.max(0, j - (steps - 1)) * c.beat; };
    const pickAt = none ? 1e9 : c.span <= 1 ? (kills.length + 1) * c.beat : Math.max(c.span - 1, 1) * c.bar;
    fr.spark(ox, oy, 8, c.col, E.out3(seg(c.lt, 0, 0.3)));
    paths.forEach((p, i) => {
      const g0 = c.span > 1 ? Math.min(i, 3) * c.beat : i * Math.min(0.12, c.beat / Math.max(n, 1)), k = hit(c, g0, 0.25), kx = hit(c, killAt(i), 0.15), kp = i === pick ? hit(c, pickAt, 0.2) : 0;   // 一句以上：路一拍长出一条；划掉、点亮都砸在拍上
      const pts = []; for (let s = 0; s <= 24; s++) { const u = s / 24; pts.push([lerp(ox, xs[i], E.io3(u)), lerp(oy, cy + ch / 2, u)]); }
      fr.poly(pts, { color: kp > 0 ? c.col : '#8A90A8', w: kp > 0 ? 5 : 2.5, a: (0.7 - 0.45 * kx) * (kp > 0 ? 1 : 1), k, glow: kp > 0 ? 18 : 0 });
      if (k <= 0) return;
      const x = xs[i] - cw / 2, y = cy - ch / 2;
      fr.g({ at: [xs[i], cy], s: 1 + 0.12 * kp }, () => {
        card(fr, -cw / 2, -ch / 2, cw, ch, kp > 0 ? c.col : '#8A90A8', { a: k * (1 - 0.55 * kx), edge: kp > 0 ? 0.9 : 0.4, glow: kp > 0 ? 24 : 0 });
        const sy = pathLabel(fr, p, cw, kp > 0 ? c.col : INK.white, k * (1 - 0.55 * kx), kp > 0 ? 18 : 0);
        if (p.sub) fr.text(p.sub, 0, sy, { font: 'sans', size: Math.min(30, fit(fr, p.sub, 'sans', 30, cw - 30)), color: INK.dim, a: k * (1 - 0.4 * kx) });
      });
      if (kx > 0) fr.line(x + 18, cy, x + 18 + (cw - 36) * kx, cy, { color: NEON.red.main, w: 6, glow: 14 });
    });
  },

  /* 一组对比：{left:{label, value, sub?}, right:{label, value, sub?}, badge?:{label, value}}
   * 第一句只出左边；第二句（只有一句就第三拍）箭头走过去，出右边和角标 */
  compare(fr, c) {
    const d = c.d, L = d.left || {}, R = d.right || {}, y = d.badge ? 560 : 680, h = 440;   // 没有角标时整体往下放，主体别挤在上半截
    const tr = c.span > 1 ? c.bar : c.beat * 2;
    const tb = d.badge && c.span >= 3 ? 2 * c.bar : c.span > 1 ? tr + 2 * c.beat : tr + c.beat;   // 一镜三句以上：左边 → 右边 → 角标各占一句
    // 一拍一动：左边卡片第 1 拍、左边的数第 2 拍；箭头在右边那一句的第 1 拍冲过去、右边的数第 2 拍砸下来
    const k1 = hit(c, 0), kv1 = c.span > 1 ? hit(c, c.beat) : k1, ka = hit(c, tr, 0.25), k2 = hit(c, tr + (c.span > 1 ? c.beat : 0.15)), kb = hit(c, tb, 0.25);
    card(fr, X0, y, CW, h, c.col, { a: k1, edge: 0.35 });
    fr.text(L.label || '', X0 + 50, y + 80, { font: 'sansh', size: 40, track: 3, color: INK.text, align: 'l', a: k1 });
    const ls = fit(fr, String(L.value), 'sansh', 110, CW * 0.4);
    if (L.icon) drawIcon(fr, L.icon, X0 + 120, y - 110, 150, c.col, k1);
    fr.text(String(L.value || ''), X0 + 50, y + 190, { font: 'sansh', size: ls, color: INK.white, align: 'l', a: kv1 });
    if (L.sub) fr.text(L.sub, X0 + 50, y + 280, { font: 'sans', size: 32, color: INK.dim, align: 'l', a: c.span > 1 ? hit(c, 2 * c.beat) : k1 });
    const ax0 = X0 + 60, ax1 = XR - 60, ay = y + 360;
    fr.line(ax0, ay, lerp(ax0, ax1, ka), ay, { color: c.col, w: 3, a: 0.9, glow: 12 });
    if (ka > 0 && ka < 1) fr.spark(lerp(ax0, ax1, ka), ay, 7, c.col, 1);
    if (ka >= 1) fr.poly([[ax1 - 18, ay - 12], [ax1, ay], [ax1 - 18, ay + 12]], { color: c.col, w: 3, glow: 10 });
    fr.text(R.label || '', XR - 50, y + 80, { font: 'sansh', size: 40, track: 3, color: INK.text, align: 'r', a: k2 });
    const rs = fit(fr, String(R.value), 'sansh', 130, CW * 0.45);
    if (R.icon) drawIcon(fr, R.icon, XR - 120, y - 110, 150, c.col, k2);
    fr.text(String(R.value || ''), XR - 50, y + 190 + (1 - k2) * 20, { font: 'sansh', size: rs, color: c.col, align: 'r', a: k2, glow: 30 });
    if (R.sub) fr.text(R.sub, XR - 50, y + 280, { font: 'sans', size: 32, color: INK.dim, align: 'r', a: c.span > 1 ? hit(c, tr + 2 * c.beat) : k2 });
    if (d.badge && kb > 0) fr.g({ at: [CX, y + h + 120], s: lerp(1.3, 1, kb) }, () => {
      card(fr, -170, -70, 340, 140, NEON.green.main, { a: kb, edge: 0.9, glow: 20, r: 18 });
      fr.text(d.badge.label || '', 0, -28, { font: 'sans', size: 28, color: NEON.green.alt, a: kb });
      fr.text(String(d.badge.value || ''), 0, 26, { font: 'sansh', size: 60, color: NEON.green.main, a: kb, glow: 18 });
    });
  },

  /* 打勾清单：{title?, rows:[{text, ok?:true|false, note?}]} —— 一句勾一条；ok:false 画一道横线、发灰 */
  checklist(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n);
    const big = n <= 3, huge = n <= 2, fs = huge ? 74 : big ? 60 : 46, bx = huge ? 108 : big ? 88 : 68;   // 条目少就放大，别让画面空着
    const gap = Math.min(huge ? 250 : big ? 200 : 150, 760 / Math.max(n, 1)), y0 = 620 + (760 - gap * n) / 2;
    if (d.title) fr.text(d.title, X0, y0 - (big ? 130 : 90), { font: 'sansh', size: big ? 54 : 44, color: INK.text, align: 'l', a: E.out3(seg(c.lt, 0, 0.3)) });
    rows.forEach((r, i) => {
      const k = hit(c, bt(c, i, n, 0)); if (k <= 0) return;   // 第 1 拍条目 → 第 2 拍打勾 / 划掉 → 第 3 拍补充 → 第 4 拍闪
      const y = y0 + i * gap, ok = r.ok !== false, hot = i === cur, kt = hit(c, bt(c, i, n, 1), 0.2), fl = hot ? flash4(c, bt(c, i, n, 3)) : 0;
      const col = ok ? c.col : '#6A7088';
      const q = bx / 68;
      fr.rect(X0, y - bx / 2, bx, bx, { r: 14 * q, color: col, w: 3, a: k, glow: ok && hot ? 16 + 30 * fl : 0, fill: INK.card, fa: 0.7 * k });
      if (ok) fr.poly([[X0 + 16 * q, y + 2 * q], [X0 + 30 * q, y + 18 * q], [X0 + 54 * q, y - 16 * q]], { color: col, w: 6 * q, k: kt, glow: 14 });
      else fr.line(X0 + 18 * q, y, X0 + (18 + 32 * kt) * q, y, { color: col, w: 6 * q });
      if (r.icon) drawIcon(fr, r.icon, X0 + bx + 32 + bx * 0.45, y, bx * 0.9, ok ? col : '#6A7088', k);
      const tx = X0 + bx + 32 + (r.icon ? bx + 20 : 0), ts = Math.min(fs, fit(fr, r.text, 'sansh', fs, XR - tx - (r.note ? 200 : 0)));
      fr.text(r.text, tx, y, { font: 'sansh', size: ts, color: ok ? (hot ? INK.white : INK.text) : '#6A7088', align: 'l', a: k });
      if (!ok) fr.line(tx - 4, y, tx + 4 + fr.measure(r.text, { font: 'sansh', size: ts }) * kt, y, { color: '#6A7088', w: 3, a: k });
      if (r.note) fr.text(r.note, XR, y, { font: 'sansh', size: big ? 38 : 30, color: ok ? c.col : '#6A7088', align: 'r', a: hit(c, bt(c, i, n, 2)) * (hot ? 1 : 0.7) });
    });
  },

  /* 一步一步：{rows:[{text, note?}]} —— 01 02 03 竖排，连线往下长；片尾给"下一步"用 */
  steps(fr, c) {
    const d = c.d, rows = d.rows || [], n = rows.length, cur = current(c, n);
    const big = n <= 3, R = big ? 56 : 44, ts = big ? 62 : 48, ns = big ? 30 : 28;   // 步骤少就放大
    const gap = Math.min(big ? 240 : 190, 820 / Math.max(n, 1)), y0 = 600 + (820 - gap * n) / 2, x = X0 + R + 6;
    rows.forEach((r, i) => {
      const k = hit(c, bt(c, i, n, 0)); if (k <= 0) return;   // 第 1 拍编号和这一步 → 第 3 拍补充 → 第 4 拍连线往下长、闪一下
      const y = y0 + i * gap, hot = i === cur, fl = hot ? flash4(c, bt(c, i, n, 3)) : 0;
      if (i < n - 1) fr.line(x, y + R + 2, x, y + R + 2 + (gap - 2 * R - 4) * hit(c, bt(c, i, n, 3), 0.3), { color: c.col, w: 3, a: 0.5 });
      fr.circle(x, y, R * lerp(0.6, 1, k) * (1 + 0.1 * fl), { fill: hot ? c.col : INK.card, fa: hot ? 0.95 : 0.8, color: c.col, w: 3, a: k, glow: hot ? 22 + 30 * fl : 0 });
      fr.text(String(i + 1).padStart(2, '0'), x, y + 2, { font: 'sansh', size: R * 0.78, color: hot ? INK.base : c.col, a: k });
      const tx = x + R + 40, tsz = Math.min(ts, fit(fr, r.text, 'sansh', ts, XR - tx));
      fr.text(r.text, tx, y - (r.note ? ts * 0.38 : 0), { font: 'sansh', size: tsz, color: hot ? INK.white : INK.text, align: 'l', a: k });
      if (r.note) fr.text(r.note, tx, y + ts * 0.8, { font: 'sansr', size: ns + (big ? 4 : 0), color: INK.dim, align: 'l', a: hit(c, bt(c, i, n, 2)) });
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
      const kk = hit(c, bt(c, i, n, 0)); if (kk <= 0) return;   // 第 1 拍节点 → 第 4 拍闪一下
      const t = -Math.PI / 2 + Math.PI * 2 * i / n, x = CX + Math.cos(t) * R, y = cy + Math.sin(t) * R, hot = i === act, fl = hot ? flash4(c, bt(c, i, n, 3)) : 0;
      fr.circle(x, y, 78 * lerp(0.6, 1, kk) * (hot ? 1.08 : 1) * (1 + 0.12 * fl), { fill: INK.card, fa: 0.95, color: hot ? c.col : c.alt, w: 3, a: kk, glow: hot ? 26 : 0 });
      if (nd.icon) { drawIcon(fr, nd.icon, x, y - 4, 92, hot ? c.col : c.alt, kk); fr.text(nd.label, x, y + 110, { font: 'sansh', size: fit(fr, nd.label, 'sansh', 40, 200), color: hot ? c.col : INK.white, a: kk }); }
      else {
        fr.text(nd.label, x, y - (nd.sub ? 14 : 0), { font: 'sansh', size: fit(fr, nd.label, 'sansh', 40, 130), color: hot ? c.col : INK.white, a: kk });
        if (nd.sub) fr.text(nd.sub, x, y + 28, { font: 'sansr', size: 22, color: INK.dim, a: kk });
      }
    });
  },

  /* 卡片墙：{items:[{name, tag?, rows?:['…']}], pick?} —— 两列，一句亮一张；pick 最后一直亮着 */
  cards(fr, c) {
    const d = c.d, items = d.items || [], n = items.length, act = current(c, n);
    const cols = n <= 3 ? 1 : 2, rowsN = Math.ceil(n / cols), gw = cols === 1 ? CW : (CW - 30) / 2, gh = Math.min(260, (860 - 30 * (rowsN - 1)) / rowsN);
    const y0 = 470 + (900 - (gh * rowsN + 30 * (rowsN - 1))) / 2;
    items.forEach((it, i) => {
      const k = hit(c, bt(c, i, n, 0)); if (k <= 0) return;   // 第 1 拍卡片 → 第 2 拍标签 → 第 3 拍内容 → 第 4 拍闪
      const x = X0 + (i % cols) * (gw + 30), y = y0 + Math.floor(i / cols) * (gh + 30), hot = i === act || i === d.pick, kt = hit(c, bt(c, i, n, 1)), kr = hit(c, bt(c, i, n, 2)), fl = hot ? flash4(c, bt(c, i, n, 3)) : 0;
      card(fr, x, y, gw, gh, hot ? c.col : '#5A6075', { a: k * (hot ? 1 : 0.5), edge: hot ? 0.9 : 0.4, glow: hot ? 22 + 30 * fl : 0 });
      if (it.icon) {   // 有图标：图标大、居中在上，名字在下
        const is = Math.min(gh * 0.5, gw * 0.42);
        drawIcon(fr, it.icon, x + gw / 2, y + gh * 0.38, is, hot ? c.col : '#8A90A8', k);
        fr.text(it.name, x + gw / 2, y + gh * 0.8, { font: 'sansh', size: fit(fr, it.name, 'sansh', 44, gw - 40), color: hot ? c.col : INK.text, a: k, glow: hot ? 14 : 0 });
        if (it.tag) fr.text(it.tag, x + gw - 24, y + 36, { font: 'sans', size: 24, color: INK.dim, align: 'r', a: kt });
      } else {
        fr.text(it.name, x + 34, y + 58, { font: 'sansh', size: fit(fr, it.name, 'sansh', 46, gw - 140), color: hot ? c.col : INK.text, align: 'l', a: k, glow: hot ? 14 : 0 });
        if (it.tag) fr.text(it.tag, x + gw - 30, y + 58, { font: 'sans', size: 26, color: INK.dim, align: 'r', a: kt });
        (it.rows || []).slice(0, 3).forEach((r, j) => fr.text(r, x + 34, y + 122 + j * 44, { font: 'sansr', size: 30, color: hot ? INK.text : INK.dim, align: 'l', a: kr * (hot ? 1 : 0.6) }));
      }
    });
  },
};

window.SCENES = SCENES;
})();
