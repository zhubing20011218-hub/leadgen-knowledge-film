/* 《被裁之后》画面件（leadgen-knowledge-film · 引流六拍）
 * 竖屏 1080×1920。安全区：x 60–1020、y 150–1520（字幕区 1520 以下不碰）。
 * 每个件：(fr, t, p)，自己不管时间，进出场由 film.js 乘 a。
 * 颜色：一种颜色一个意思 —— 象牙白 = 常规；红 = 失去/被吃掉；金 = 钱/结论。
 */
(function () {
'use strict';
const { W, H, clamp, lerp, seg, ss, fade, E, rng, rgba, mix } = VK;
const C = window.C;
const CH = (window.CH = window.CH || {});

/* ---------- 小工具 ---------- */
function card(fr, x, y, w, h, o) {
  o = o || {};
  fr.g({ a: o.a == null ? 1 : o.a }, () => {
    fr.rect(x, y, w, h, { r: o.r || 22, fill: 'rgba(28,22,14,0.82)', color: o.color || C.faint, w: o.w || 2 });
    if (o.glow) fr.rect(x, y, w, h, { r: o.r || 22, color: o.color || C.gold, w: 1, a: 0.35 });
  });
}
function tag(fr, str, x, y, o) {
  o = o || {};
  fr.text(str, x, y, { font: o.font || 'serifr', size: o.size || 30, color: o.color || C.dim, align: o.align || 'c', track: o.track == null ? 3 : o.track, a: o.a });
}

/* ---------- ① 人生时间线：节点依次亮起，然后断掉 ---------- */
CH.timeline = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const y = 980, x0 = 150, x1 = 930;
  const nodes = [
    { x: 250, zh: '毕业', sub: '22', t0: 0.9 },
    { x: 470, zh: '入职', sub: '28', t0: 1.5 },
    { x: 690, zh: '结婚', sub: '30', t0: 2.1 },
    { x: 890, zh: '退休', sub: '60', t0: 2.7 },
  ];
  const crackT = p.crack == null ? 4.2 : p.crack;   // 断点时刻（绝对秒）
  fr.g({ a }, () => {
    // 主线：从左长到右
    const grow = ss(t, 0.55, 2.2);
    fr.poly([[x0, y], [lerp(x0, x1, grow), y]], { color: C.line, w: 3, a: 0.55 });
    // 断点：裂开 + 右侧变暗
    const broke = ss(t, crackT, crackT + 0.5);
    if (broke > 0) {
      const bx = 600;
      fr.poly([[bx - 26, y - 26], [bx - 6, y - 4], [bx - 18, y + 12], [bx + 4, y + 30]], { color: C.red, w: 4, a: 0.9 * broke, glow: 10, glowA: 0.4 });
      fr.poly([[bx + 6, y - 18], [bx + 22, y + 2], [bx + 10, y + 22]], { color: C.red, w: 3, a: 0.6 * broke });
    }
    nodes.forEach((n, i) => {
      const k = ss(t, n.t0, n.t0 + 0.45);
      if (k <= 0) return;
      const dead = broke > 0 && n.x > 600;
      const col = dead ? C.faint : (i === 0 ? C.gold : C.line);
      fr.circle(n.x, y, 15 * E.out3(k), { fill: dead ? 'rgba(60,54,46,0.9)' : 'rgba(20,16,10,0.95)', color: col, w: 3, a: 0.95 });
      fr.circle(n.x, y, 6 * E.out3(k), { fill: col, a: 0.85 });
      tag(fr, n.zh, n.x, y - 74, { size: 38, color: dead ? C.faint : C.ink, a: k });
      tag(fr, n.sub, n.x, y + 68, { font: 'latin', size: 34, color: dead ? C.faint : C.dim, a: k });
    });
    // 数字：年份轴上的年份
    tag(fr, '22 岁 → 60 岁', W / 2, y + 190, { size: 30, color: C.faint, a: ss(t, 2.2, 3.0) * 0.9 });
  });
};

/* ---------- ② 断裂：一纸通知落桌 ---------- */
CH.breakCard = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const k = ss(t, p.t0, p.t0 + 0.75);              // 落桌
  if (k <= 0) return;
  const drop = lerp(-260, 0, E.out3(k));
  const squash = 1 + 0.05 * Math.exp(-Math.max(0, t - p.t0 - 0.75) * 7) * Math.cos((t - p.t0 - 0.75) * 15);
  const w = 560, h = 380, cx = W / 2, cy = 900 + drop;
  fr.g({ a, at: [cx, cy], rot: lerp(-0.09, -0.03, E.out3(k)), s: [1, squash] }, () => {
    fr.rect(-w / 2, -h / 2, w, h, { r: 8, fill: 'rgba(196,180,150,0.92)' });
    fr.rect(-w / 2, -h / 2, w, h, { r: 8, color: '#C9BEA6', w: 2 });
    fr.text('解除劳动合同通知书', 0, -h / 2 + 62, { font: 'serifm', size: 40, color: '#241C12', align: 'c', track: 2 });
    fr.line(-w / 2 + 60, -h / 2 + 96, w / 2 - 60, -h / 2 + 96, { color: '#8C7F68', w: 2 });
    fr.text('因部门裁撤，岗位取消', -w / 2 + 60, -h / 2 + 150, { font: 'serifr', size: 32, color: '#2C241A', align: 'l' });
    fr.text('生效日期：次年 3 月 1 日', -w / 2 + 60, -h / 2 + 200, { font: 'serifr', size: 30, color: '#3A3226', align: 'l' });
    fr.text('38 岁 · 工号 0173', -w / 2 + 60, -h / 2 + 256, { font: 'latinm', size: 34, color: '#2C241A', align: 'l' });
    // 红章
    const st = ss(t, p.t0 + 0.7, p.t0 + 1.05);
    if (st > 0) {
      fr.g({ a: 0.9 * st, at: [w / 2 - 110, h / 2 - 110], rot: -0.22, s: st }, () => {
        fr.circle(0, 0, 74, { color: C.red, w: 4, a: 0.9 });
        fr.circle(0, 0, 64, { color: C.red, w: 1.5, a: 0.6 });
        fr.text('裁', 0, -4, { font: 'serifh', size: 64, color: C.red, align: 'c' });
      });
    }
  });
};

/* ---------- ③ 片名卡 ---------- */
CH.titleCard = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const sc = lerp(0.965, 1, E.out3(ss(t, p.t0, p.t0 + 0.7)));
  fr.g({ a, s: sc, at: [W / 2, 860] }, () => {
    fr.text('被裁之后', 0, 0, { font: 'serifm', size: 156, color: C.gold, align: 'c', track: 6, grad: [[0, C.goldHi], [1, C.gold]], glow: 18, glowA: 0.35 });
    fr.text('路不止一条，但门槛不一样', 0, 128, { font: 'serifr', size: 44, color: C.dim, align: 'c', track: 4 });
    fr.line(-150, 200, 150, 200, { color: C.gold, w: 2, a: 0.8, glow: 6 });
  });
};

/* ---------- ④ 岔路：三条路各自标门槛 ---------- */
CH.forks = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const base = [W / 2, 1380];
  const items = [
    { x: 250, y: 640, zh: '考公', limit: '卡 35 岁线', t0: p.t0 + 0.2, killed: p.kill0 },
    { x: 540, y: 600, zh: '打工', limit: '时薪换时间', t0: p.t0 + 0.9, killed: 9e9 },
    { x: 830, y: 640, zh: '开店', limit: '先要十万', t0: p.t0 + 1.6, killed: p.kill2 },
  ];
  fr.g({ a }, () => {
    // 主干
    fr.line(base[0], base[1], base[0], base[1] - 120, { color: C.line, w: 3, a: 0.35 });
    fr.circle(base[0], base[1], 10, { fill: C.gold, a: 0.9 });
    items.forEach((it) => {
      const k = ss(t, it.t0, it.t0 + 0.7);
      if (k <= 0) return;
      const dead = t >= it.killed;
      const kk = dead ? ss(t, it.killed, it.killed + 0.5) : 0;
      // 连接线
      fr.poly([[base[0], base[1] - 120], [(base[0] + it.x) / 2, it.y + 190], [it.x, it.y + 110]], { color: dead ? C.faint : C.line, w: 2.5, a: 0.45 * k, k });
      // 卡片
      fr.g({ a: k * (1 - 0.45 * kk) }, () => {
        card(fr, it.x - 130, it.y - 90, 260, 180, { color: dead ? C.faint : C.line, r: 18 });
        fr.text(it.zh, it.x, it.y - 22, { font: 'serifm', size: 56, color: dead ? C.faint : C.ink, align: 'c', track: 4 });
        fr.text(it.limit, it.x, it.y + 46, { font: 'serifr', size: 30, color: dead ? C.faint : (dead ? C.dim : C.dim), align: 'c', track: 2 });
      });
      // 划掉
      if (kk > 0) {
        const w = 260 * E.out3(kk);
        fr.line(it.x - w / 2, it.y - 8, it.x + w / 2, it.y - 8, { color: C.red, w: 4, a: 0.9, glow: 8, glowA: 0.35 });
      }
    });
  });
};

/* ---------- ⑤ 两条比例条：时间 vs 成长 ---------- */
CH.barsRow = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const rows = [
    { zh: '时间被占满', v: 1.0, col: C.dim, t0: p.t0 + 0.2 },
    { zh: '能力在涨', v: 0.12, col: C.gold, t0: p.t0 + 0.6 },
  ];
  const x0 = 120, wMax = 840;
  fr.g({ a }, () => {
    rows.forEach((r, i) => {
      const k = ss(t, r.t0, r.t0 + 0.8), y = 860 + i * 220;
      tag(fr, r.zh, x0, y - 46, { size: 36, color: C.dim, align: 'l', track: 2, a: k });
      fr.rect(x0, y, wMax, 54, { r: 27, color: C.faint, w: 1.5, a: 0.5 * k });
      fr.rect(x0, y, wMax * Math.min(r.v, 0.92) * E.out3(k), 54, { r: 27, fill: r.col, fa: 0.85, a: k, glow: 10, glowA: 0.28 });
      fr.text(Math.round(r.v * 100) + '%', x0 + wMax - 6, y - 22, { font: 'latinm', size: 34, color: r.col, align: 'r', a: k });
    });
    tag(fr, '同样干十年，差别在时间换来了什么', W / 2, 1230, { size: 32, color: C.dim, a: ss(t, p.t0 + 0.55, p.t0 + 0.95) * 0.95 });
  });
};

/* ---------- ⑥ 秤：8 元/公斤 ---------- */
CH.scalePiece = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const cx = W / 2, panY = 1080, panW = 520;
  const show = ss(t, p.t0 + 0.2, p.t0 + 0.9);
  const boxDrop = ss(t, p.t0 + 0.5, p.t0 + 1.3);
  fr.g({ a }, () => {
    // 秤盘 + 机身
    fr.rect(cx - panW / 2, panY, panW, 18, { r: 9, color: C.line, w: 3, a: 0.9 * show, fill: 'rgba(24,19,12,0.7)' });
    fr.rect(cx - 160, panY + 30, 320, 220, { r: 16, color: C.line, w: 2.5, a: 0.8 * show });
    fr.rect(cx - 210, panY + 240, 420, 22, { r: 11, color: C.line, w: 2.5, a: 0.8 * show });
    // 读数
    const read = lerp(0, p.kg || 8, E.out3(ss(t, p.t0 + 1.0, p.t0 + 1.8)));
    fr.text((p.kg || 8).toFixed(2), cx, panY + 128, { font: 'latinm', size: 88, color: C.gold, align: 'c', a: show, glow: 14, glowA: 0.3 });
    fr.text('运费（元）', cx, panY + 196, { font: 'serifr', size: 28, color: C.dim, align: 'c', a: show });
    // 包裹
    if (boxDrop > 0) {
      const bw = 320, bh = 240, by = lerp(panY - 700, panY - bh, E.in2(boxDrop));
      fr.g({ at: [cx, by], s: [1, 1 + 0.04 * Math.exp(-Math.max(0, (t - p.t0 - 1.3) * 7)) * Math.cos((t - p.t0 - 1.3) * 14)] }, () => {
        fr.poly([[-bw / 2, 0], [-bw / 2 + 34, -40], [bw / 2 + 34, -40], [bw / 2, 0]], { color: C.line, w: 3, a: 0.9 });
        fr.poly([[bw / 2, 0], [bw / 2 + 34, -40], [bw / 2 + 34, bh - 40], [bw / 2, bh]], { color: C.line, w: 3, a: 0.9 });
        fr.rect(-bw / 2, 0, bw, bh, { color: C.line, w: 3, a: 0.95 });
        fr.line(0, 0, 0, bh, { color: C.gold, w: 4, a: 0.5 });
        fr.text('1 公斤', 0, bh * 0.55, { font: 'serifr', size: 40, color: C.ink, align: 'c', a: 0.95 });
      });
    }
    tag(fr, '示例单价，按实际物流报价算', W / 2, 1490, { size: 26, color: C.faint, a: 0.9 * show });
  });
};

/* ---------- ⑦ 大数字（可红可金） ---------- */
CH.numRoll = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const k = ss(t, p.t0 + 0.1, p.t0 + 1.2);
  const v = lerp(0, p.to, E.out3(k));
  const col = p.red ? C.red : C.gold;
  const shake = p.shake ? Math.sin(t * 26) * 4 * Math.max(0, 1 - Math.abs(t - (p.t0 + 1.4)) * 2) : 0;
  fr.g({ a, at: [W / 2 + shake, 880] }, () => {
    const str = p.dec ? v.toFixed(p.dec) : Math.round(v).toLocaleString('en-US');
    fr.text((p.prefix || '') + str + (p.suffix || ''), 0, 0, { font: 'latinm', size: p.size || 176, color: col, align: 'c', glow: 18, glowA: 0.35 });
    fr.text(p.label || '', 0, 150, { font: 'serifr', size: 38, color: C.dim, align: 'c', track: 4 });
  });
};

/* ---------- ⑧ 打勾清单：起步条件 ---------- */
CH.tickList = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const rows = p.rows || [];
  fr.g({ a }, () => {
    tag(fr, p.title || '起步要什么', W / 2, 520, { size: 44, color: C.ink, track: 4 });
    rows.forEach((r, i) => {
      const k = ss(t, p.t0 + 0.25 + i * 0.28, p.t0 + 0.6 + i * 0.28);
      if (k <= 0) return;
      const y = 720 + i * 170, x = 170;
      fr.rect(x, y - 38, 76, 76, { r: 16, color: r.no ? C.faint : C.gold, w: 3, a: 0.9 * k });
      if (r.no) fr.line(x + 18, y - 2, x + 58, y - 2, { color: C.dim, w: 4, a: 0.9 * k });
      else fr.poly([[x + 18, y + 4], [x + 34, y + 22], [x + 60, y - 22]], { color: C.gold, w: 5, a: 0.95 * k });
      fr.text(r.zh, x + 110, y, { font: 'serifm', size: 46, color: r.no ? C.faint : C.ink, align: 'l', track: 2, a: k });
      if (r.note) fr.text(r.note, W - 170, y, { font: 'serifr', size: 28, color: C.dim, align: 'r', a: 0.9 * k });
    });
    tag(fr, p.foot || '不看学历、不用辞职', W / 2, 1330, { size: 30, color: C.dim, a: ss(t, p.t0 + 1.2, p.t0 + 1.7) * 0.9 });
  });
};

/* ---------- ⑨ 对比双卡：互联网+ → AI+电商 ---------- */
CH.compareDuo = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const kL = ss(t, p.t0 + 0.1, p.t0 + 0.6), kR = ss(t, p.t0 + 0.9, p.t0 + 1.4);
  fr.g({ a }, () => {
    const w = 380, h = 320, yL = 800, yR = 800;
    fr.g({ a: kL }, () => {
      card(fr, 90, yL, w, h, { color: C.faint, r: 20 });
      fr.text('互联网 +', 90 + w / 2, yL + 70, { font: 'serifm', size: 52, color: C.ink, align: 'c', track: 2 });
      fr.text('零售 · 支付 · 物流', 90 + w / 2, yL + 150, { font: 'serifr', size: 30, color: C.dim, align: 'c' });
      fr.text('十年，重做了一遍', 90 + w / 2, yL + 220, { font: 'serifr', size: 30, color: C.dim, align: 'c' });
    });
    fr.g({ a: kR }, () => {
      card(fr, 610, yR, w, h, { color: C.gold, r: 20, glow: true });
      fr.text('AI + 电商', 610 + w / 2, yR + 70, { font: 'serifm', size: 52, color: C.goldHi, align: 'c', track: 2 });
      fr.text('选品 · 文案 · 图 · 剪辑', 610 + w / 2, yR + 150, { font: 'serifr', size: 28, color: C.dim, align: 'c' });
      fr.text('一个人也能跑完', 610 + w / 2, yR + 220, { font: 'serifr', size: 30, color: C.gold, align: 'c' });
    });
    // 箭头
    const ka = ss(t, p.t0 + 0.7, p.t0 + 1.2);
    if (ka > 0) {
      const ax = 470, ay = yL + 160, len = 140 * E.out3(ka);
      fr.line(ax, ay, ax + len, ay, { color: C.gold, w: 4, a: 0.9 });
      fr.poly([[ax + len, ay], [ax + len - 22, ay - 14], [ax + len - 22, ay + 14]], { fill: C.gold, a: 0.9 });
    }
    tag(fr, '这一轮，像当年互联网 + 改造零售', W / 2, 1230, { size: 32, color: C.dim, a: ss(t, p.t0 + 1.3, p.t0 + 1.8) * 0.95 });
  });
};

/* ---------- ⑩ 收尾清单卡（可截图） ---------- */
CH.listCard = function (fr, t, p) {
  const a = p.a == null ? 1 : p.a;
  if (a <= 0.003) return;
  const rows = p.rows || [];
  fr.g({ a }, () => {
    card(fr, 110, 620, 860, 560, { r: 26, color: C.gold, glow: true });
    tag(fr, p.title || '门槛最低的一条', W / 2, 700, { size: 40, color: C.goldHi, track: 4 });
    rows.forEach((r, i) => {
      const k = ss(t, p.t0 + 0.2 + i * 0.3, p.t0 + 0.6 + i * 0.3);
      if (k <= 0) return;
      const y = 800 + i * 118;
      fr.g({ a: k, at: [0, (1 - E.out3(k)) * 14] }, () => {
        fr.text(String(i + 1).padStart(2, '0'), 180, y, { font: 'latin', size: 34, color: C.gold, align: 'l' });
        fr.text(r, 250, y, { font: 'serifr', size: 40, color: C.ink, align: 'l', track: 2 });
      });
    });
    tag(fr, p.foot || '', W / 2, 1250, { size: 30, color: C.dim, a: ss(t, p.t0 + 1.3, p.t0 + 1.8) });
  });
};
})();
