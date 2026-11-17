# -*- coding: utf-8 -*-
"""用自己的歌：量速度、找每小节第一拍、挑最合适的一段，把片子卡到这首歌的重拍上。只用 ffmpeg + Python 标准库。
  python3 scripts/fit_song.py <工程> <歌.mp3> --licensed          分析这首歌，改好 film.json 的 bpm 和 music（build.sh 会用它代替合成配乐）
  python3 scripts/fit_song.py <工程> <放歌的文件夹> --licensed     选歌：逐首分析排名，用最合适的那首（--top 只排名不改）
  python3 scripts/fit_song.py <歌或文件夹>                         只看分析结果（速度、节拍稳不稳、哪段最响），不改任何文件
--shift=N（1–3）：出片后听着字幕换句落在反拍上（不是一小节最重的那一下），加它把小节起点挪 N 拍再跑一次
--licensed 是你确认这首歌能商用（自己做的、买了授权的、免版税曲库下载的）。平台热歌、来路不明的 mp3 不要用：
合进视频文件里发出去会被判版权、静音或限流；想用平台热歌，就用 build.sh 出的「配平台音乐用」那一版，在 App 里加。

怎么量（为什么不装别的库）：ffmpeg 把歌解成 11025Hz 单声道 → 每 10 毫秒算一次响度 → 响度突然变大的地方是"起音"；
起音的自相关找速度（偏向 90–140 BPM，抖音知识片常见的速度），再在 ±3% 里细调到能对齐最多起音的那个速度；
只看低频（底鼓）的起音，判断四拍里哪一拍是每小节第一拍。最后按"整段够响 + 反转那一句正好落在歌变强的地方 + 从乐句开头起"挑段落。"""
import array, json, math, os, re, subprocess, sys
from pathlib import Path

SR, HOP = 11025, 110                    # 每帧约 10 毫秒
SHIFT = next((int(x.split("=")[1]) for x in sys.argv if x.startswith("--shift=")), 0)
FPS = SR / HOP
AUDIO = re.compile(r"\.(mp3|m4a|aac|wav|flac|ogg|opus)$", re.I)


def decode(path, band=None):
    af = ["-af", f"highpass=f={band[0]},lowpass=f={band[1]}"] if band else []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), *af, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    a = array.array("h"); a.frombytes(raw[: len(raw) // 2 * 2]); return a


def envelope(x):
    """每帧的 log 能量，和它的正向变化（起音强度）"""
    e = []
    for i in range(0, len(x) - HOP, HOP):
        s = 0
        for v in x[i:i + HOP]: s += v * v
        e.append(math.log10(s / HOP + 1.0))
    on = [0.0] + [max(0.0, e[i] - e[i - 1]) for i in range(1, len(e))]
    m = sorted(on)[len(on) // 2] if on else 0   # 减掉中位数：持续的铺底不算起音
    return e, [max(0.0, v - m) for v in on]


BANDS = [(30, 120), (120, 300), (300, 800), (800, 2500), (2500, 6000), (6000, 11000)]


def flux(envs):
    """分频段起音：每个频段 log 能量的上升加起来，再减掉前后 0.5 秒的平均（只留比周围突出的）。
    11-18：商业成品歌压得很满，总音量几乎不跳，只看总音量时鼓点被埋掉——参考 BGM 和没有鼓的环境音得分一样；
    分频段后参考 BGM 2.16、朋友样片 2.33、环境音 1.15，分得开"""
    n = min(len(e) for e in envs)
    out = [0.0] + [sum(max(0.0, e[i] - e[i - 1]) for e in envs) for i in range(1, n)]
    W = 50; pre = [0.0]
    for v in out: pre.append(pre[-1] + v)
    return [max(0.0, out[i] - (pre[min(n, i + W)] - pre[max(0, i - W)]) / (min(n, i + W) - max(0, i - W))) for i in range(n)]


def tempo(on):
    """自相关挑速度，偏向 90–140；再细调到对齐起音最多的那个速度和第一拍的位置"""
    seg = on[: int(FPS * 90)]
    best, cand = None, []
    for bpm10 in range(700, 1810, 5):     # 70–181 BPM，步长 0.5
        bpm = bpm10 / 10; lag = FPS * 60 / bpm; L = int(round(lag))
        ac = sum(seg[i] * seg[i + L] for i in range(0, len(seg) - L)) / max(1, len(seg) - L)
        prior = math.exp(-0.5 * (math.log2(bpm / 115) / 0.45) ** 2)
        cand.append((ac * prior, bpm))
    cand.sort(reverse=True)
    peaks = [i for i in range(1, len(on) - 1) if on[i] > 0 and on[i] >= on[i - 1] and on[i] >= on[i + 1]]
    peaks = sorted(peaks, key=lambda i: -on[i])[:1500]
    for _, b0 in cand[:3]:                # 头三个候选各细调一遍，取对得最齐的
        for k in range(-30, 31):
            bpm = b0 * (1 + k / 1000); P = FPS * 60 / bpm; bins = [0.0] * 48
            for i in peaks: bins[int((i % P) / P * 48) % 48] += on[i]
            j = max(range(48), key=lambda q: bins[q - 1] + bins[q] + bins[(q + 1) % 48])
            score = bins[j - 1] + bins[j] + bins[(j + 1) % 48]
            if not best or score > best[0]: best = (score, bpm, (j + 0.5) / 48 * P)
    _, bpm, off = best
    total = sum(on[i] for i in peaks) or 1
    return bpm, off, best[0] / total      # 速度、第一拍偏移（帧）、多少起音落在拍上（节拍稳不稳）


def analyze(path):
    x = decode(path); e = envelope(x)[0]
    envs = [envelope(decode(path, b))[0] for b in BANDS]; on = flux(envs)
    low = envs[0]; mid = [(a + b) / 2 for a, b in zip(envs[2], envs[3])]   # 底鼓、和弦 / 旋律
    dur = len(x) / SR
    bpm, off, steady = tempo(on)
    P = FPS * 60 / bpm
    beats = []; t = off
    while t < len(on) - 1: beats.append(t); t += P
    # 四拍里哪一拍是每小节第一拍：换和弦 / 旋律的地方（中频前后一拍差得最多）+ 底鼓起音最重的那一拍。
    # 只看底鼓分不清第一拍和第三拍（四拍都有鼓时），11-17 用已知答案的片段测：只看底鼓 8/30，加上中频变化 18/27；朋友样片的真实配乐两种都对
    avg = lambda arr, a, b: sum(arr[max(0, int(a)):max(1, int(b))]) / max(1, int(b) - max(0, int(a)))
    sc = []
    for j in range(4):
        bs = [b for b in beats[j::4] if P <= b < len(e) - P] or beats[j::4]
        sc.append((sum(abs(avg(mid, b, b + P) - avg(mid, b - P, b)) for b in bs) / len(bs),
                   sum(max(0, avg(low, b, b + P / 4) - avg(low, b - P / 4, b)) for b in bs) / len(bs)))
    mx = [max(x[i] for x in sc) or 1 for i in range(2)]
    down = max(range(4), key=lambda j: sc[j][0] / mx[0] + sc[j][1] / mx[1])
    down = (down + int(SHIFT)) % 4   # --shift N：听出来换句落在反拍上时，手动挪 N 拍
    bars = beats[down::4]
    loud = [sum(e[int(b): int(b + 4 * P)]) / max(1, int(4 * P)) for b in bars]
    align = []   # 每小节：起音里有多少落在推算的拍子上（±40 毫秒）。中途变速、没有鼓的地方会低
    for b in bars:
        tot = sum(on[int(b): int(b + 4 * P)]) or 1e-9
        hit = sum(on[i] for k in range(4) for i in range(int(b + k * P) - 4, int(b + k * P) + 5) if 0 <= i < len(on))
        align.append(hit / tot / (9 / P))   # 除以"随便乱打也会落进去"的比例（9 帧窗口 × 4 拍 / 一小节的帧数）：1 = 跟乱打一样，2 = 起音大多踩在拍上
    ok = sorted(a for a, l in zip(align, loud) if l > min(loud) + 0.3 * (max(loud) - min(loud)))
    steady = ok[len(ok) // 2] if ok else 0
    return {"path": str(path), "dur": round(dur, 1), "bpm": round(bpm, 2), "steady": round(steady, 2),
            "bars": [round(b / FPS, 3) for b in bars], "loud": [round(v, 3) for v in loud], "align": [round(a, 2) for a in align]}


def pick_segment(a, n_lines, turn_line):
    """挑 n_lines 小节：整段够响 + 反转那句落在歌变强的地方 + 从 4 小节乐句的开头起"""
    bars, loud = a["bars"], a["loud"]; need = n_lines + 1
    if len(bars) < need: return None
    lo, hi = min(loud), max(loud); nl = [(v - lo) / ((hi - lo) or 1) for v in loud]
    best = None
    for s in range(0, len(bars) - need + 1):
        w = nl[s:s + n_lines]; body = sum(w) / len(w)
        quiet = sum(1 for v in w if v < 0.25) / len(w)                       # 太安静的小节（前奏、间奏）
        t = s + turn_line; jump = (sum(nl[t:t + 2]) / 2 - sum(nl[max(s, t - 2):t]) / max(1, min(2, t - s))) if turn_line and t + 2 <= len(nl) else 0
        al = sorted(a["align"][s:s + n_lines]); al_lo = al[len(al) // 10]   # 这一段里对得最差的那几小节
        score = body - 0.8 * quiet + 0.6 * max(0, jump) + (0.08 if s % 4 == 0 else 0) + 1.2 * al_lo
        if not best or score > best[0]: best = (score, s, jump, al_lo)
    _, s, jump, al_lo = best
    return {"start": bars[s], "bar": s, "turn_jump": round(jump, 2), "align": round(al_lo, 2)}


def film_info(proj):
    f = json.loads((proj / "film.json").read_text(encoding="utf-8"))
    lines, turn = 0, None
    for i, c in enumerate(f.get("chapters") or []):
        if c.get("turn") and turn is None: turn = lines
        lines += len(c.get("lines") or [])
    if turn is None:
        firsts, k = [], 0
        for c in f.get("chapters") or []: firsts.append(k); k += len(c.get("lines") or [])
        turn = firsts[max(1, len(firsts) - 2)] if len(firsts) > 2 else 0
    return f, lines, turn


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not a: sys.exit(__doc__)
    if len(a) == 1:   # 只看分析
        targets = [Path(a[0]).expanduser()]; proj = None
    else:
        proj, targets = Path(a[0]).expanduser().resolve(), [Path(a[1]).expanduser()]
    src = targets[0]
    files = sorted(p for p in src.iterdir() if AUDIO.search(p.name)) if src.is_dir() else [src]
    if not files: sys.exit(f"{src} 里没有音频文件")
    if proj and "--licensed" not in sys.argv:
        sys.exit("先确认这首歌能商用（自己做的、买了授权、免版税曲库），确认了加 --licensed 再跑。\n"
                 "平台热歌不要合进视频文件：用 build.sh 出的「配平台音乐用」那一版，在抖音 / 剪映里加歌。")
    n_lines, turn = (film_info(proj)[1:] if proj and (proj / "film.json").exists() else (14, 6))
    rows = []
    for p in files:
        try: an = analyze(p)
        except subprocess.CalledProcessError: print(f"  跳过 {p.name}：ffmpeg 读不了"); continue
        seg = pick_segment(an, n_lines, turn)
        fit = 1 - min(1, abs(math.log2(an["bpm"] / 112)) / 0.5)              # 离 112 越近越像样片的节奏
        score = (0.45 * min(1, max(0, an["steady"] - 1.2) / 1.0) + 0.35 * fit + 0.2 * max(0, (seg or {}).get("turn_jump", 0))) if seg else -1
        rows.append((score, an, seg))
        print(f"  {p.name}：{an['bpm']} BPM · 节拍{'稳' if an['steady'] >= 1.6 else '一般' if an['steady'] >= 1.3 else '不稳'}（{an['steady']}）· "
              f"{an['dur']} 秒" + (f" · 建议从 {seg['start']:.2f} 秒（第 {seg['bar'] + 1} 小节）起用，这段{'对得齐' if seg['align'] >= 1.6 else '大体对得上' if seg['align'] >= 1.3 else '有几小节对不齐'}，反转处{'变强' if seg['turn_jump'] > 0.05 else '没明显变化'}" if seg else f" · 太短，放不下 {n_lines} 小节"))
    rows.sort(key=lambda r: -r[0])
    if len(rows) > 1: print("== 推荐顺序：" + "  ".join(f"{i + 1}. {Path(r[1]['path']).name}" for i, r in enumerate(rows) if r[0] >= 0))
    if not proj or "--top" in sys.argv or not rows or rows[0][0] < 0: return
    score, an, seg = rows[0]
    if an["steady"] < 1.3 or seg["align"] < 1.3: print(f"⚠  {Path(an['path']).name} 节拍不稳或这一段对不齐（可能是现场录音、自由节奏、中途变速或没有鼓），卡点会对不齐，建议换一首有稳定鼓点的")
    f, _, _ = film_info(proj)
    old = f.get("bpm", 112); f["bpm"] = an["bpm"]; f["phase"] = 0
    f["music"] = {**(f.get("music") or {}), "song": an["path"], "start": seg["start"], "bpm": an["bpm"], "steady": an["steady"]}
    (proj / "film.json").write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
    bar = 240 / an["bpm"]
    print(f"== 用 {Path(an['path']).name}：{an['bpm']} BPM，从 {seg['start']:.2f} 秒起，一句一小节 {bar:.2f} 秒，全片 {n_lines * bar:.1f} 秒（原来 {old} BPM、{n_lines * 240 / old:.1f} 秒）")
    bp = proj / "brief.json"
    if bp.exists():
        b = json.loads(bp.read_text(encoding="utf-8")); want = round(b.get("seconds", 30) / bar)
        b["music"] = {"song": an["path"], "bpm": an["bpm"]}; bp.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
        if abs(want - n_lines) > 1:
            print(f"⚠  按这首歌的速度，{b.get('seconds')} 秒要 {want} 句，现在 {n_lines} 句：重跑 python3 scripts/ds_make.py {proj}（它会按歌的速度重新排句数）")
    print(f"下一步：bash scripts/build.sh {proj}（会用这首歌代替合成配乐，卡点音效叠在上面）")


if __name__ == "__main__":
    main()
