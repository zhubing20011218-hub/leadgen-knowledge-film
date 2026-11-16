# -*- coding: utf-8 -*-
"""画面机器体检（不花钱）：每句字幕播到 78% 的那一帧，量四件事。
  python scripts/frame_qa.py <工程> [--json]
  - 太空：主画面区（顶栏以下、字幕以上）亮的东西太少
  - 偏上：主体挤在上半部、下面空着
  - 出画：亮的东西贴到左右边
  - 不动：同一镜里这一句和上一句几乎一样。说了数的句子一定要动；其余的算停顿句，最多占 1/5
看图模型看不准这几样（它看缩小的拼图），这里按像素量。结果写到 review/frame_qa.json。"""
import io, json, re, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "engine"))
import render  # noqa: E402

Z0, Z1 = 450, 1420          # 主画面区：顶栏、章节小标、章的大关键词以下，字幕以上
LUMA = 90                   # 比这个亮才算"东西"（背景光晕在 40 以下）


def measure(png, prev=None):
    from PIL import Image, ImageChops
    im = Image.open(io.BytesIO(png)).convert("L")
    zone = im.crop((0, Z0, 1080, Z1)).point(lambda v: 255 if v > LUMA else 0)
    small = zone.resize((270, (Z1 - Z0) // 4))
    px = small.load(); w, h = small.size
    rows = [y for y in range(h) if sum(1 for x in range(w) if px[x, y]) >= 2]
    lit = sum(1 for y in range(h) for x in range(w) if px[x, y]) / (w * h)
    edge = any(px[x, y] for y in range(h) for x in (0, 1, w - 2, w - 1))
    r = {"lit": round(lit, 4), "edge": edge}
    if rows:
        top, bot = rows[0] * 4 + Z0, rows[-1] * 4 + Z0
        r.update(top=top, bottom=bot, center=(top + bot) // 2, span=round((bot - top) / (Z1 - Z0), 2))
    if prev is not None:
        a = Image.open(io.BytesIO(prev)).convert("L").crop((0, Z0, 1080, Z1)).resize((270, (Z1 - Z0) // 4))
        b = im.crop((0, Z0, 1080, Z1)).resize((270, (Z1 - Z0) // 4))
        d = ImageChops.difference(a, b).point(lambda v: 255 if v > 40 else 0)
        r["changed"] = round(sum(1 for v in d.get_flattened_data() if v) / (270 * ((Z1 - Z0) // 4)), 4)
    return r


def main():
    a = sys.argv[1:]
    proj = Path(a[0]).expanduser().resolve()
    f = json.loads((proj / "film.json").read_text(encoding="utf-8"))
    bar = 60 / (f.get("bpm") or 112) * 4; ph = f.get("phase") or 0
    lines = []
    for c in f.get("chapters") or []:
        for j, ln in enumerate(c.get("lines") or []):
            sh = ln.get("shot") or (c.get("shot") if j == 0 else None)   # 章上的 shot = 第一句的
            lines.append({"text": ln.get("text", ""), "new": bool(sh), "type": (sh or {}).get("type")})
    shot_type = None
    for i, ln in enumerate(lines):
        if ln["new"]: shot_type = ln["type"]
        ln["type"] = shot_type
        ln["last"] = i == len(lines) - 1 or lines[i + 1]["new"]   # 这一镜的最后一句：东西都出齐了，才量空不空、偏不偏

    def go(pg):
        out, prev = [], None
        for i, ln in enumerate(lines):
            png = render.shot(pg, ph + (i + 0.78) * bar)
            out.append(measure(png, None if ln["new"] else prev)); prev = png
        return out
    res = render.with_page(proj, go)

    issues, still = [], []
    for i, (ln, r) in enumerate(zip(lines, res)):
        n, ty, msg = i + 1, ln["type"], []
        if ty in ("title", "statement", "number") or not ln["last"]: pass   # 大字卡、大数字本来就只占中间一条；一镜没出齐的句子不量空不空
        elif r["lit"] < 0.012 or r.get("span", 0) < 0.22: msg.append(f"画面太空（亮的部分只占 {r['lit']:.1%}，上下只铺了 {r.get('span', 0):.0%}）：条目太少就换个件，或给条目加 icon")
        elif r.get("center", 875) < 720 and r.get("bottom", Z1) < 1150: msg.append(f"主体偏上（中心在 {r['center']}，下面 {Z1 - r['bottom']}px 空着）")
        if r["edge"]: msg.append("有东西贴到画面左右边（可能出画或被裁）")
        if "changed" in r and r["changed"] < 0.004:
            still.append(n)
            if re.search(r"\d", ln["text"]): msg.append(f"和上一句画面几乎一样（只变了 {r['changed']:.1%}），可这句说了数：把这个数做成这一镜的下一条")
        r.update(line=n, text=ln["text"], type=ty)
        for m in msg: issues.append({"line": n, "type": ty, "problem": m})
    quiet = [x for x in still if not re.search(r"\d", lines[x - 1]["text"])]
    if len(quiet) > max(1, len(lines) // 5):   # 停顿句（提问 / 结论）留 1/5 的名额，和 check_film.py 一样；超了才报
        for x in quiet: issues.append({"line": x, "type": lines[x - 1]["type"], "problem": f"画面不动的句子太多（{len(quiet)} 句，最多 {max(1, len(lines) // 5)} 句）：这句给这一镜加一条它说的东西，或加 stamp 盖个章"})
    (proj / "review").mkdir(exist_ok=True)
    (proj / "review/frame_qa.json").write_text(json.dumps({"issues": issues, "frames": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    if "--json" in a: print(json.dumps(issues, ensure_ascii=False)); return
    print(f"画面体检：{len(lines)} 句，{len(issues)} 处要看")
    for x in issues: print(f"  第{x['line']}句（{x['type']}）{x['problem']}")


if __name__ == "__main__":
    main()
