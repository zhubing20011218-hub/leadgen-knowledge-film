/* film.js — 播放器：读同目录的 film.json，按小节排时间，画背景 / 顶栏 / 章节标 / 字幕 / 出处小字，
 * 再把每一镜交给 scenes.js 里对应的画面件。
 *
 * 规矩（改之前先读 references/03）：
 *   - 一句字幕 = 一小节。第 i 句从 phase + i × 小节 开始，画面的每一次变化都落在小节线上。
 *   - 一镜（shot）可以撑几句：后面的句子不写 shot，就是同一镜往前走一步（step + 1）。
 *   - 竖屏 1080×1920，底部 15%（y > 1632）留给平台界面，什么都不放。
 * 这个文件一般不用改；改片子只改 film.json。
 */
(function () {
'use strict';
const { W, H, clamp, lerp, seg, ss, fade, E, hash, rgba, mix } = VK;
const SAFE_BOTTOM = 1632;          // 再往下是平台的点赞 / 评论 / 文案遮挡区
const X0 = 96;                     // 左边距
const TOP_Y = 106, RULE_Y = 140;   // 顶栏
const KICK_Y = 252, HEAD_Y = 330;  // 章节小标 / 一镜的小标题
const SUB_Y = 1496, NOTE_Y = 1590; // 字幕 / 出处小字

function fail(msg) {
  document.getElementById('err').textContent = msg;
  VK.film({ dur: 1, theme: 'flat', draw(fr) { fr.text('film.json 出错：' + msg.slice(0, 60), W / 2, H / 2, { font: 'sans', size: 34, color: '#f66' }); } });
}

fetch('film.json', { cache: 'no-store' }).then(r => r.json()).then(start).catch(e => fail(String(e && e.message || e)));

function start(F) {
  const BPM = F.bpm || 112, BAR = 60 / BPM * 4, BEAT = BAR / 4, PHASE = F.phase || 0;
  window.BAR = BAR; window.BEAT = BEAT;

  /* 摊平：每句字幕一行，记住它属于哪一章、哪一镜、是这一镜的第几步 */
  const LINES = [], SHOTS = [], CHAPS = [];
  (F.chapters || []).forEach((ch, ci) => {
    const pal = NEON[ch.color] || NEON.cyan;
    const C = { i: ci, name: ch.name || '', en: (ch.en || '').toUpperCase(), col: pal.main, alt: pal.alt, first: LINES.length };
    CHAPS.push(C);
    (ch.lines || []).forEach(ln => {
      const i = LINES.length, t0 = PHASE + i * BAR;
      if (ln.shot || !SHOTS.length || SHOTS[SHOTS.length - 1].ch !== C) {
        const d = ln.shot || { type: 'statement', big: ln.text };
        SHOTS.push({ d, ch: C, first: i, t0, span: 0 });
      }
      const S = SHOTS[SHOTS.length - 1]; S.span++;
      LINES.push({ i, t0, t1: t0 + BAR, text: String(ln.text || ''), hl: ln.hl || [], note: ln.note || null, shot: S, step: S.span - 1, ch: C });
    });
    C.last = LINES.length - 1;
  });
  if (!LINES.length) return fail('没有字幕');
  SHOTS.forEach((S, k) => { S.t1 = S.t0 + S.span * BAR; S.next = SHOTS[k + 1] || null; });
  const N = LINES.length, END = PHASE + N * BAR + 0.5;

  const lineAt = t => LINES[clamp(Math.floor((t - PHASE) / BAR), 0, N - 1)];

  /* 章节色：换章时在小节线前后 0.5 秒里渐变 */
  function colorsAt(t) {
    const L = lineAt(t), C = L.ch, prev = CHAPS[C.i - 1];
    if (prev && C.first === L.i) { const k = ss(t, L.t0 - 0.25, L.t0 + 0.35); return { col: mix(prev.col, C.col, k), alt: mix(prev.alt, C.alt, k) }; }
    return { col: C.col, alt: C.alt };
  }

  /* 背景：深蓝黑 + 两团章节色的光 + 星点；画在内容层下面，不参与辉光 */
  function under(out, t) {
    const { col, alt } = colorsAt(t);
    out.fillStyle = INK.base; out.fillRect(0, 0, W, H);
    const drift = Math.sin(t * 0.21) * 40;
    let g = out.createRadialGradient(W * 0.22 + drift, H * 0.30, 0, W * 0.22 + drift, H * 0.30, H * 0.62);
    g.addColorStop(0, rgba(col, 0.30)); g.addColorStop(0.5, rgba(col, 0.09)); g.addColorStop(1, rgba(col, 0));
    out.fillStyle = g; out.fillRect(0, 0, W, H);
    g = out.createRadialGradient(W * 0.85 - drift, H * 0.66, 0, W * 0.85 - drift, H * 0.66, H * 0.48);
    g.addColorStop(0, rgba(alt, 0.16)); g.addColorStop(1, rgba(alt, 0));
    out.fillStyle = g; out.fillRect(0, 0, W, H);
    for (let i = 0; i < 90; i++) {
      const s = hash(i + 3.7), px = hash(i * 1.31 + 9) * W, py = hash(i * 2.17 + 4) * H * 0.86;
      const a = (0.10 + 0.32 * s * s) * (0.7 + 0.3 * Math.sin(t * (0.5 + s) + i));
      out.fillStyle = rgba('#C9D4FF', a); out.fillRect(px, py, s > 0.9 ? 2.2 : 1.4, s > 0.9 ? 2.2 : 1.4);
    }
    g = out.createLinearGradient(0, SAFE_BOTTOM - 120, 0, H);   // 底部压暗：平台界面压在这里
    g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,0.92)');
    out.fillStyle = g; out.fillRect(0, SAFE_BOTTOM - 120, W, H - SAFE_BOTTOM + 120);
    VK.vignette(out, 0.55);
  }

  /* 顶栏：• 01 章名 …… 05 / 14，下面一条细线，章节色的进度 */
  function topBar(fr, t, L, col) {
    const C = L.ch, num = String(C.i + 1).padStart(2, '0');
    fr.circle(X0 + 5, TOP_Y, 5, { fill: col, a: 0.95 });
    fr.text(num + '  ' + C.name, X0 + 22, TOP_Y, { font: 'sans', size: 26, track: 3, color: INK.text, align: 'l' });
    fr.text(String(L.i + 1).padStart(2, '0') + ' / ' + String(N).padStart(2, '0'), W - X0, TOP_Y, { font: 'mono', size: 25, track: 2, color: INK.dim, align: 'r' });
    fr.rect(X0, RULE_Y, W - 2 * X0, 1.5, { fill: '#FFFFFF', a: 0.10 });
    const p = clamp((t - PHASE) / (N * BAR));
    fr.rect(X0, RULE_Y - 1, (W - 2 * X0) * p, 3.5, { fill: col, a: 0.95 });
  }

  /* 章节小标：— 02 PRICE WAR；每章第一句跟着小节线滑进来 */
  function kicker(fr, t, L, col) {
    const C = L.ch, k = L.i === C.first ? ss(t, L.t0, L.t0 + 0.35) : 1;
    const label = String(C.i + 1).padStart(2, '0') + '  ' + (C.en || C.name);
    fr.g({ a: k }, () => {
      fr.rect(X0, KICK_Y - 1.5, 46 * k, 3, { fill: col });
      fr.text(label, X0 + 62 - (1 - k) * 20, KICK_Y, { font: 'sans', size: 27, track: 7, color: col, align: 'l', glow: 14 });
    });
  }

  /* 一镜的小标题（可选）：shot.head */
  function head(fr, t, S, a) {
    if (!S.d.head) return;
    const k = ss(t, S.t0, S.t0 + 0.3) * a;
    fr.text(S.d.head, X0, HEAD_Y + (1 - k) * 14, { font: 'sansh', size: 52, track: 2, color: INK.white, align: 'l', a: k });
  }

  /* 字幕：左边一条章节色竖线 + 一行粗黑体，关键词染章节色；下面一条短线随小节走完 */
  const measureCache = {};
  function subtitle(fr, t, L, col) {
    const str = L.text;
    let size = 50; while (size > 38 && fr.measure(str, { font: 'sansh', size, track: 2 }) > 840) size -= 2;
    const hlMask = Array.from(str).map(() => false);
    const chars = Array.from(str);
    L.hl.forEach(w => { const s = chars.join(''); let p = s.indexOf(w); while (p >= 0) { const a = Array.from(s.slice(0, p)).length, n = Array.from(w).length; for (let k = 0; k < n; k++) hlMask[a + k] = true; p = s.indexOf(w, p + w.length); } });
    const lt = t - L.t0, out = 1 - ss(t, L.t1 - 0.10, L.t1);
    const barK = E.out3(seg(lt, 0, 0.22));
    fr.rect(X0, SUB_Y - 30, 4, 60 * barK, { fill: col, a: out });
    fr.glow(X0 + 2, SUB_Y, 30, col, 0.35 * out);
    const stg = Math.min(0.025, 0.3 / Math.max(chars.length, 1));
    fr.chars(str, X0 + 28, SUB_Y, { font: 'sansh', size, track: 2, color: INK.white, align: 'l', shadow: 0.6, shadowBlur: 16 }, i => {
      const k = E.out3(seg(lt, 0.02 + i * stg, 0.02 + i * stg + 0.22));
      return { a: k * out, dy: (1 - k) * 12, color: hlMask[i] ? col : INK.white, glow: hlMask[i] ? 18 : 0 };
    });
    const p = seg(lt, 0, BAR);
    fr.rect(X0 + 28, SUB_Y + 52, 260, 2, { fill: '#FFFFFF', a: 0.12 * out });
    fr.rect(X0 + 28, SUB_Y + 52, 260 * p, 2, { fill: col, a: 0.9 * out });
  }

  function note(fr, t, L) {
    const s = L.note || L.shot.d.note; if (!s) return;
    const S = L.shot, k = fade(t, S.t0 + 0.2, S.t1, 0.4, 0.2);
    fr.text(s, X0 + 28, NOTE_Y, { font: 'sansr', size: 23, track: 1, color: INK.dim, align: 'l', a: 0.85 * k });
  }

  VK.film({
    dur: END, theme: 'flat', bloom: 0.55, grain: 0.03,
    meta: { title: F.title, bpm: BPM, bar: BAR, phase: PHASE, lines: N },
    draw(fr, t) {
      fr.look.bg = 'flat'; fr.look.bgo = { color: INK.base }; fr.look.under = under;
      const L = lineAt(t), S = L.shot, { col, alt } = colorsAt(t);

      /* 当前镜：小节线上进场；下一镜不同就在最后 0.16 秒退场 */
      const inK = ss(t, S.t0, S.t0 + 0.28), outK = S.next ? 1 - ss(t, S.t1 - 0.16, S.t1) : 1;
      const step = Math.min(S.span - 1, Math.max(0, Math.floor((t - S.t0) / BAR)));
      const ctx = { t, lt: t - S.t0, st: t - (S.t0 + step * BAR), step, span: S.span, bar: BAR, beat: BEAT, col, alt, d: S.d, k: inK * outK, final: S.ch.i === CHAPS.length - 1 && !S.next, X0 };
      const fn = SCENES[S.d.type] || SCENES.statement;
      if (t >= S.t0 - 0.001) fr.g({ a: ctx.k }, () => fn(fr, ctx));

      /* 换章时一下很淡的章节色闪光 */
      if (L.ch.first === L.i && L.i > 0) fr.flash(0.10 * (1 - seg(t, L.t0, L.t0 + 0.25)) * (t >= L.t0 ? 1 : 0), col);

      if (S.d.type !== 'title' && S.d.type !== 'statement') { kicker(fr, t, L, col); head(fr, t, S, outK); }
      topBar(fr, t, L, col);
      subtitle(fr, t, L, col);
      note(fr, t, L);
    },
  });
}
})();
