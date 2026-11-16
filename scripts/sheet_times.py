# -*- coding: utf-8 -*-
"""拼图该截哪些时刻：每句字幕播到 78% 的那一帧（挤在一句里的条目也都出完了、还没开始退场）。
  python3 scripts/sheet_times.py <工程>/film.json [最多几格，默认 18]
句子比格子多时，优先每一镜的第一句，再均匀补。"""
import json, sys

f = json.load(open(sys.argv[1], encoding="utf-8")); cap = int(sys.argv[2]) if len(sys.argv) > 2 else 18
bar = 60 / (f.get("bpm") or 112) * 4; ph = f.get("phase") or 0
lines, firsts = [], []
for c in f.get("chapters") or []:
    for j, ln in enumerate(c.get("lines") or []):
        if ln.get("shot") or (j == 0 and c.get("shot")): firsts.append(len(lines))
        lines.append(ln)
idx = list(range(len(lines)))
if len(idx) > cap:
    pick = firsts[:cap]
    rest = [i for i in idx if i not in pick]
    while len(pick) < cap and rest: pick.append(rest.pop(len(rest) // 2))
    idx = sorted(pick)[:cap]
print(" ".join(f"{ph + (i + 0.78) * bar:.2f}" for i in idx))
