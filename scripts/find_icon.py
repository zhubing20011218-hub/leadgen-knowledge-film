# -*- coding: utf-8 -*-
"""找图标：python3 scripts/find_icon.py 快递 [仓库 trend …]
自带 28 个霓虹图标 + Lucide 1500+ 个线条图标（ISC 许可）。中文先查常用词表，英文按名字和标签搜。
找到的名字写进 film.json 的 "icon"。画面要的是"一眼认得出的东西"：搜不到合适的，换一个更具体的说法再搜（"效率" → "闪电" / "沙漏"）。"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWN = re.findall(r"^  (\w+)\(fr, c\)", (HERE.parent / "template/icons.js").read_text(encoding="utf-8"), re.M)
IDX = json.loads((HERE / "icon_index.json").read_text(encoding="utf-8"))
TAGS, ZH = IDX["tags"], IDX["zh"]
ALL = set(OWN) | set(TAGS)


def find(q, k=12):
    q = q.strip().lower(); out = []
    add = lambda n: n in ALL and n not in out and out.append(n)
    for w, n in ZH.items():   # 中文：词表里完全相同的排最前，再是包含的
        if q == w.lower(): add(n)
    for w, n in ZH.items():
        if q in w.lower() or (len(w) >= 2 and w.lower() in q): add(n)
    if q in ALL: add(q)
    for n in sorted(ALL, key=len):
        if q in n: add(n)
    for n in sorted(TAGS, key=len):
        if any(q == t or q in t.split() for t in TAGS[n]): add(n)
    return out[:k]


def suggest(name, k=6):
    """图标名不存在时给几个最像的（检查脚本用）"""
    import difflib
    hits = find(name, k)
    return hits or difflib.get_close_matches(str(name), sorted(ALL), n=k, cutoff=0.6)


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    for q in sys.argv[1:]:
        r = find(q)
        print(f"{q}：", "  ".join(f"{n}{'（自带）' if n in OWN else ''}" for n in r) or "没找到：换一个更具体的东西再搜，或用英文（truck、wallet、flame）")
