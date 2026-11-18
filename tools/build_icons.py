# -*- coding: utf-8 -*-
"""从 lucide-static 生成 template/lucide.js（图标线条）和 scripts/icon_index.json（按名字 / 英文标签 / 中文词找图标）。
只在升级图标库时跑一次；生成的两个文件已经在仓库里，平时不用跑。
  npm pack lucide-static@0.469.0 && tar xzf lucide-static-0.469.0.tgz
  python3 tools/build_icons.py package/
Lucide 是 ISC 许可（见 LICENSE-THIRD-PARTY.md），只取线条数据，不改图标本身。"""
import json, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
pkg = Path(sys.argv[1])
nodes = json.loads((pkg / "icon-nodes.json").read_text())
tags = json.loads((pkg / "tags.json").read_text())
version = json.loads((pkg / "package.json").read_text())["version"]


def n(v):
    v = float(v); return str(int(v)) if v == int(v) else f"{v:g}"


def to_d(tag, a):
    """一个 SVG 元素 → 一段 path 的 d（24×24 的格子）"""
    if tag == "path": return a["d"]
    if tag == "line": return f"M{n(a['x1'])} {n(a['y1'])}L{n(a['x2'])} {n(a['y2'])}"
    if tag in ("polyline", "polygon"):
        p = a["points"].replace(",", " ").split(); pts = [f"{p[i]} {p[i+1]}" for i in range(0, len(p), 2)]
        return "M" + "L".join(pts) + ("Z" if tag == "polygon" else "")
    if tag in ("circle", "ellipse"):
        cx, cy = float(a["cx"]), float(a["cy"]); rx = float(a.get("r", a.get("rx"))); ry = float(a.get("r", a.get("ry")))
        return f"M{n(cx - rx)} {n(cy)}a{n(rx)} {n(ry)} 0 1 0 {n(2 * rx)} 0a{n(rx)} {n(ry)} 0 1 0 {n(-2 * rx)} 0"
    if tag == "rect":
        x, y, w, h = (float(a.get(k, 0)) for k in ("x", "y", "width", "height")); r = min(float(a.get("rx", a.get("ry", 0)) or 0), w / 2, h / 2)
        if not r: return f"M{n(x)} {n(y)}h{n(w)}v{n(h)}h{n(-w)}Z"
        return (f"M{n(x + r)} {n(y)}h{n(w - 2 * r)}a{n(r)} {n(r)} 0 0 1 {n(r)} {n(r)}v{n(h - 2 * r)}a{n(r)} {n(r)} 0 0 1 {n(-r)} {n(r)}"
                f"h{n(-(w - 2 * r))}a{n(r)} {n(r)} 0 0 1 {n(-r)} {n(-r)}v{n(-(h - 2 * r))}a{n(r)} {n(r)} 0 0 1 {n(r)} {n(-r)}Z")
    raise ValueError(tag)


icons = {k: "|".join(to_d(t, a) for t, a in v) for k, v in sorted(nodes.items())}
(SKILL / "template/lucide.js").write_text(
    f"/* Lucide {version} 图标（ISC 许可，见 LICENSE-THIRD-PARTY.md）。由 tools/build_icons.py 生成，不要手改。\n"
    " * 每个图标是 24×24 格子里的几段 SVG 路径（用 | 隔开：每段单独起笔，小写 m 开头的段不能拼在一起），icons.js 把它描成霓虹线条。*/\n"
    "window.LUCIDE=" + json.dumps(icons, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
idx_path = SKILL / "scripts/icon_index.json"
old = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
idx = {"_": f"Lucide {version}：name → 英文标签；zh 是中文常用词 → 图标名（手写，可以加）", "zh": old.get("zh", {}),
       "tags": {k: tags.get(k, []) for k in sorted(nodes)}}
idx_path.write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(len(icons), "个图标；lucide.js", (SKILL / "template/lucide.js").stat().st_size // 1024, "KB")
