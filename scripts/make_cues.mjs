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
    palette: 'poster', lead: 'bell', kick: 1, clap: true, knock: false, swing: 0, hat16: false, bassEvery: 1,
    chords: [['A2', 'A4 C5 E5 C5 A4 E5 C5 E5'], ['F2', 'F4 A4 C5 A4 F4 C5 A4 C5'], ['C3', 'C5 E5 G5 E5 C5 G5 E5 G5'], ['G2', 'G4 B4 D5 B4 G4 D5 B4 D5']],
  },
  tension: {   // 紧张：和声小调（E 大三和弦往回拉），十六分音符镲，八分音符低音一直往前推
    palette: 'swiss', lead: 'pluck', kick: 1, clap: true, knock: false, swing: 0, hat16: true, bassEvery: 0.5,
    chords: [['A2', 'A4 C5 E5 A5 E5 C5 A4 C5'], ['A2', 'A4 C5 F5 A5 F5 C5 A4 C5'], ['F2', 'F4 A4 C5 F5 C5 A4 F4 A4'], ['E2', 'E4 G#4 B4 E5 B4 G#4 E4 G#4']],
  },
  warm: {   // 温暖 / 治愈：大调四和弦，铃声琶音，底鼓只在一三拍，二四拍木鱼，不用拍手
    palette: 'data', lead: 'bell', kick: 2, clap: false, knock: true, swing: 0, hat16: false, bassEvery: 2,
    chords: [['C3', 'C5 E5 G5 E5 C5 G5 E5 G5'], ['G2', 'B4 D5 G5 D5 B4 G5 D5 G5'], ['A2', 'A4 C5 E5 C5 A4 E5 C5 E5'], ['F2', 'A4 C5 F5 C5 A4 F5 C5 F5']],
  },
  lofi: {   // 轻松 / 聊天感：七和弦（Dm7 G7 Cmaj7 Am7），摇摆的八分音符，木鱼当军鼓
    palette: 'riso', lead: 'pluck', kick: 2, clap: false, knock: true, swing: 0.16, hat16: false, bassEvery: 2,
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
    if (sh || !SHOTS.length) SHOTS.push({d: sh || {}, first: n, span: 0});
    SHOTS[SHOTS.length - 1].span++; n++;
  });
  return {i, first, last: n - 1, turn: !!c.turn, title: ((c.lines || [])[0]?.shot || c.shot)?.type === 'title'};
});
const N = n, END = PHASE + N * BAR + 0.5, at = (line) => PHASE + line * BAR;
let turn = CH.findIndex((c) => c.turn); if (turn < 0) turn = Math.max(1, CH.length - 2);

const r3 = (x) => Math.round(x * 1000) / 1000;
const up = (note, k) => note.replace(/-?\d$/, (d) => String(Number(d) + k));
const bed = [], patterns = [], events = [];

CH.forEach((c, i) => {
  const a = at(c.first), b = i === CH.length - 1 ? END : at(c.last + 1), ch = CHORDS[i % CHORDS.length];
  const gapStart = i === turn - 1 ? b - BAR : b;          // 反转前一小节：撤鼓
  if (!SFX_ONLY) {
    bed.push({type: 'pad', note: ch.root, start: r3(a), end: r3(b + 0.25), gain: styleName === 'warm' ? 0.15 : 0.13, fade: 0.25});
    const arpInst = styleName === 'warm' ? 'bell' : 'pluck', sw = S.swing * BEAT;
    // 琶音：八分音符（正拍、反拍各一路）；lofi 的反拍往后拖一点（摇摆）
    [0, 1].forEach((odd) => patterns.push({type: arpInst, every: 1, start: r3(a + odd * (BEAT / 2 + sw)), end: r3(gapStart), notes: ch.arp.filter((_, k) => k % 2 === odd),
      gain: (i === 0 ? 0.09 : 0.075) * (arpInst === 'bell' ? 0.55 : 1), ...(arpInst === 'bell' ? {dur: 1.2} : {decay: styleName === 'lofi' ? 0.985 : 0.993}), ...(styleName === 'lofi' ? {bright: 0.2} : {})}));
    patterns.push({type: 'hat', every: 1, start: r3(a + BEAT / 2 + sw), end: r3(gapStart), gain: 0.07});
    if (i === 0) {   // 开场章不上整套鼓，但每小节第一拍一下轻底鼓：前 3 秒决定划不划走，换画面要有一下"咚"
      patterns.push({type: 'kick', every: 4, start: r3(a), end: r3(gapStart), gain: 0.32});
    }
    if (i >= 1) {
      patterns.push({type: 'kick', every: S.kick, start: r3(a), end: r3(gapStart), gain: S.kick === 1 ? 0.5 : 0.42});
      if (S.clap) patterns.push({type: 'clap', every: 2, start: r3(a + BEAT), end: r3(gapStart), gain: 0.16, tone: 0.6});
      if (S.knock) patterns.push({type: 'knock', every: 2, start: r3(a + BEAT), end: r3(gapStart), gain: 0.14, freq: styleName === 'lofi' ? 480 : 700});
      patterns.push({type: 'pluck', every: S.bassEvery, start: r3(a), end: r3(gapStart), notes: [up(ch.root, 1)], gain: S.bassEvery < 1 ? 0.1 : 0.12, decay: 0.985, bright: 0.25});
      patterns.push({type: 'hat', every: S.hat16 ? 0.25 : 0.5, start: r3(a), end: r3(gapStart), gain: S.hat16 ? 0.028 : 0.035});
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
if (!SFX_ONLY) for (let i = 0; i < N; i++) events.push({type: 'tick', t: r3(at(i)), freq: 2600, gain: 0.06});
events.push({type: 'bell', t: r3(at(N - 1)), note: 'A5', gain: 0.16});
events.push({type: 'boom', t: r3(at(N - 1)), gain: 0.45});

process.stdout.write(JSON.stringify({duration: r3(END), bpm: BPM, loop: false, palette: S.palette, seed: 11, style: styleName, bed, patterns, events}, null, 1) + '\n');
