/* icons.js — 霓虹线条图标：让观众一眼认出"这是什么"（手机、简历、工位、包裹……）。
 * 每个图标画在以 (0,0) 为中心、±50 的格子里；调用方用 drawIcon(fr, 名字, x, y, 尺寸, 颜色, 透明度) 摆到画面上。
 * 只用线和简单的形，描边是章节色、里面填深色，和霓虹风格一致。新加图标：照下面写一个函数，再到
 * references/03 的图标表和 scripts/check_film.py 的 ICONS 里登记名字。
 */
(function () {
'use strict';
const B = () => INK.card;                         // 填充：深色卡片底
const S = (col, w = 4.5, extra) => Object.assign({ color: col, w, glow: 10 }, extra || {});

const ICONS = {
  phone(fr, c) { fr.rect(-27, -48, 54, 96, { r: 10, fill: B(), ...S(c) }); fr.line(-8, -40, 8, -40, S(c, 3.5)); fr.circle(0, 38, 4, { fill: c }); fr.rect(-19, -32, 38, 60, { r: 4, color: c, w: 2, a: 0.5 }); },
  laptop(fr, c) { fr.rect(-36, -36, 72, 48, { r: 5, fill: B(), ...S(c) }); fr.poly([[-46, 20], [46, 20], [40, 32], [-40, 32]], { close: true, fill: B(), ...S(c) }); fr.line(-8, 26, 8, 26, S(c, 3)); },
  resume(fr, c) { fr.poly([[-32, -46], [18, -46], [32, -32], [32, 46], [-32, 46]], { close: true, fill: B(), ...S(c) }); fr.poly([[18, -46], [18, -32], [32, -32]], S(c, 3.5)); fr.circle(-14, -22, 8, S(c, 3.5)); fr.line(0, -26, 22, -26, S(c, 3.5)); fr.line(0, -16, 16, -16, S(c, 3)); [6, 18, 30].forEach(y => fr.line(-20, y, 22, y, S(c, 3))); },
  person(fr, c) { fr.circle(0, -24, 16, { fill: B(), ...S(c) }); fr.path('M -32 44 C -32 6, 32 6, 32 44 Z', { fill: B(), color: c, w: 4.5, glow: 10 }); },
  people(fr, c) { [[-26, 6, 0.75], [26, 6, 0.75], [0, 0, 1]].forEach(([x, y, s]) => fr.g({ at: [x, y], s }, () => { fr.circle(0, -22, 14, { fill: B(), ...S(c) }); fr.path('M -26 38 C -26 6, 26 6, 26 38 Z', { fill: B(), color: c, w: 4.5, glow: 10 }); })); },
  bed(fr, c) { fr.rect(-46, 2, 92, 22, { r: 4, fill: B(), ...S(c) }); fr.line(-46, -26, -46, 38, S(c)); fr.line(46, 24, 46, 38, S(c)); fr.rect(-40, -12, 24, 14, { r: 6, fill: B(), ...S(c, 3.5) }); fr.path('M -12 2 C -4 -16, 30 -16, 44 2', { color: c, w: 4, glow: 10 }); },
  desk(fr, c) { fr.rect(-24, -46, 48, 32, { r: 4, fill: B(), ...S(c) }); fr.line(0, -14, 0, -2, S(c)); fr.line(-12, -2, 12, -2, S(c)); fr.line(-48, 8, 48, 8, S(c, 5)); fr.line(-40, 8, -40, 44, S(c)); fr.line(40, 8, 40, 44, S(c)); fr.rect(-30, 14, 22, 14, { r: 2, color: c, w: 3 }); },
  factory(fr, c) { fr.poly([[-46, 44], [-46, -6], [-22, -22], [-22, -6], [2, -22], [2, -6], [26, -22], [26, 44]], { close: true, fill: B(), ...S(c) }); fr.rect(30, -44, 14, 88, { fill: B(), ...S(c) }); [-34, -12, 10].forEach(x => fr.rect(x, 12, 12, 12, { color: c, w: 3 })); },
  box(fr, c) { fr.poly([[-38, -16], [0, -34], [38, -16], [0, 2]], { close: true, fill: B(), ...S(c) }); fr.poly([[-38, -16], [0, 2], [0, 44], [-38, 26]], { close: true, fill: B(), ...S(c) }); fr.poly([[38, -16], [0, 2], [0, 44], [38, 26]], { close: true, fill: B(), ...S(c) }); fr.line(-19, -25, 19, -7, S(c, 3)); },
  ship(fr, c) { fr.poly([[-48, 8], [48, 8], [36, 32], [-38, 32]], { close: true, fill: B(), ...S(c) }); [[-34, -12], [-12, -12], [10, -12], [-23, -30], [-1, -30]].forEach(([x, y]) => fr.rect(x, y, 20, 18, { fill: B(), ...S(c, 3.5) })); fr.path('M -48 42 q 12 -8 24 0 t 24 0 t 24 0 t 24 0', { color: c, w: 3, a: 0.7 }); },
  plane(fr, c) { fr.path('M -46 4 L 46 -10 L 46 2 L -46 12 Z M 4 -2 L -14 -36 L -2 -36 L 22 -6 M 4 6 L -10 36 L 2 36 L 22 2 M -40 6 L -48 -14 L -40 -14 L -30 4', { fill: B(), color: c, w: 4, glow: 10 }); },
  globe(fr, c) { fr.circle(0, 0, 44, { fill: B(), ...S(c) }); fr.ellipse(0, 0, 18, 44, S(c, 3)); fr.ellipse(0, 0, 36, 44, S(c, 2.5, { a: 0.6 })); fr.line(-44, 0, 44, 0, S(c, 3)); fr.ellipse(0, -22, 38, 6, S(c, 2.5, { a: 0.6 })); fr.ellipse(0, 22, 38, 6, S(c, 2.5, { a: 0.6 })); },
  money(fr, c) { fr.rect(-48, -26, 96, 52, { r: 6, fill: B(), ...S(c) }); fr.circle(0, 0, 15, S(c, 3.5)); fr.text('¥', 0, 1, { font: 'sansh', size: 22, color: c }); fr.circle(-34, -14, 3, { fill: c }); fr.circle(34, 14, 3, { fill: c }); },
  coins(fr, c) { [30, 14, -2, -18].forEach((y, i) => { fr.ellipse(0, y, 36, 11, { fill: B(), ...S(c, 4) }); if (i === 3) fr.text('¥', 0, y + 1, { font: 'sansh', size: 16, color: c }); }); },
  chartup(fr, c) { fr.poly([[-44, -44], [-44, 40], [46, 40]], S(c)); fr.poly([[-32, 26], [-12, 4], [6, 14], [36, -26]], S(c, 5)); fr.poly([[22, -28], [38, -28], [38, -12]], S(c, 5)); },
  chartdown(fr, c) { fr.poly([[-44, -44], [-44, 40], [46, 40]], S(c)); fr.poly([[-32, -26], [-12, -4], [6, -14], [36, 26]], S(c, 5)); fr.poly([[22, 28], [38, 28], [38, 12]], S(c, 5)); },
  clock(fr, c) { fr.circle(0, 0, 44, { fill: B(), ...S(c) }); fr.line(0, 0, 0, -28, S(c, 5)); fr.line(0, 0, 20, 10, S(c, 5)); for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; fr.line(Math.cos(a) * 36, Math.sin(a) * 36, Math.cos(a) * 40, Math.sin(a) * 40, S(c, 3)); } },
  calendar(fr, c) { fr.rect(-42, -34, 84, 76, { r: 6, fill: B(), ...S(c) }); fr.line(-42, -14, 42, -14, S(c, 3.5)); fr.line(-22, -44, -22, -26, S(c, 5)); fr.line(22, -44, 22, -26, S(c, 5)); for (let r = 0; r < 3; r++) for (let k = 0; k < 4; k++) fr.rect(-30 + k * 17, -4 + r * 14, 8, 7, { fill: c, fa: r === 1 && k === 2 ? 1 : 0.45 }); },
  cart(fr, c) { fr.poly([[-48, -36], [-34, -36], [-22, 18], [34, 18], [44, -18], [-28, -18]], S(c)); fr.circle(-16, 34, 7, { fill: B(), ...S(c) }); fr.circle(28, 34, 7, { fill: B(), ...S(c) }); },
  store(fr, c) { fr.rect(-40, -6, 80, 48, { fill: B(), ...S(c) }); fr.poly([[-46, -6], [-38, -36], [38, -36], [46, -6]], { close: true, fill: B(), ...S(c) }); [-23, 0, 23].forEach(x => fr.line(x, -36, x * 1.2, -6, S(c, 3))); fr.rect(-12, 14, 24, 28, { color: c, w: 3.5 }); },
  chat(fr, c) { fr.path('M -44 -34 Q -44 -42 -36 -42 L 36 -42 Q 44 -42 44 -34 L 44 14 Q 44 22 36 22 L -6 22 L -26 40 L -22 22 L -36 22 Q -44 22 -44 14 Z', { fill: B(), color: c, w: 4.5, glow: 10 }); [-18, 0, 18].forEach(x => fr.circle(x, -10, 5, { fill: c })); },
  ai(fr, c) { fr.rect(-30, -30, 60, 60, { r: 8, fill: B(), ...S(c) }); for (let i = -1; i <= 1; i++) { fr.line(i * 16, -30, i * 16, -44, S(c, 3.5)); fr.line(i * 16, 30, i * 16, 44, S(c, 3.5)); fr.line(-30, i * 16, -44, i * 16, S(c, 3.5)); fr.line(30, i * 16, 44, i * 16, S(c, 3.5)); } fr.text('AI', 0, 2, { font: 'sansh', size: 26, color: c, glow: 10 }); },
  video(fr, c) { fr.rect(-44, -32, 88, 64, { r: 8, fill: B(), ...S(c) }); fr.poly([[-10, -16], [18, 0], [-10, 16]], { close: true, fill: c }); },
  house(fr, c) { fr.poly([[-44, -4], [0, -44], [44, -4]], S(c, 5)); fr.rect(-32, -8, 64, 50, { fill: B(), ...S(c) }); fr.rect(-10, 14, 20, 28, { color: c, w: 3.5 }); },
  chair(fr, c) { fr.rect(-26, -48, 52, 56, { r: 6, fill: B(), ...S(c) }); fr.rect(-34, 4, 68, 14, { r: 4, fill: B(), ...S(c) }); fr.line(-28, 18, -32, 48, S(c)); fr.line(28, 18, 32, 48, S(c)); fr.line(-16, -34, 16, -34, S(c, 3)); },
  cup(fr, c) { fr.poly([[-26, -26], [26, -26], [20, 46], [-20, 46]], { close: true, fill: B(), ...S(c) }); fr.rect(-32, -38, 64, 12, { r: 4, fill: B(), ...S(c) }); fr.line(8, -38, 22, -56, S(c, 4)); [[-8, 30], [6, 34], [-2, 20], [10, 22]].forEach(([x, y]) => fr.circle(x, y, 4, { fill: c })); },
  bowl(fr, c) { fr.path('M -46 -2 L 46 -2 Q 42 40 0 42 Q -42 40 -46 -2 Z', { fill: B(), color: c, w: 4.5, glow: 10 }); fr.line(-20, 42, 20, 42, S(c)); fr.line(-6, -46, 30, -8, S(c, 4)); fr.line(8, -50, 40, -14, S(c, 4)); fr.path('M -30 -2 q 8 -16 16 0 q 8 -16 16 0', { color: c, w: 3, a: 0.7 }); },
  briefcase(fr, c) { fr.rect(-44, -22, 88, 60, { r: 6, fill: B(), ...S(c) }); fr.rect(-14, -36, 28, 14, { r: 4, color: c, w: 4 }); fr.line(-44, 2, 44, 2, S(c, 3)); fr.rect(-6, -4, 12, 12, { fill: c }); },
};

/* 画一个图标：s = 像素尺寸（图标格子 100 → s），k = 进场 0..1（缩放 + 透明），state: 'no' 盖一道红斜杠 / 'ok' 右下角一个勾 */
function drawIcon(fr, name, x, y, s, col, k = 1, state) {
  const f = ICONS[name] || lucide(name); if (!f || k <= 0) return;
  fr.g({ at: [x, y], s: (s / 100) * (0.85 + 0.15 * E3(k)), a: k }, () => {
    f(fr, col);
    if (state === 'no') { fr.line(-48, -48, 48, 48, { color: NEON.red.main, w: 8, glow: 14 }); }
    if (state === 'ok') { fr.circle(36, 36, 16, { fill: NEON.green.main }); fr.poly([[28, 36], [34, 42], [45, 30]], { color: INK.base, w: 5 }); }
  });
}
const E3 = x => 1 - Math.pow(1 - x, 3);
/* 自带的 28 个没有，就从 Lucide 图标库找（template/lucide.js，1500+ 个，名字查法：python3 scripts/find_icon.py 快递）。
 * Lucide 是 24×24 的线条图标：放大到和自带图标一样的 ±46 格子，描成同样粗细的霓虹线 */
const LUC = {};
function lucide(name) {
  const d = window.LUCIDE && window.LUCIDE[name]; if (!d) return null;
  if (!LUC[name]) { const parts = d.split('|').map(p => new Path2D(p)); LUC[name] = (fr, c) => {
    const x = fr.x; x.save(); x.translate(-46, -46); x.scale(92 / 24, 92 / 24);
    x.lineWidth = 1.25; x.lineCap = 'round'; x.lineJoin = 'round'; x.strokeStyle = c; x.shadowColor = c; x.shadowBlur = 10;
    parts.forEach(p => x.stroke(p)); x.restore();
  }; }
  return LUC[name];
}
const hasIcon = name => !!(ICONS[name] || (window.LUCIDE && window.LUCIDE[name]));

window.ICONS = ICONS; window.drawIcon = drawIcon; window.hasIcon = hasIcon;
})();
