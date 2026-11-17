// make_cues.mjs — 从 film.json 生成配乐的 cues.json（再交给 score.mjs 合成）。
//   node scripts/make_cues.mjs <工程>/film.json [--sfx-only] > <工程>/scripts/cues.json
//     --sfx-only：只要卡点音效（换章、片名、反转、盖章、片尾），不要音乐。用自己的歌或平台曲库时叠在歌上面。
// 配乐跟着片子的结构走，不用手排：
//   风格（film.json 的 music.style，不写按 bpm 选：128 → tension，100 → warm，其他 → drive）决定和弦、鼓型、音色；
//   每章换一个和弦；第一章只有拨弦 / 铃声和轻底鼓，从第二章起整套鼓进来；
//   反转那一章（chapter.turn = true，不写就取倒数第二章）之前的一小节撤掉鼓，留一口气，反转落在重拍上全编制回来，
//   从反转起加一条旋律（让后半段像一首歌在往上走）；
//   每句字幕起点一声轻 tick，每章起点一声 drop，片名和反转各一记 boom，盖章（shot.stamp）那一拍一记砸章声。
//   开场章：第一帧一记 boom，每小节第一拍一下轻底鼓（前 3 秒要有冲击，11-16 实测原来开头 3 小节是全片最安静的）。
import {readFileSync} from 'node:fs';

const film = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const SFX_ONLY = process.argv.includes('--sfx-only');
const BPM = film.bpm || 112, BEAT = 60 / BPM, BAR = BEAT * 4, PHASE = film.phase || 0;
const chapters = film.chapters || [];

// ---------- 风格：和弦（根音 + 琶音）、旋律用哪件乐器、鼓型、合成器调色 ----------
const STYLES = {
  drive: {   // 律动（默认，和标杆样片一个路子）：小调四和弦，八分音符拨弦，四拍底鼓 + 二四拍拍手
    palette: 'poster', lead: 'bell', kick: 1, clap: true, knock: false, swing: 0, hat16: false, bassEvery: 1, bed: {pump: 0.4, cutoff: 2400, gain: 0.17, bass: 1},
    chords: [['A2', 'A4 C5 E5 C5 A4 E5 C5 E5'], ['F2', 'F4 A4 C5 A4 F4 C5 A4 C5'], ['C3', 'C5 E5 G5 E5 C5 G5 E5 G5'], ['G2', 'G4 B4 D5 B4 G4 D5 B4 D5']],
  },
  tension: {   // 紧张：和声小调（E 大三和弦往回拉），十六分音符镲，八分音符低音一直往前推
    palette: 'swiss', lead: 'pluck', kick: 1, clap: true, knock: false, swing: 0, hat16: true, bassEvery: 0.5, bed: {pump: 0.45, cutoff: 1800, gain: 0.16, bass: 1},
    chords: [['A2', 'A4 C5 E5 A5 E5 C5 A4 C5'], ['A2', 'A4 C5 F5 A5 F5 C5 A4 C5'], ['F2', 'F4 A4 C5 F5 C5 A4 F4 A4'], ['E2', 'E4 G#4 B4 E5 B4 G#4 E4 G#4']],
  },
  warm: {   // 温暖 / 治愈：大调四和弦，铃声琶音，底鼓只在一三拍，二四拍木鱼，不用拍手
    palette: 'data', lead: 'bell', kick: 2, clap: false, knock: true, swing: 0, hat16: false, bassEvery: 2, bed: {pump: 0.22, cutoff: 1400, gain: 0.14, bass: 2},
    chords: [['C3', 'C5 E5 G5 E5 C5 G5 E5 G5'], ['G2', 'B4 D5 G5 D5 B4 G5 D5 G5'], ['A2', 'A4 C5 E5 C5 A4 E5 C5 E5'], ['F2', 'A4 C5 F5 C5 A4 F5 C5 F5']],
  },
  doc: {   // 纪录片：小调钢琴柱式和弦 + 长音铺底 + 很轻的打击，不抽吸（照 Vibe 知识大赏横屏讲概念系列的配乐路子：沉静、留白）
    palette: 'data', lead: 'bell', kick: 2, clap: false, knock: false, swing: 0, hat16: false, bassEvery: 2, piano: true, bed: {pump: 0, cutoff: 900, gain: 0.08, bass: 4},
    chords: [['A2', 'A3 C4 E4 A4 E4 C4 A3 C4'], ['F2', 'F3 A3 C4 F4 C4 A3 F3 A3'], ['C3', 'C4 E4 G4 C5 G4 E4 C4 E4'], ['G2', 'G3 B3 D4 G4 D4 B3 G3 B3']],
  },
  lofi: {   // 轻松 / 聊天感：七和弦（Dm7 G7 Cmaj7 Am7），摇摆的八分音符，木鱼当军鼓
    palette: 'riso', lead: 'pluck', kick: 2, clap: false, knock: true, swing: 0.16, hat16: false, bassEvery: 2, bed: {pump: 0.15, cutoff: 1000, gain: 0.12, bass: 2},
    chords: [['D2', 'D4 F4 A4 C5 A4 F4 D4 F4'], ['G2', 'B3 D4 F4 A4 F4 D4 B3 D4'], ['C3', 'C4 E4 G4 B4 G4 E4 C4 E4'], ['A2', 'A3 C4 E4 G4 E4 C4 A3 C4']],
  },
};
const styleName = film.music?.style in STYLES ? film.music.style : BPM >= 124 ? 'tension' : BPM <= 104 ? 'warm' : 'drive';
const S = STYLES[styleName];
const CHORDS = S.chords.map(([root, arp]) => ({root, arp: arp.split(' ')}));

// ---------- 摊平：章、镜、句 ----------
let n = 0;
const SHOTS = [];
const CH = chapters.map((c, i) => {
  const first = n;
  (c.lines || []).forEach((ln, j) => {
    const sh = ln.shot || (j === 0 ? c.shot : null);
    if (sh || !SHOTS.length) SHOTS.push({d: sh || {}, first: n, span: 0, ch: i});
    SHOTS[SHOTS.length - 1].span++; n++;
  });
  return {i, first, last: n - 1, turn: !!c.turn, title: ((c.lines || [])[0]?.shot || c.shot)?.type === 'title'};
});
const N = n, END = PHASE + N * BAR + 0.5, at = (line) => PHASE + line * BAR;
let turn = CH.findIndex((c) => c.turn); if (turn < 0) turn = Math.max(1, CH.length - 2);

const r3 = (x) => Math.round(x * 1000) / 1000;
const up = (note, k) => note.replace(/-?\d$/, (d) => String(Number(d) + k));
const SEMI = {C: -9, D: -7, E: -5, F: -4, G: -2, A: 0, B: 2};
const hzOf = (n) => { const m = /^([A-G])(#|b)?(-?\d)$/.exec(n); return 440 * 2 ** ((SEMI[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0) + (Number(m[3]) - 4) * 12) / 12); };
const bed = [], patterns = [], events = [];

CH.forEach((c, i) => {
  const a = at(c.first), b = i === CH.length - 1 ? END : at(c.last + 1), ch = CHORDS[i % CHORDS.length];
  const gapStart = i === turn - 1 ? b - BAR : b;          // 反转前一小节：撤鼓
  if (!SFX_ONLY) {
    bed.push({type: 'pad', note: ch.root, start: r3(a), end: r3(b + 0.25), gain: 0.07, fade: 0.25});
    // 厚和弦铺底 + 持续贝斯（11-18 对照参考 BGM：它的低音 / 中频 86–97% 的时间都铺满，我们原来只有 22–41%，听着一下一下的像玩具）
    const notes = [up(ch.root, 1), ...[...new Set(ch.arp)].slice(0, 3).map((x) => up(x, -1))], B = S.bed, lift = i >= turn;   // 根音低八度垫底，低中频才厚
    bed.push({type: 'chord', notes, start: r3(a), end: r3(b + 0.12), gain: B.gain * (i === 0 ? 0.75 : 1), cutoff: B.cutoff * (lift ? 1.4 : 1), pump: {bpm: BPM, depth: B.pump}, fade: 0.06});
    if (lift) bed.push({type: 'chord', notes: notes.map((x) => up(x, 1)), start: r3(a), end: r3(gapStart + 0.12), gain: B.gain * 0.45, cutoff: B.cutoff * 1.8, pump: {bpm: BPM, depth: B.pump}, fade: 0.06, voices: 3});   // 反转后高八度再叠一层：像副歌一样变亮
    patterns.push({type: 'bass', every: B.bass, start: r3(a), end: r3(gapStart), notes: [up(ch.root, -1)], dur: r3(BEAT * B.bass * 0.97), gain: 0.26, pump: {bpm: BPM, depth: B.pump * 0.7}});
    if (S.piano) {   // 每小节第一拍一记钢琴柱式和弦，第三拍轻一点再按一次（四拍都在小节线上，字幕换句那一下就是钢琴落下来）
      const v = [...new Set([up(ch.root, 1), ...[...new Set(ch.arp)].slice(0, 3)])];
      for (let t = a, k = 0; t < gapStart - 0.01; t += BAR / 2, k++) events.push({type: 'piano', t: r3(t), notes: v, dur: r3(BAR * 0.95), gain: k % 2 ? 0.16 : 0.26, bright: i >= turn ? 0.7 : 0.45});
    }
    const arpInst = styleName === 'warm' ? 'bell' : 'pluck', sw = S.swing * BEAT;
    // 琶音：八分音符（正拍、反拍各一路）；lofi 的反拍往后拖一点（摇摆）
    if (!S.piano || i >= turn) [0, 1].forEach((odd) => patterns.push({type: arpInst, every: 1, start: r3(a + odd * (BEAT / 2 + sw)), end: r3(gapStart), notes: ch.arp.filter((_, k) => k % 2 === odd),
      gain: (i === 0 ? 0.07 : 0.055) * (arpInst === 'bell' ? 0.55 : 1), ...(arpInst === 'bell' ? {dur: 1.2} : {decay: styleName === 'lofi' ? 0.985 : 0.993}), ...(styleName === 'lofi' ? {bright: 0.2} : {})}));
    patterns.push({type: 'hat', every: 1, start: r3(a + BEAT / 2 + sw), end: r3(gapStart), gain: S.piano ? 0.035 : 0.07});
    if (i === 0) {   // 开场章不上整套鼓，但每小节第一拍一下轻底鼓：前 3 秒决定划不划走，换画面要有一下"咚"
      patterns.push({type: 'kick', every: 4, start: r3(a), end: r3(gapStart), gain: 0.32});
    }
    if (i >= 1) {
      patterns.push({type: 'kick', every: S.kick, start: r3(a), end: r3(gapStart), gain: S.kick === 1 ? 0.42 : 0.38});
      if (S.clap) patterns.push({type: 'clap', every: 2, start: r3(a + BEAT), end: r3(gapStart), gain: 0.16, tone: 0.6});
      if (S.knock) patterns.push({type: 'knock', every: 2, start: r3(a + BEAT), end: r3(gapStart), gain: 0.14, freq: styleName === 'lofi' ? 480 : 700});
      patterns.push({type: 'pluck', every: S.bassEvery, start: r3(a), end: r3(gapStart), notes: [up(ch.root, 1)], gain: S.bassEvery < 1 ? 0.06 : 0.07, decay: 0.985, bright: 0.25});
      patterns.push({type: 'hat', every: S.hat16 || i >= turn ? 0.25 : 0.5, start: r3(a), end: r3(gapStart), gain: S.hat16 || i >= turn ? 0.028 : 0.035});
    }
    if (i >= turn) {   // 旋律：从反转起，每小节 4 个四分音符，取这章和弦的音——后半段像一首歌在往上推
      const tones = [ch.arp[0], ch.arp[2], ch.arp[1], ch.arp[3] || ch.arp[2]];
      const mel = i === CH.length - 1 ? [tones[0], tones[1], tones[3], tones[1]] : [tones[1], tones[2], tones[0], tones[3]];
      patterns.push({type: S.lead, every: 1, start: r3(a), end: r3(gapStart), notes: mel.map((x) => up(x, 1)), gain: S.lead === 'bell' ? 0.1 : 0.08, ...(S.lead === 'bell' ? {dur: 1.4} : {decay: 0.995, bright: 0.55}), pan: 0.15});
    }
  }
  if (i === 0 && !c.title) events.push({type: 'boom', t: r3(a), gain: 0.42});
  if (gapStart < b) events.push({type: 'whoosh', t: r3(b - 0.62), dur: 0.6, gain: 0.22});
  if (i > 0) { events.push({type: 'whoosh', t: r3(a - 0.45), dur: 0.45, gain: 0.12}); events.push({type: 'drop', t: r3(a), freq: 760, gain: 0.22}); }
  if (c.title || i === turn) events.push({type: 'boom', t: r3(a), gain: 0.5});
});

// 盖章：和 template/film.js 同一个时刻——最后一句；那句还要出最后一条时，第三拍再砸
for (const s of SHOTS) {
  const st = typeof s.d.stamp === 'string' ? {text: s.d.stamp} : s.d.stamp;
  if (!st || !st.text || s.d.type === 'title' || s.d.type === 'statement') continue;
  const k = Math.min(Math.max(st.at == null ? s.span - 1 : Number(st.at), 0), s.span - 1);
  const items = (s.d.values || s.d.rows || s.d.nodes || s.d.items || s.d.paths || []).length;
  const t = at(s.first + k) + (s.span === 1 || items > k ? 2 * BEAT : 0);
  events.push({type: 'knock', t: r3(t), freq: 180, gain: 0.55});
  events.push({type: 'boom', t: r3(t), gain: 0.3, freq: 55, dur: 0.6});
}
// ---------- 画面动作 → 音乐（11-18 作者："配乐要跟着画面的代码走"；上游引擎 audio.py 也是按画面事件表配乐）----------
// 时刻和 template/scenes.js 用同一套算法：第 i 个东西（共 n 个）在一镜里什么时候出来。音高取这一章和弦里的音，所以是旋律不是音效。
// 用自己的歌 / 平台曲库的歌时（--sfx-only）只留不带音高的（闷击、碎裂、低音），免得和歌的调打架。
const lineText = []; chapters.forEach((c) => (c.lines || []).forEach((ln) => lineText.push(String(ln.text || ''))));
const itemAt = (span, i, n) => (n <= span || i < span - 1) ? i * BAR : (span - 1) * BAR + (i - (span - 1)) * Math.min(BEAT, (BAR * 0.55) / Math.max(n - (span - 1) - 1, 1));
const bright = ['warm', 'doc', 'lofi'].includes(styleName) ? 'bell' : 'pluck';
for (const sh of SHOTS) {
  const d = sh.d, ty = d.type, t0 = at(sh.first), span = sh.span, ch = CHORDS[sh.ch % CHORDS.length];
  const ladder = [...new Set(ch.arp)].sort((a, b) => hzOf(a) - hzOf(b)); const step = (k) => up(ladder[k % ladder.length], 1 + Math.floor(k / ladder.length));
  const note = (t, nt, g = 0.09, inst = bright) => { if (!SFX_ONLY) events.push({type: inst, t: r3(t), note: nt, gain: inst === 'bell' ? g : g * 0.9, ...(inst === 'bell' ? {dur: 1.4} : {decay: 0.994, bright: 0.6})}); };
  const thud = (t, g = 0.3) => events.push({type: 'knock', t: r3(t), freq: 210, gain: g});
  const stab = (t, notes, g = 0.08) => notes.forEach((x) => note(t, x, g, 'bell'));
  const list = d.rows || d.nodes || d.items || [];
  if (ty === 'number') {
    const v = (d.values || []).map(Number);
    v.forEach((x, i) => {
      const t = t0 + itemAt(span, i, v.length);
      if (i === 0) { note(t, step(2)); return; }
      const upward = x > v[i - 1], run = upward ? [0, 1, 2, 4] : [4, 2, 1, 0];   // 往上涨：上行；往下掉：下行
      run.forEach((k, j) => note(t + j * BEAT / 4, step(k + (upward ? 1 : 0)), 0.07));
      if (!upward) thud(t + 0.6 * BEAT, 0.2);
    });
  } else if (ty === 'fork' && d.focus == null) {
    const paths = d.paths || [], none = d.pick === -1 || d.pick === 'none', pick = none ? -1 : d.pick != null ? Number(d.pick) : paths.length - 1;
    paths.forEach((_, i) => note(t0 + (span > 1 ? Math.min(i, 3) * BEAT : i * Math.min(0.12, BEAT / paths.length)), step(i), 0.05));   // 路一拍长出一条
    const kills = paths.map((_, i) => i).filter((i) => i !== pick), steps = Math.max(span - (none ? 1 : 2), 1);
    kills.forEach((i, j) => {   // 和 scenes.js 的 killAt 一样：一句划掉一条
      const kt = span <= 1 ? (j + 1) * BEAT : (1 + Math.min(j, steps - 1)) * BAR + Math.max(0, j - (steps - 1)) * BEAT;
      thud(t0 + kt, 0.26); note(t0 + kt, up(ladder[0], 0), 0.06, 'pluck');   // 划掉砸在拍上
    });
    if (!none) stab(t0 + (span <= 1 ? (kills.length + 1) * BEAT : Math.max(span - 1, 1) * BAR), [step(0), step(2), step(4)], 0.07);   // 留下的那条：亮和弦
    else events.push({type: 'boom', t: r3(t0 + (span - 1) * BAR), gain: 0.3, freq: 45, dur: 0.8});
  } else if (ty === 'fork') {
    note(t0, step(0), 0.05); note(t0 + BEAT, step(Number(d.focus) * 2), 0.09, 'bell');   // 第 2 拍这一条亮起来
  } else if (ty === 'checklist') {
    list.forEach((r, i) => { const a = t0 + itemAt(span, i, list.length), t = a + (list.length <= span ? BEAT : 0); note(a, step(i), 0.05, 'pluck'); if (r && r.ok === false) { thud(t, 0.22); note(t, up(ladder[0], 0), 0.05, 'pluck'); } else note(t, step(2 + i), 0.09, 'bell'); });   // 第 1 拍条目、第 2 拍打勾 / 划掉
  } else if (ty === 'ledger') {
    const rows = d.rows || [], n = rows.length + (d.total ? 1 : 0); let k = 3;
    rows.forEach((r, i) => { const neg = r && (r.op === '-' || r.op === '−'); k = i === 0 ? 3 : k + (neg ? -1 : 1); note(t0 + itemAt(span, i, n), step(Math.max(0, k)), 0.06); note(t0 + itemAt(span, i, n) + (n <= span ? BEAT : 0), step(Math.max(0, k)), 0.08); if (neg) thud(t0 + itemAt(span, i, n) + (n <= span ? BEAT : 0), 0.15); });   // 第 1 拍名目、第 2 拍金额落下
    if (d.total) {
      const tot = rows.reduce((a, r) => a + ((r && (r.op === '-' || r.op === '−')) ? -1 : 1) * (Number(r && r.value) || 0), 0), t = t0 + itemAt(span, n - 1, n) + (n <= span ? BEAT : 0);   // 合计在第 2 拍砸下来
      if (tot >= 0) stab(t, [step(0), step(2), step(4)], 0.08); else { stab(t, [up(ladder[0], 0), up(ladder[1], 0)], 0.07); events.push({type: 'boom', t: r3(t), gain: 0.3, freq: 45, dur: 0.8}); }
    }
  } else if (['bars', 'steps', 'cycle', 'cards', 'timeline', 'ring'].includes(ty)) {
    const n = ty === 'ring' ? list.length + 1 : list.length;
    for (let i = 0; i < n; i++) {   // 一条一条出来：音阶一级一级往上爬
      const t = ty === 'timeline' && span <= 1 ? t0 + i * Math.min(BEAT, BAR * 0.9 / Math.max(n, 1)) : t0 + itemAt(span, i, n);
      note(t, step(i), i === n - 1 ? 0.1 : 0.08);   // 条目在拍上出现，音也在拍上
      if (span > 1 && ty !== 'timeline' && ty !== 'ring') events.push({type: 'tick', t: r3(t + BEAT), freq: 3400, gain: 0.05});   // 第 2 拍它的数 / 标签落下：一声轻响
    }
    if (ty === 'timeline' && d.breakAt != null) { const t = t0 + Number(d.breakStep ?? 1) * BAR; events.push({type: 'scratch', t: r3(t), dur: 0.35, gain: 0.25}); events.push({type: 'boom', t: r3(t), gain: 0.35, freq: 42, dur: 0.9}); }
  } else if (ty === 'compare') {
    const tr = span > 1 ? BAR : BEAT * 2;
    note(t0, step(0)); if (span > 1) note(t0 + BEAT, step(1), 0.07); note(t0 + tr, step(3), 0.08); note(t0 + tr + (span > 1 ? BEAT : 0.15), step(4), 0.1);
    if (d.badge) stab(t0 + (span >= 3 ? 2 * BAR : span > 1 ? tr + 2 * BEAT : tr + BEAT), [step(2), step(4), step(6)], 0.06);
  } else if (ty === 'object') {
    if (d.count) for (let b = 0; b < 4; b++) note(t0 + b * BEAT, step(b), 0.06, 'pluck');   // 一片东西分四批冒出来，一拍一批
    else { note(t0, step(0)); note(t0 + BEAT, step(2), 0.06); }
  } else if (ty === 'flow') {
    const tr = span > 1 ? BAR : BEAT; note(t0, step(0)); events.push({type: 'whoosh', t: r3(t0 + tr), dur: Math.min(1, 2 * BEAT), gain: 0.14}); note(t0 + tr + 2 * BEAT, step(4), 0.1);   // 出发、到达都在拍上
  } else if (ty === 'statement' || ty === 'title') {
    stab(t0, [step(0), step(2), step(4)], 0.06);
  }
}
// 提问的句子（为什么 / 怎么 / 什么 / 吗 / 呢）：句首一个上滑音，像在问
lineText.forEach((x, i) => { if (/为什么|怎么|什么|哪|吗$|呢$/.test(x)) events.push({type: 'drop', t: r3(at(i)), freq: 520, dur: 0.35, gain: 0.12}); });
if (!SFX_ONLY) for (let i = 0; i < N; i++) events.push({type: 'tick', t: r3(at(i)), freq: 2600, gain: 0.04});
events.push({type: 'bell', t: r3(at(N - 1)), note: 'A5', gain: 0.16});
events.push({type: 'boom', t: r3(at(N - 1)), gain: 0.45});

process.stdout.write(JSON.stringify({duration: r3(END), bpm: BPM, loop: false, palette: S.palette, seed: 11, style: styleName, bed, patterns, events}, null, 1) + '\n');
