# -*- coding: utf-8 -*-
"""检查 film.json：python3 scripts/check_film.py <工程>/film.json [brief.json]
有错误退出码 1（不许渲染）；警告只提醒。规则的来由写在 references/05-检查表.md。"""
import json, re, sys
from pathlib import Path

COLORS = {"red", "amber", "violet", "cyan", "green", "pink", "blue"}
TYPES = {   # 件名: (必填字段, {列表字段: (最少, 最多)})
    "title": (["big"], {}),
    "statement": (["big"], {}),
    "number": (["values"], {"values": (1, 4)}),
    "bars": (["rows"], {"rows": (2, 6)}),
    "ring": (["value"], {"rows": (0, 5)}),
    "timeline": (["nodes"], {"nodes": (2, 5)}),
    "fork": (["paths"], {"paths": (2, 4)}),
    "compare": (["left", "right"], {}),
    "checklist": (["rows"], {"rows": (1, 6)}),
    "steps": (["rows"], {"rows": (1, 5)}),
    "cycle": (["nodes"], {"nodes": (3, 6)}),
    "cards": (["items"], {"items": (2, 6)}),
    "object": (["icon"], {}),
    "flow": (["from", "to"], {}),
}
ICONS = set("phone laptop resume person people bed desk factory box ship plane globe money coins chartup chartdown clock calendar cart store chat ai video house briefcase".split())   # 和 template/icons.js 一致
# 字幕里允许的字：汉字、字母、数字、空格和少数数字符号；其余标点一律不许（字幕不带标点）
SUB_OK = re.compile(r"^[一-鿿㐀-䶿A-Za-z0-9 %+×¥$/.]+$")
CONTACT = r"微信|vx|VX|加我|私信我|联系方式|电话|二维码|QQ|扣扣|wx号|链接在评论|扣 ?1|扣 ?666|领资料|领取|免费送|私我"   # 后几个是诱导互动 / 导流话术，平台会限流
PROMISE = r"月入|日入|年入|稳赚|躺赚|包赚|保证赚|一定赚|回本|暴富|财务自由|零风险|稳挣|零成本|零门槛|不用本钱|不要本钱|不花一分钱"
INTERNAL = r"不含联系方式|访谈|\bbrief\b|作者本人账目|SOP|skill|DeepSeek|Claude|提示词|分镜|示例数据来自"
ABSOLUTE = r"最好|最强|第一|唯一|100%|绝对|永远"
NUM = re.compile(r"\d")


CN = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
UNIT = {"十": 10, "百": 100, "千": 1000}


def cn2num(t):   # 两百 → 200，两万 → 20000，十年 → 10，三千五 → 3500（口语的"三千五"按 3500 算）
    total, sec, num, last = 0, 0, 0, 1
    for ch in t:
        if ch in CN: num = CN[ch]
        elif ch in UNIT: sec += (num or 1) * UNIT[ch]; last = UNIT[ch]; num = 0
        elif ch == "万": total += (sec + num) * 10000; sec = num = 0; last = 1000
    if num and last >= 100: num *= last // 10
    return total + sec + num


def numbers_in(text):
    out = set()
    for m in re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")):
        v = float(m); out.add(v)
    for m in re.finditer(r"百分之([零一二两三四五六七八九十]+)", text):
        v = cn2num(m.group(1))
        if v: out.add(float(v))
    text = re.sub(r"百分之[零一二两三四五六七八九十]+", " ", text)
    for m in re.finditer(r"[零一二两三四五六七八九十百千万]{2,}|[十百千万]", text):
        if m.start() and text[m.start() - 1] in "几数上成好": continue   # 几千、上万、数十：模糊说法，不是具体的数
        if text[m.end():m.end() + 2] == "分之" or text[m.start():m.start() + 3] == "百分之": # 百分之十八：只认后面的十八
            continue
        v = cn2num(m.group(0))
        if v: out.add(float(v))
    return out


def derive(nums):
    """brief 里的数做一两步加减乘除能得到的数（利润 = 售价 − 进价 − 运费、差几倍……），算出来的不算编。"""
    ns = sorted(n for n in nums if n > 0)[:20]; out = {}
    g = lambda v: round(v, 2)
    for a in ns:
        for b in ns:
            if a == b: continue
            for v, f in ((a + b, f"{a:g}+{b:g}"), (a - b, f"{a:g}−{b:g}"), (a * b, f"{a:g}×{b:g}"), (a / b, f"{a:g}÷{b:g}")):
                if v > 0: out.setdefault(g(v), f)
            for c in ns:
                if c not in (a, b) and a - b - c > 0: out.setdefault(g(a - b - c), f"{a:g}−{b:g}−{c:g}")
    for a in ns:
        out.setdefault(g(a * 12), f"{a:g}×12"); out.setdefault(g(a / 100), f"{a:g}%")
    return out


# 每种件最多能"变"几次：一镜的句子比这多，多出来的句子画面不动
def capacity(d):
    ty = d.get("type"); L = lambda k: len(d.get(k) or [])
    return {"title": 1, "statement": 1, "number": max(1, L("values")), "bars": L("rows"), "ring": 1 + L("rows"),
            "timeline": 2 if d.get("breakAt") is not None else 1, "fork": 1 if d.get("focus") is not None else max(2, L("paths")), "compare": 2,
            "checklist": L("rows"), "steps": L("rows"), "cycle": L("nodes"), "cards": L("items"), "object": 1, "flow": 2}.get(ty, 1)


def icon_fields(o, path="shot"):   # 找出所有 icon 字段
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "icon": yield f"{path}.icon", v
            else: yield from icon_fields(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from icon_fields(v, f"{path}[{i}]")


def width(s):   # 估算一行字幕的宽度（一个汉字 = 1）
    return sum(1 if "㐀" <= ch <= "鿿" else 0.3 if ch == " " else 0.58 for ch in s)


HIDDEN = {"icon", "type", "color"}   # 这些字段不上屏（图标名、件名、颜色名），不拿来查屏上用语


def strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in HIDDEN: yield from strings(v)
    elif isinstance(o, list):
        for v in o: yield from strings(v)


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    film = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    brief = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else {}
    err, warn = [], []
    brief_nums = numbers_in(json.dumps({k: brief.get(k) for k in ("pain", "proof", "audience")}, ensure_ascii=False)) if brief else None
    derived = derive(brief_nums) if brief_nums else {}
    bpm = film.get("bpm", 112); bar = 60 / bpm * 4
    chs = film.get("chapters") or []
    if not chs: err.append("没有 chapters")
    lines, shots = [], []
    for ci, ch in enumerate(chs, 1):
        tag = f"第{ci}章「{ch.get('name', '')}」"
        if not ch.get("name"): err.append(f"{tag} 没有 name")
        if ch.get("color") not in COLORS: err.append(f"{tag} color 只能是 {sorted(COLORS)}")
        if ci > 1 and ch.get("color") == chs[ci - 2].get("color"): err.append(f"{tag} 和上一章同一个颜色「{ch.get('color')}」，相邻两章要换色")
        if re.search(r"[\u4e00-\u9fff]", str(ch.get("en", ""))): err.append(f"{tag} en 只能写英文")
        ls = ch.get("lines") or []
        if not ls: err.append(f"{tag} 没有字幕"); continue
        if not ls[0].get("shot"): err.append(f"{tag} 第一句必须带 shot（每章开一个新镜），比如 \"shot\": {{\"type\": \"statement\", \"big\": \"两到六个字\"}}")
        for ln in ls:
            n = len(lines) + 1
            if ln.get("shot"): shots.append({"shot": ln["shot"], "lines": [], "tag": f"第{n}句起的镜"})
            if shots: shots[-1]["lines"].append(ln)
            lines.append(ln)
            t = str(ln.get("text", "")).strip()
            if not t: err.append(f"第{n}句 没有字"); continue
            if not SUB_OK.match(t):
                fix = re.sub(r" +", " ", re.sub(r"[^\u4e00-\u9fff\u3400-\u4dbfA-Za-z0-9 %+×¥$/.]", " ", t)).strip()
                err.append(f"第{n}句「{t}」有标点或怪字符（字幕不带标点，用空格断开）。改成：「{fix}」")
            if width(t) > 16.5: err.append(f"第{n}句「{t}」太长（约 {width(t):.1f} 字，上限 16，一眼读不完）：删掉修饰词，或拆成两句（拆了句数会变，别的地方删一句）")
            for w in ln.get("hl") or []:
                if w not in t: err.append(f"第{n}句 高亮词「{w}」不在字幕里")
            if len(ln.get("hl") or []) > 2: warn.append(f"第{n}句 高亮超过 2 处，重点会散")
    for s in shots:
        d, tag = s["shot"], s["tag"]
        ty = d.get("type")
        if ty not in TYPES: err.append(f"{tag} type「{ty}」不认识，只能用 {sorted(TYPES)}"); continue
        need, lists = TYPES[ty]
        for f in need:
            if d.get(f) in (None, "", []): err.append(f"{tag}（{ty}）缺 {f}")
        for f, (lo, hi) in lists.items():
            v = d.get(f) or []
            if not (lo <= len(v) <= hi): err.append(f"{tag}（{ty}）{f} 要 {lo}–{hi} 个，现在 {len(v)} 个")
        if ty == "number" and len(d.get("values") or []) > len(s["lines"]) + 3: warn.append(f"{tag} number 的值比句子多太多，挤在一句里会看不清")
        if ty == "bars" and any(r.get("tag") and (len(str(r["tag"])) <= 2 or str(r["tag"]) in str(d.get("unit", ""))) for r in d.get("rows") or []): warn.append(f"{tag} bars 的 tag 像是单位（单位写在 unit 里，tag 写一句补充或留空）")
        if ty == "steps" and any(re.fullmatch(r"\s*0?\d+\s*", str(r.get("note", "x"))) for r in d.get("rows") or []): warn.append(f"{tag} steps 的 note 只写了编号，编号会自动画，note 留空或写一句补充")
        if ty == "fork" and d.get("focus") is not None and not (0 <= int(d["focus"]) < len(d.get("paths") or [])): err.append(f"{tag} focus 超出 paths 范围")
        if ty == "fork" and d.get("pick") is not None and not (0 <= int(d["pick"]) < len(d.get("paths") or [])): err.append(f"{tag} pick 超出 paths 范围")
        if ty == "timeline" and d.get("breakAt") is not None and not (0 <= int(d["breakAt"]) < len(d.get("nodes") or []) - 1): err.append(f"{tag} breakAt 要小于节点数 - 1")
        if ty == "timeline" and d.get("breakStep") is not None and int(d["breakStep"]) >= len(s["lines"]): err.append(f"{tag} breakStep={d['breakStep']} 但这一镜只有 {len(s['lines'])} 句，裂不到")
        for pth, v in [(p, v) for p, v in icon_fields(d)]:
            if v not in ICONS: err.append(f"{tag} {pth} 的图标「{v}」没有，只能用：{' '.join(sorted(ICONS))}")
        if ty == "object" and d.get("count") is not None and not (2 <= int(d["count"]) <= 60): err.append(f"{tag} object 的 count 要 2–60（一个就别写 count）")
        span, cap = len(s["lines"]), capacity(d)
        if span > cap:
            msg = f"{tag}（{ty}）有 {span} 句，但这个件只能变 {cap} 次：后面 {span - cap} 句画面不动。拆成两镜，或给它加条目（rows / values / nodes）"
            (err if span - cap >= 2 else warn).append(msg)
        if ty in ("steps", "checklist", "cards", "cycle"):
            k = len(d.get("rows") or d.get("items") or d.get("nodes") or [])
            for ln in s["lines"]:
                m = re.search(r"([0-9]+|[一二两三四五六七八九十]) ?(步|件事|条路)", str(ln.get("text", "")))   # "一条视频"的"条"是量词，不核对
                if m and int(cn2num(m.group(1)) if not m.group(1).isdigit() else m.group(1)) != k:
                    err.append(f"{tag} 字幕说「{m.group(0)}」，但画面只有 {k} 条：让两边对上（改字幕里的数，或补齐条目）")
        if ty == "bars" and len({str(r.get("value")) for r in d.get("rows") or []}) == 1 and len(d.get("rows") or []) > 1: err.append(f"{tag} bars 每条的值都一样，比不出大小：换成有差别的真实数，或者换件（checklist / steps）")
        notes = [d.get("note")] + [ln.get("note") for ln in s["lines"]]
        note_txt = " ".join(n for n in notes if n)
        if brief_nums is not None:
            shown = set()
            def walk(o, path):
                if isinstance(o, bool): return
                if isinstance(o, (int, float)): yield path, str(o)
                elif isinstance(o, str): yield path, o
                elif isinstance(o, dict):
                    for k, v in o.items():
                        if k not in ("type", "note", "breakAt", "breakStep", "pick", "max", "ok", "pct", "from"): yield from walk(v, f"{path}.{k}")
                elif isinstance(o, list):
                    for i, v in enumerate(o): yield from walk(v, f"{path}[{i}]")
            where = {}
            for pth, x in walk(d, "shot"):
                for v in numbers_in(x): where.setdefault(v, f"{pth}「{x}」")
            for j, ln in enumerate(s["lines"]):
                for v in numbers_in(str(ln.get("text", ""))): where.setdefault(v, f"这一镜第{j + 1}句字幕「{ln.get('text')}」")
            odd = sorted(v for v in where if v > 2 and v not in brief_nums and not (1900 <= v <= 2100))
            for v in [v for v in odd if v in derived]:
                warn.append(f"{tag} 数字 {v:g} 是从 brief 算出来的（{derived[v]}），放行")
            odd = [v for v in odd if v not in derived]
            if odd:
                nums = "、".join(f"{v:g}（在 {where[v]}）" for v in odd)
                if re.search("按.*算|来源", note_txt): warn.append(f"{tag} 数字 {nums} 不在 brief 里（note 写了怎么算的 / 来源，放行，自己再核对一遍）")
                elif ty == "timeline" and "示意" in note_txt: warn.append(f"{tag} 人生节点的数字 {nums} 是示意（放行）")
                else: err.append(f"{tag} 数字 {nums} 在 brief 里找不到：疑似编造。用 brief 里的数；从 brief 算出来的，note 写「按 … 算」；公开规则写「来源：…」；拿不出依据就别放数字（「示意」只给人生节点用）")
        has_num = any(NUM.search(x) for x in strings({k: v for k, v in d.items() if k not in ("type", "note", "breakAt", "breakStep", "pick", "max")})) or any(NUM.search(str(ln.get("text", ""))) for ln in s["lines"])
        if has_num and ty not in ("title", "statement", "steps") and not any(notes):
            err.append(f"{tag}（{ty}）屏上有数字，但没有 note 写出处（真实来源 / 示例 / 示意）")
        if brief.get("example") and has_num and any(notes) and not any(n and re.search("示例|示意", n) for n in notes):
            err.append(f"{tag} brief 标了 example（数字不是真实数据），note 必须写「示例」或「示意」")
    for a, b in zip(shots, shots[1:]):   # 连着几镜逐条讲同一组岔路：每镜的 paths 要一模一样，只改 focus
        da, db = a["shot"], b["shot"]
        if da.get("type") == db.get("type") == "fork" and da.get("focus") is not None and db.get("focus") is not None and da.get("paths") != db.get("paths"):
            warn.append(f"{b['tag']} 和上一镜是同一组岔路，但 paths 写得不一样（前后会对不上）：照抄上一镜的 paths，只改 focus")
    every = list(strings(film)) + [str(ln.get("text", "")) for ln in lines]
    for x in every:
        for name, pat, is_err in (("联系方式或诱导互动", CONTACT, True), ("收入承诺", PROMISE, True), ("内部用语", INTERNAL, True), ("绝对化用语", ABSOLUTE, False)):
            m = re.search(pat, x)
            if m: (err if is_err else warn).append(f"屏上出现{name}「{m.group(0)}」：{x}")
    for w in brief.get("banned") or []:
        if any(w in x for x in every): err.append(f"出现了 brief 里禁止的说法「{w}」")
    n = len(lines)
    if brief.get("seconds"):
        want = round(brief["seconds"] / bar)
        if abs(n - want) > 1:
            per = "，".join(f"「{c.get('name')}」{len(c.get('lines') or [])} 句" for c in chs)
            how = f"还差 {want - n} 句：挑一两章往后加句子（加在已有的镜后面，或开新镜）" if n < want else f"多了 {n - want} 句：删掉最弱的几句"
            err.append(f"{brief['seconds']} 秒 @ {bpm} BPM 要正好 {want} 句（一句一小节 {bar:.2f} 秒），现在 {n} 句。{how}。现在各章：{per}")
    if shots and shots[0]["shot"].get("type") not in ("title", "statement", "timeline", "number", "compare"): warn.append("开头第一镜不是钩子类（title / statement / timeline / number / compare），确认前 3 秒能让人停下")
    if len(lines) >= 8 and len(shots) > 0.75 * len(lines):
        warn.append(f"镜头换得太勤：{len(lines)} 句用了 {len(shots)} 镜。标杆样片是一章一个主画面撑 3–4 句、每句往上加一样东西；能合的合进同一镜（rows / values / nodes 多写几条）")
    plain = sum(1 for s in shots if s["shot"].get("type") == "statement")
    if shots and plain > len(shots) / 2: warn.append(f"{plain}/{len(shots)} 镜是纯文字 statement，画面太少")
    if not re.search("主页|合集|评论", "".join(every[-40:])): warn.append("结尾没有看到下一步（主页 / 合集 / 评论区）")
    dur = film.get("phase", 0) + n * bar
    print(f"{n} 句 · {len(shots)} 镜 · {len(chs)} 章 · {bpm} BPM · 一句 {bar:.3f} 秒 · 全片 {dur:.2f} 秒")
    for w in warn: print("⚠ ", w)
    for e in err: print("✗ ", e)
    print("通过" if not err else f"{len(err)} 个错误，改完再渲")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
