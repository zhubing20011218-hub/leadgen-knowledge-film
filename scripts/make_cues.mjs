// make_cues.mjs — 从 film.json 生成配乐的 cues.json（再交给 score.mjs 合成）。
//   node scripts/make_cues.mjs <工程>/film.json > <工程>/scripts/cues.json
// 配乐跟着片子的结构走，不用手排：
//   每章换一个和弦（Am → F → C → G 循环）；第一章只有拨弦和镲，从第二章起鼓进来；
//   反转那一章（film.json 里 chapter.turn = true，不写就取倒数第二章）之前的一小节撤掉鼓，留一口气，
//   反转落在重拍上全编制回来；每句字幕起点一声轻 tick，每章起点一声 drop，片名和反转各一记 boom。
import {readFileSync} from 'node:fs';

const film = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const BPM = film.bpm || 112, BEAT = 60 / BPM, BAR = BEAT * 4, PHASE = film.phase || 0;
const chapters = film.chapters || [];
let n = 0;
const CH = chapters.map((c, i) => { const first = n; n += (c.lines || []).length; return {i, first, last: n - 1, turn: !!c.turn, title: (c.lines || [])[0]?.shot?.type === 'title'}; });
const N = n, END = PHASE + N * BAR + 0.5, at = (line) => PHASE + line * BAR;
let turn = CH.findIndex((c) => c.turn); if (turn < 0) turn = Math.max(1, CH.length - 2);

const CHORDS = [
  {root: 'A2', arp: ['A4', 'C5', 'E5', 'C5', 'A4', 'E5', 'C5', 'E5']},
  {root: 'F2', arp: ['F4', 'A4', 'C5', 'A4', 'F4', 'C5', 'A4', 'C5']},
  {root: 'C3', arp: ['C5', 'E5', 'G5', 'E5', 'C5', 'G5', 'E5', 'G5']},
  {root: 'G2', arp: ['G4', 'B4', 'D5', 'B4', 'G4', 'D5', 'B4', 'D5']},
];
const r3 = (x) => Math.round(x * 1000) / 1000;
const bed = [], patterns = [], events = [];

CH.forEach((c, i) => {
  const a = at(c.first), b = i === CH.length - 1 ? END : at(c.last + 1), ch = CHORDS[i % CHORDS.length];
  const gapStart = i === turn - 1 ? b - BAR : b;          // 反转前一小节：撤鼓
  bed.push({type: 'pad', note: ch.root, start: r3(a), end: r3(b + 0.25), gain: 0.13, fade: 0.25});
  patterns.push({type: 'pluck', every: 0.5, start: r3(a), end: r3(gapStart), notes: ch.arp, gain: i === 0 ? 0.09 : 0.075, decay: 0.993});
  patterns.push({type: 'hat', every: 1, start: r3(a + BEAT / 2), end: r3(gapStart), gain: 0.07});
  if (i >= 1) {
    patterns.push({type: 'kick', every: 1, start: r3(a), end: r3(gapStart), gain: 0.5});
    patterns.push({type: 'clap', every: 2, start: r3(a + BEAT), end: r3(gapStart), gain: 0.16, tone: 0.6});
    patterns.push({type: 'pluck', every: 1, start: r3(a), end: r3(gapStart), notes: [ch.root.replace(/\d/, (d) => String(Number(d) + 1))], gain: 0.12, decay: 0.985, bright: 0.25});
    patterns.push({type: 'hat', every: 0.5, start: r3(a), end: r3(gapStart), gain: 0.035});
  }
  if (gapStart < b) events.push({type: 'whoosh', t: r3(b - 0.62), dur: 0.6, gain: 0.22});
  if (i > 0) { events.push({type: 'whoosh', t: r3(a - 0.45), dur: 0.45, gain: 0.12}); events.push({type: 'drop', t: r3(a), freq: 760, gain: 0.22}); }
  if (c.title || i === turn) events.push({type: 'boom', t: r3(a), gain: 0.5});
});
for (let i = 0; i < N; i++) events.push({type: 'tick', t: r3(at(i)), freq: 2600, gain: 0.06});
events.push({type: 'bell', t: r3(at(N - 1)), note: 'A5', gain: 0.16});
events.push({type: 'boom', t: r3(at(N - 1)), gain: 0.45});

process.stdout.write(JSON.stringify({duration: r3(END), bpm: BPM, loop: false, palette: 'poster', seed: 11, bed, patterns, events}, null, 1) + '\n');
