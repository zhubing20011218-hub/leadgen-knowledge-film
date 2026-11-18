# -*- coding: utf-8 -*-
"""检查自由画面（shot.type = "draw"）。check_film.py 调用；排版算法和 template/draw.js 是同一套，两边改一起改。
查：字段写对没有、图标有没有、每样东西放不放得下（出界 / 互相压住 / 字太长）、画面是不是太空、
每句有没有东西在动（没有就是停顿句）、屏上有哪些数（"字幕说的数画面上要有"）。"""
import math, re
from find_icon import ALL as ICON_NAMES, suggest

W, X0 = 1080, 96
CW, ZT, ZB = W - 2 * X0, 470, 1390
ZH = ZB - ZT
TEXT = {"s": 40, "m": 58, "l": 86, "xl": 140}
DEF = {"icon": 0.26, "phone": 0.46, "box": 0.76, "crowd": 0.86, "bar": 0.80}
ROW, TITLE, PAD = 66, 78, 44
KINDS = {"icon", "text", "num", "box", "phone", "crowd", "bar", "arrow", "line"}
THINGS = {"icon", "box", "phone", "crowd", "bar"}   # 认得出的东西；只有字和数的画面换成 statement / number
ACTS = {"strike", "cross", "check", "flash", "dim", "hide", "move", "grow", "count", "fill", "swap", "color", "mark", "shake"}
COLORS = {"main", "alt", "white", "dim", "red", "green", "gold"}
NEED = {"icon": ["icon"], "text": ["text"], "num": ["value"], "box": [], "phone": [], "crowd": ["n"], "bar": ["value"], "arrow": ["from", "to"], "line": ["from", "to"]}
ACT_NEED = {"move": ["x", "y"], "count": ["to"], "fill": ["to"], "swap": ["text"], "color": ["color"], "mark": ["to"]}
HIDE_KEYS = {"id", "kind", "x", "y", "size", "w", "at", "beat", "icon", "color", "do", "s", "from", "dash", "chat", "live"}   # 不上屏的字段


def cjk_w(s, size):
    return sum((1 if "㐀" <= ch <= "鿿" else 0.3 if ch == " " else 0.6) * size for ch in str(s))


def fmt(v):
    try: n = float(v)
    except (TypeError, ValueError): return str(v)
    return f"{n:,.{len(str(v).split('.')[1]) if '.' in str(v) else 0}f}"


def auto_layout(items):
    free = [it for it in items if it.get("kind") not in ("arrow", "line") and (it.get("x") is None or it.get("y") is None)]
    n = len(free)
    if not n: return
    cols = n if n <= 3 else 2 if n == 4 else 3; rows = -(-n // cols)
    for i, it in enumerate(free):
        r = i // cols; in_row = n - r * cols if r == rows - 1 else cols; c = i - r * cols
        if it.get("x") is None: it["x"] = (c + 0.5 + (cols - in_row) / 2) / cols
        if it.get("y") is None: it["y"] = (r + 0.5) / rows


def crowd_grid(it, w):
    n = max(1, min(100, round(float(it.get("n") or 10)))); cols = min(n, max(1, math.ceil(math.sqrt(n * 1.6))))
    return n, cols, -(-n // cols), w / cols


def size_of(it):
    """(宽, 高) 像素；和 draw.js 的 boxOf 一致"""
    k = it.get("kind")
    if k == "icon":
        s = float(it.get("size") or DEF["icon"]) * CW
        return max(s, cjk_w(it.get("label", ""), 40)), s + (62 if it.get("label") else 0)
    if k == "text":
        z = TEXT.get(it.get("size"), TEXT["m"]); return min(CW, cjk_w(it.get("text", ""), z)), z * 1.25
    if k == "num":   # 下面那行 label 只往下伸（draw.js：label 在 size × 0.62 + 10 处，36 号字）
        z = TEXT.get(it.get("size"), TEXT["xl"]); s = f"{it.get('prefix', '')}{fmt(it.get('value'))}{it.get('suffix', '')}"
        return min(CW, cjk_w(s, z)), z * 1.15 + (z * 0.07 + 40 if it.get("label") else 0)
    if k == "box":
        n = len(it.get("rows") or []); return float(it.get("w") or DEF["box"]) * CW, PAD + (TITLE if it.get("title") else 0) + n * ROW + (8 if n else 0)
    if k == "phone":
        w = float(it.get("size") or DEF["phone"]) * CW; return w, w * 1.95
    if k == "crowd":
        w = float(it.get("w") or DEF["crowd"]) * CW; n, cols, rows, cell = crowd_grid(it, w); return w, rows * cell
    if k == "bar":
        return float(it.get("w") or DEF["bar"]) * CW, 112 if it.get("label") else 50
    return 0, 0


def rect(it, x=None, y=None):
    w, h = size_of(it); cx = X0 + float(it["x"] if x is None else x) * CW; cy = ZT + float(it["y"] if y is None else y) * ZH
    if it.get("kind") == "num":   # 数字以自己为中心，label 挂在下面：上半截短、下半截长
        z = TEXT.get(it.get("size"), TEXT["xl"]); top = z * 0.575
        return cx - w / 2, cy - top, cx + w / 2, cy - top + h
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def num_on(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def check(d, span, tag, err, warn, stamp=None):
    """返回 (这一镜哪几句有东西在动, 屏上的数)"""
    items = [dict(x) for x in d.get("items") or [] if isinstance(x, dict)]
    acts = [x for x in d.get("acts") or [] if isinstance(x, dict)]
    shown, moving = set(), set()
    if not 1 <= len(items) <= 10: err.append(f"{tag}（draw）items 要 1–10 样东西，现在 {len(items)} 样：东西多了观众看不过来，一镜只演一件事")
    if len(acts) > 12: err.append(f"{tag}（draw）acts 有 {len(acts)} 个：一镜最多 12 个动作，一句最多三四个")
    ids = {}
    for i, it in enumerate(items):
        k, nm = it.get("kind"), f"items[{i}]{('「' + str(it.get('id')) + '」') if it.get('id') else ''}"
        it["_nm"] = nm
        if k not in KINDS: err.append(f"{tag}（draw）{nm} 的 kind「{k}」不认识，只能是 {' / '.join(sorted(KINDS))}"); it["kind"] = None; continue
        for f in NEED[k]:
            if it.get(f) in (None, "", []): err.append(f"{tag}（draw）{nm}（{k}）缺 {f}")
        if it.get("id"): ids[str(it["id"])] = it
        a = it.get("at", 0)
        if not isinstance(a, int) or not 0 <= a < span: err.append(f"{tag}（draw）{nm} 的 at={a}：这一镜只有 {span} 句，at 写 0–{span - 1}（第几句出场，从 0 数）"); it["at"] = 0
        if it.get("beat") is not None and it["beat"] not in (1, 2, 3, 4): err.append(f"{tag}（draw）{nm} 的 beat 只能是 1–4"); it["beat"] = 1
        if it.get("color") is not None and it["color"] not in COLORS: err.append(f"{tag}（draw）{nm} 的 color 只能是 {' / '.join(sorted(COLORS))}（main = 这章的颜色）")
        for f in ("x", "y"):
            if it.get(f) is not None and not (isinstance(it[f], (int, float)) and 0 <= it[f] <= 1): err.append(f"{tag}（draw）{nm} 的 {f}={it[f]}：x、y 是内容区里的比例，0–1"); it[f] = 0.5
        for f, lo, hi in (("size", 0.08, 0.95), ("w", 0.2, 1.0)):
            if f == "size" and k in ("text", "num"): continue   # 字的 size 是 s / m / l / xl
            if it.get(f) is not None and not (isinstance(it[f], (int, float)) and lo <= it[f] <= hi):
                err.append(f"{tag}（draw）{nm} 的 {f}={it[f]}：是内容区宽度的比例，{lo}–{hi}"); it.pop(f)
        if k in ("text", "num") and it.get("size") is not None and it["size"] not in TEXT: err.append(f"{tag}（draw）{nm} 的 size 只能是 s / m / l / xl（字号）"); it.pop("size")
        for f in ("icon",):
            if it.get(f) and it[f] not in ICON_NAMES: err.append(f"{tag}（draw）{nm} 的图标「{it[f]}」没有。像的有：{' '.join(suggest(it[f])) or '（没有，换个更具体的东西）'}。查图标：python3 scripts/find_icon.py <中文或英文词>")
        L = lambda s, n: len(str(s).replace(" ", "")) > n
        if k == "text" and L(it.get("text", ""), 10): err.append(f"{tag}（draw）{nm} 的字「{it.get('text')}」超过 10 个字：画面上的字是标签，不是句子（句子写在字幕里）")
        if it.get("label") and L(it["label"], 8): err.append(f"{tag}（draw）{nm} 的 label「{it['label']}」超过 8 个字")
        if it.get("title") and L(it["title"], 8): err.append(f"{tag}（draw）{nm} 的 title「{it['title']}」超过 8 个字")
        rows = it.get("rows") or []
        if k in ("box", "phone"):
            if len(rows) > 5: err.append(f"{tag}（draw）{nm} 的 rows 有 {len(rows)} 行，最多 5 行（一行一拍写出来）")
            for r in rows:
                t = r.get("me", r.get("them", r.get("text", ""))) if isinstance(r, dict) else r
                if L(t, 12): err.append(f"{tag}（draw）{nm} 的一行「{t}」超过 12 个字")
            if k == "box" and not it.get("title") and not rows: err.append(f"{tag}（draw）{nm}（box）是空卡片：写 title 或 rows")
        if k == "num" and str(it.get("prefix", "")).strip() in ("¥", "$", "￥") and "元" in str(it.get("suffix", "")): err.append(f"{tag}（draw）{nm} 前面写了 ¥、后面又写「元」，屏上会是「¥8,000 元」：留一个（删掉 suffix 的「元」）")
        if k == "num" and num_on(it.get("value")) is None: err.append(f"{tag}（draw）{nm}（num）的 value 要写数字（单位写进 prefix / suffix）")
        if k == "bar" and not (isinstance(it.get("value"), (int, float)) and 0 <= it["value"] <= 1): err.append(f"{tag}（draw）{nm}（bar）的 value 是填满的比例 0–1，要显示的数写在 text 里（比如 \"value\": 0.3, \"text\": \"30%\"）")
        if k == "bar":   # 名字在左上、显示的字在右上，两个挤在一行（11-18：「孩子午睡 2 小时」和「一半」撞在一起）
            texts = [str(it.get("text") or "")] + [str(a.get("text") or "") for a in acts if a.get("do") == "fill" and str(a.get("id")) == str(it.get("id"))]
            need = cjk_w(it.get("label") or "", 40) + max(cjk_w(t, 44) for t in texts) + 40; have = float(it.get("w") or DEF["bar"]) * CW
            if it.get("label") and need > have: err.append(f"{tag}（draw）{nm}（bar）的名字「{it['label']}」和右边的字「{'/'.join(t for t in texts if t)}」挤在一行放不下：w 改成 {min(1.0, need / CW + 0.02):.2f}，或者名字缩到 4 个字以内")
        if k == "crowd" and not (isinstance(it.get("n"), int) and 2 <= it["n"] <= 100): err.append(f"{tag}（draw）{nm}（crowd）的 n 是一共几个，2–100")
    for i, it in enumerate(items):
        if it.get("kind") in ("arrow", "line"):
            for f in ("from", "to"):
                v = it.get(f)
                if isinstance(v, str) and v not in ids: err.append(f"{tag}（draw）{it['_nm']} 的 {f}「{v}」找不到：写一样东西的 id，或者一个点 [x, y]")
                elif isinstance(v, list) and not (len(v) == 2 and all(isinstance(z, (int, float)) and 0 <= z <= 1 for z in v)): err.append(f"{tag}（draw）{it['_nm']} 的 {f} 写成 [x, y]（0–1）")
    if items and not any(it.get("kind") in THINGS for it in items):
        err.append(f"{tag}（draw）屏上只有字和数，没有一样认得出的东西：自由画面要画东西本身（icon / phone / box / crowd / bar）。只想放大字就用 statement，只有一个数在变就用 number")
    T = lambda a, b: (a or 0) * 4 + ((b or 1) - 1)   # 第几拍（从这一镜开头数）
    for j, a in enumerate(acts):
        nm = f"acts[{j}]"
        if a.get("do") not in ACTS: err.append(f"{tag}（draw）{nm} 的 do「{a.get('do')}」不认识，只能是 {' / '.join(sorted(ACTS))}"); continue
        if str(a.get("id")) not in ids: err.append(f"{tag}（draw）{nm} 的 id「{a.get('id')}」找不到：动作要对着一样有 id 的东西"); continue
        for f in ACT_NEED.get(a["do"], []):
            if a.get(f) is None: err.append(f"{tag}（draw）{nm}（{a['do']}）缺 {f}")
        at = a.get("at", 0)
        if not isinstance(at, int) or not 0 <= at < span: err.append(f"{tag}（draw）{nm} 的 at={at}：这一镜只有 {span} 句，at 写 0–{span - 1}"); continue
        if a.get("beat") is not None and a["beat"] not in (1, 2, 3, 4): err.append(f"{tag}（draw）{nm} 的 beat 只能是 1–4"); continue
        it = ids[str(a["id"])]
        if T(at, a.get("beat")) <= T(it.get("at"), it.get("beat")): err.append(f"{tag}（draw）{nm} 对「{a['id']}」的 {a['do']} 不晚于它出场：动作要排在它出来之后的某一拍")
        if a["do"] == "fill" and not (isinstance(a.get("to"), (int, float)) and 0 <= a["to"] <= 1): err.append(f"{tag}（draw）{nm}（fill）的 to 是比例 0–1，显示的数写在 text")
        if a["do"] == "count" and num_on(a.get("to")) is None: err.append(f"{tag}（draw）{nm}（count）的 to 要写数字")
        if a["do"] in ("move",):
            for f in ("x", "y"):
                if not (isinstance(a.get(f), (int, float)) and 0 <= a[f] <= 1): err.append(f"{tag}（draw）{nm}（move）的 {f} 是 0–1 的比例")
        if a["do"] == "swap" and len(str(a.get("text", "")).replace(" ", "")) > 10: err.append(f"{tag}（draw）{nm}（swap）的字超过 10 个")
        moving.add(at)
    auto_layout(items)
    for it in items:   # 出场也算这句在动
        if it.get("kind"): moving.add(it["at"] if isinstance(it.get("at"), int) else 0)
    # 放不放得下
    solid = [it for it in items if it.get("kind") in KINDS - {"arrow", "line"}]
    boxes = {}
    for it in solid:
        x0, y0, x1, y1 = rect(it); boxes[id(it)] = (x0, y0, x1, y1)
        out = []
        if x0 < X0 - 30: out.append(f"左边出界 {X0 - x0:.0f} 像素")
        if x1 > W - X0 + 30: out.append(f"右边出界 {x1 - W + X0:.0f} 像素")
        if y0 < ZT - 30: out.append(f"顶上压到关键词 {ZT - y0:.0f} 像素")
        if y1 > ZB + 30: out.append(f"底下压到字幕 {y1 - ZB:.0f} 像素")
        if out:
            w, h = size_of(it); xs = (w / 2 / CW, 1 - w / 2 / CW); ys = (h / 2 / ZH, 1 - h / 2 / ZH)
            fix = (f"x 放在 {xs[0]:.2f}–{xs[1]:.2f}、y 放在 {ys[0]:.2f}–{ys[1]:.2f} 之间" if xs[0] <= xs[1] and ys[0] <= ys[1] else "它本身就比内容区大，调小 size / w，或删几行") + ("；数字 / 字太宽就把 size 改成 l 或 m" if it["kind"] in ("num", "text") else "")
            err.append(f"{tag}（draw）{it['_nm']}（{it['kind']}）{('、'.join(out))}：{fix}")
        for a in acts:
            if a.get("do") == "move" and str(a.get("id")) == str(it.get("id")) and isinstance(a.get("x"), (int, float)) and isinstance(a.get("y"), (int, float)):
                mx0, my0, mx1, my1 = rect(it, a["x"], a["y"])
                if mx0 < X0 - 30 or mx1 > W - X0 + 30 or my0 < ZT - 30 or my1 > ZB + 30: err.append(f"{tag}（draw）{it['_nm']} 挪到 ({a['x']}, {a['y']}) 以后出界了")
    def gone(it):   # 什么时候被收走（hide），之后不算压住
        hs = [T(a.get("at"), a.get("beat")) for a in acts if a.get("do") == "hide" and str(a.get("id")) == str(it.get("id"))]
        return min(hs) if hs else 10 ** 6
    together = lambda a, b: not (T(b.get("at"), b.get("beat")) >= gone(a) or T(a.get("at"), a.get("beat")) >= gone(b))
    def free_spot(it):   # 给弱模型一个能直接抄的位置：离原位最近、不出界、不压任何同时在屏上的东西
        others = [boxes[id(o)] for o in solid if o is not it and together(o, it)]
        best = None
        for gx in range(2, 19):
            for gy in range(2, 19):
                x, y = gx / 20, gy / 20; r = rect(it, x, y)
                if r[0] < X0 - 10 or r[2] > W - X0 + 10 or r[1] < ZT - 10 or r[3] > ZB + 10: continue
                if any(min(r[2], o[2]) - max(r[0], o[0]) > 0 and min(r[3], o[3]) - max(r[1], o[1]) > 0 for o in others): continue
                dist = (x - float(it["x"])) ** 2 + (y - float(it["y"])) ** 2
                if best is None or dist < best[0]: best = (dist, x, y)
        return best and (best[1], best[2])
    peak = 0   # 同一时刻屏上最多几样东西
    for at in range(span):
        for bt in range(1, 5):
            now = [it for it in solid if T(it.get("at"), it.get("beat")) <= T(at, bt) < gone(it)]
            peak = max(peak, len(now))
    if peak > 6: err.append(f"{tag}（draw）同一时刻屏上有 {peak} 样东西，最多 5–6 样（观众一眼看不过来，也摆不开）：前面句子的东西用完就收走（acts 里 \"do\": \"hide\"，at 写下一句），或者这一章拆成两章")
    elif peak == 6: warn.append(f"{tag}（draw）同一时刻屏上有 6 样东西，偏多：用完的收走（hide）会更清楚")
    for i, a in enumerate(solid):
        for b in solid[i + 1:]:
            if not together(a, b): continue
            A, B = boxes[id(a)], boxes[id(b)]
            ix = max(0, min(A[2], B[2]) - max(A[0], B[0])); iy = max(0, min(A[3], B[3]) - max(A[1], B[1])); inter = ix * iy
            sa, sb = (A[2] - A[0]) * (A[3] - A[1]), (B[2] - B[0]) * (B[3] - B[1])
            if not inter or not min(sa, sb): continue
            inside = inter >= 0.92 * min(sa, sb)   # 一样东西整个放在另一样上面（卡片上的字、手机上的勾），是故意的
            words = {"text", "num"} & {a.get("kind"), b.get("kind")}   # 字压到别的东西的边上就看着脏（11-18：「12 小时」压着手机的边框），不等到压住一成多
            if not inside and (inter / min(sa, sb) > 0.12 or (words and ix > 12 and iy > 12)):
                late = b if T(b.get("at"), b.get("beat")) >= T(a.get("at"), a.get("beat")) else a
                spot = free_spot(late)
                how = (f"最小改法：把 {late['_nm']} 挪到 \"x\": {spot[0]:.2f}, \"y\": {spot[1]:.2f}（那里空着）" if spot
                       else "没有空地方了：调小 size / w（数字 / 字写 l 或 m），或者把前面用完的收走（hide）")
                err.append(f"{tag}（draw）{a['_nm']}（{a['kind']}）和 {b['_nm']}（{b['kind']}）压在一起了（重叠 {inter / min(sa, sb):.0%}）。{how}")
    for it in items:   # 连线标签太宽，夹不进两样东西中间
        if it.get("kind") in ("arrow", "line") and isinstance(it.get("from"), str) and isinstance(it.get("to"), str) and it["from"] in ids and it["to"] in ids:
            A, B = boxes.get(id(ids[it["from"]])), boxes.get(id(ids[it["to"]]))
            if A and B:
                gap = max(B[0] - A[2], A[0] - B[2], B[1] - A[3], A[1] - B[3])
                if gap < 70: err.append(f"{tag}（draw）{it['_nm']} 连着的两样东西几乎挨着（只隔 {max(gap, 0):.0f} 像素），线{('和标签「' + str(it['label']) + '」') if it.get('label') else ''}都看不见：把两样东西拉开（x 差 0.4 以上），或者不要这条线")
    if solid:
        ux0 = min(b[0] for b in boxes.values()); ux1 = max(b[2] for b in boxes.values())
        uy0 = min(b[1] for b in boxes.values()); uy1 = max(b[3] for b in boxes.values())
        if (uy1 - uy0) < 0.45 * ZH and (ux1 - ux0) < 0.75 * CW: warn.append(f"{tag}（draw）画面太小：所有东西加起来只占内容区 {(ux1 - ux0) / CW:.0%} 宽、{(uy1 - uy0) / ZH:.0%} 高。主体放大（size / w），或者摆开占满（标杆样片主体占画面六七成）")
        elif (uy1 - uy0) < 0.45 * ZH: warn.append(f"{tag}（draw）东西都挤在一条里（只占内容区 {(uy1 - uy0) / ZH:.0%} 高）：上下也摆开（一排在 y 0.3，一排在 y 0.75），或者主体放大")
        if stamp:   # 引擎会把章放到右下 → 左下 → 右上 → 左上 → 正中下第一个空着的地方（draw.js 的 stampSpot），都占满了才提醒
            free = False
            for fx, sy in ((0.64, 1350), (0.36, 1350), (0.64, 560), (0.36, 560), (0.5, 1350)):
                r = (W * fx - 190, sy - 100, W * fx + 190, sy + 100)
                if not any(min(r[2], b[2]) > max(r[0], b[0]) and min(r[3], b[3]) > max(r[1], b[1]) for b in boxes.values()): free = True; break
            if not free: warn.append(f"{tag}（draw）盖章找不到空地方（四个角和正中下都有东西），会压住东西：东西摆紧凑一点，留出一个角")
    # 屏上的数
    def leaves(o):
        if isinstance(o, bool): return
        if isinstance(o, (int, float, str)): yield o
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in HIDE_KEYS and not k.startswith("_"): yield from leaves(v)
        elif isinstance(o, list):
            for v in o: yield from leaves(v)
    for it in items:
        if it.get("kind") == "bar": it = {k: v for k, v in it.items() if k != "value"}   # 进度条的 value 是比例，不上屏
        for x in leaves(it): shown.add(x)
        if it.get("kind") == "crowd": shown.add(it.get("n")); shown.add(it.get("mark"))
    for a in acts:
        if a.get("do") in ("count", "mark"): shown.add(a.get("to"))
        if a.get("do") in ("swap", "fill") and a.get("text") is not None: shown.add(a.get("text"))
    return moving, shown


def brief_walk_skip():
    """查"数是不是编的"时跳过的字段（坐标、大小、第几句第几拍都不是屏上的数）"""
    return HIDE_KEYS - {"from"}
