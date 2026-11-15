/* 片子骨架（leadgen-knowledge-film · 30 秒 / 120 BPM / 竖屏）
 * 这里只放基础设施：GRID（小节→秒）、字幕表、字幕渲染、出处小字、每段调度。
 * 画面件在 scenes.js（已带 10 个件），本文件负责"哪一段用哪个件、参数是什么"。
 *
 * 改片子只改三处：SUBS（字幕）、draw 里的调度（用哪件、参数）、note（出处小字）。
 * 换 BPM 只给 window.FILM_BPM 赋值（或者改 BPM 常量），画面代码不用动。
 */
(function () {
'use strict';
const { W, H, clamp, lerp, seg, ss, fade, E, rng, rgba, mix } = VK;
const C = window.C;

/* 120 BPM：一拍 0.5 秒、一小节 2 秒、第一记重拍 0.4 秒 */
const BASE_BPM = 120, BPM = window.FILM_BPM || BASE_BPM, BPB = 4;
const BASE_BAR = 60 / BASE_BPM * BPB, BAR = 60 / BPM * BPB, K = BASE_BAR / BAR;
const BEAT = BAR / BPB, PHASE = 0.4;
window.BEAT = BEAT; window.BAR = BAR; window.PHASE = PHASE;

const at = (bar) => PHASE + bar * BAR;

/* 六拍起点（小节号）：人生节点 / 断裂 / 片名 / 分叉 / 收窄 / 出路 / 行动 */
const T = {
  hook: at(0), brk: at(3), title: at(4), fork: at(5),
  narrow: at(8), way: at(11), act: at(13), dur: 30.0,
};
window.T = T;

/* 字幕：≤18 字一句；{金} = 钱/结论，{!红} = 失去/被吃掉 */
const SUBS = [
  { a: 0.6, b: 2.4, zh: '第一句：把观众拉进他的处境' },
  { a: 2.6, b: 4.4, zh: '第二句：把处境说得更具体' },
  { a: 4.6, b: 6.3, zh: '第三句：点出转折' },

  { a: 6.6, b: 8.3, zh: '第四句：断裂发生' },

  { a: 10.6, b: 12.4, zh: '第五句：把几条路摆出来' },
  { a: 12.6, b: 14.4, zh: '第六句：第一条路卡在哪' },
  { a: 14.6, b: 16.3, zh: '第七句：第二条路卡在哪' },

  { a: 16.6, b: 18.4, zh: '第八句：为什么走不通' },
  { a: 18.6, b: 20.3, zh: '第九句：用数字演出来' },
  { a: 20.6, b: 22.3, zh: '第十句：把代价说清' },

  { a: 22.6, b: 24.3, zh: '第十一句：出路只要什么' },
  { a: 24.6, b: 26.3, zh: '第十二句：AI 接手了什么' },

  { a: 26.6, b: 28.3, zh: '第十三句：这一轮像什么' },
  { a: 28.6, b: 30.0, zh: '第十四句：结论 + 去主页看合集' },
];

function parseMark(s) {
  const out = []; let tone = null;
  const cs = Array.from(s);
  for (let i = 0; i < cs.length; i++) {
    const c = cs[i];
    if (c === '{') { tone = 'gold'; if (cs[i + 1] === '!') { tone = 'red'; i++; } }
    else if (c === '}') tone = null;
    else out.push({ ch: c, tone });
  }
  return out;
}

/* 字幕：竖屏下三分之一；放不下先缩字号，再按逗号折两行 */
const SUB_MAXW = 930, SUB_Y = 1600, SUB_LH = 78;
let frMeasure = null;
function fitLines(str) {
  for (let size = 56; size >= 42; size -= 2) if (frMeasure(str, size) <= SUB_MAXW) return { size, lines: [str] };
  const parts = str.split('，');
  if (parts.length > 1) {
    let best = null, bestDiff = 1e9;
    for (let i = 1; i < parts.length; i++) {
      const a = parts.slice(0, i).join('，') + '，', b = parts.slice(i).join('，');
      const w = Math.max(frMeasure(a, 48), frMeasure(b, 48));
      const d = Math.abs(frMeasure(a, 48) - frMeasure(b, 48));
      if (w <= SUB_MAXW && d < bestDiff) { best = [a, b]; bestDiff = d; }
    }
    if (best) return { size: 48, lines: best };
  }
  return { size: 42, lines: [str] };
}

function subs(fr, t) {
  if (!frMeasure) frMeasure = (str, size) => fr.measure(str, { font: 'serifm', size, track: size * 0.05 });
  for (const s of SUBS) {
    if (t < s.a || t > s.b) continue;
    const str = s.zh.replace(/\{!?|\}/g, '');
    const layout = fitLines(str);
    const stg = Math.min(0.06, 1.05 / Math.max(str.length, 1));
    const out = 1 - ss(t, s.b - 0.36, s.b);
    const y0 = SUB_Y - (layout.lines.length - 1) * SUB_LH * 0.5;
    layout.lines.forEach((line, li) => {
      const lcs = parseMark(line);
      const t0 = s.a + li * 0.2;
      fr.chars(line, W / 2, y0 + li * SUB_LH, { font: 'serifm', size: layout.size, track: layout.size * 0.05, color: C.ink, shadow: 0.55, shadowBlur: 18, shadowY: 2 }, i => {
        const k = seg(t, t0 + i * stg, t0 + i * stg + 0.3), tone = lcs[i] && lcs[i].tone;
        return { a: E.out3(k) * out, blur: (1 - k) * 7 + (1 - out) * 5, color: tone === 'red' ? C.red : tone === 'gold' ? C.gold : C.ink };
      });
    });
  }
}

/* 出处 / 前提小字：每个数字都要有依据 */
function note(fr, t, a, b, str, y = 1730) {
  const k = fade(t, a, b, 0.6, 0.6);
  if (k > 0) fr.text(str, W / 2, y, { font: 'serifr', size: 24, track: 2, color: C.dim, a: k });
}

VK.film({
  dur: PHASE + (T.dur - PHASE) / K,
  theme: 'warm', bloom: 0.58, grain: 0.045,
  meta: { title: '片名', bpm: BPM, bars: [0, 3, 5, 8, 11, 13], phase: PHASE, sections: T },
  draw(fr, t) {
    const u = PHASE + (t - PHASE) * K;
    t = u;

    /* 段落硬切，切点落在小节线上；每一段挑一个件 */
    if (t >= T.hook - 0.2 && t < T.brk) CH.timeline(fr, t, { crack: 4.3 });
    if (t >= T.brk && t < T.title) CH.breakCard(fr, t, { t0: T.brk });
    if (t >= T.title && t < T.fork) CH.titleCard(fr, t, { t0: T.title });
    if (t >= T.fork && t < T.narrow) CH.forks(fr, t, { t0: T.fork, kill0: 12.6, kill2: 14.6 });
    if (t >= T.narrow && t < T.narrow + 2) CH.barsRow(fr, t, { t0: T.narrow });
    if (t >= T.narrow + 2 && t < T.narrow + 4) CH.scalePiece(fr, t, { t0: T.narrow + 2, kg: 8 });
    if (t >= T.narrow + 4 && t < T.way) CH.numRoll(fr, t, { t0: T.narrow + 4, to: 20000, suffix: ' 元', label: '一句说明', red: true, shake: true, size: 150 });
    if (t >= T.way && t < T.way + 2) CH.tickList(fr, t, { t0: T.way, title: '起步要什么', rows: [{ zh: '一部手机', note: '就能上架' }, { zh: '一台电脑', note: '下班做' }, { zh: '学历', note: '不看', no: true }], foot: '不用辞职' });
    if (t >= T.way + 2 && t < T.act) CH.tickList(fr, t, { t0: T.way + 2, title: 'AI 接手的三件事', rows: [{ zh: '选品', note: '看数据' }, { zh: '文案', note: '写标题' }, { zh: '图片 / 剪片', note: '出素材' }], foot: '一个人也能跑完' });
    if (t >= T.act && t < T.act + 2) CH.compareDuo(fr, t, { t0: T.act });
    if (t >= T.act + 2) CH.listCard(fr, t, { t0: T.act + 2, title: '门槛最低的一条，怎么开始', rows: ['第一步', '第二步', '第三步'], foot: '主页合集' });

    /* 出处小字：有数字的地方都要有一行 */
    note(fr, t, 0.4, 6.3, '人生节点为示意，不是真实人物');
    note(fr, t, 6.4, 8.4, '场景为示意，非真实人物');
    note(fr, t, 10.4, 16.3, '数字为一般情况，各地各行业不同');
    note(fr, t, 16.4, 22.3, '数字来自作者本人账目，不是行业平均');

    subs(fr, t);
  },
});
})();
