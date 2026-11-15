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
}
# 字幕里允许的字：汉字、字母、数字、空格和少数数字符号；其余标点一律不许（字幕不带标点）
SUB_OK = re.compile(r"^[一-鿿㐀-䶿A-Za-z0-9 %+×¥$/.]+$")
CONTACT = r"微信|vx|VX|加我|私信我|联系方式|电话|二维码|QQ|扣扣|wx号|链接在评论"
PROMISE = r"月入|日入|年入|稳赚|躺赚|包赚|保证赚|一定赚|回本|暴富|财务自由|零风险|稳挣|零成本|零门槛|不用本钱|不要本钱|不花一分钱"
INTERNAL = r"不含联系方式|访谈|brief|作者本人账目|SOP|skill|DeepSeek|Claude|提示词|分镜|示例数据来自"
ABSOLUTE = r"最好|最强|第一|唯一|100%|绝对|永远"
NUM = re.compile(r"\d")


def width(s):   # 估算一行字幕的宽度（一个汉字 = 1）
    return sum(1 if "㐀" <= ch <= "鿿" else 0.3 if ch == " " else 0.58 for ch in s)


def strings(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for v in o.values(): yield from strings(v)
    elif isinstance(o, list):
        for v in o: yield from strings(v)


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    film = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    brief = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else {}
    err, warn = [], []
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
        if not ls[0].get("shot"): err.append(f"{tag} 第一句必须带 shot（每章开一个新镜）")
        for ln in ls:
            n = len(lines) + 1
            if ln.get("shot"): shots.append({"shot": ln["shot"], "lines": [], "tag": f"第{n}句起的镜"})
            if shots: shots[-1]["lines"].append(ln)
            lines.append(ln)
            t = str(ln.get("text", "")).strip()
            if not t: err.append(f"第{n}句 没有字"); continue
            if not SUB_OK.match(t): err.append(f"第{n}句「{t}」有标点或怪字符（字幕不带标点，用空格断开）")
            if width(t) > 16: err.append(f"第{n}句「{t}」太长（约 {width(t):.1f} 字，上限 16，一眼读不完）")
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
        if ty == "fork" and d.get("pick") is not None and not (0 <= int(d["pick"]) < len(d.get("paths") or [])): err.append(f"{tag} pick 超出 paths 范围")
        if ty == "timeline" and d.get("breakAt") is not None and not (0 <= int(d["breakAt"]) < len(d.get("nodes") or []) - 1): err.append(f"{tag} breakAt 要小于节点数 - 1")
        if ty == "timeline" and d.get("breakStep") is not None and int(d["breakStep"]) >= len(s["lines"]): err.append(f"{tag} breakStep={d['breakStep']} 但这一镜只有 {len(s['lines'])} 句，裂不到")
        notes = [d.get("note")] + [ln.get("note") for ln in s["lines"]]
        has_num = any(NUM.search(x) for x in strings({k: v for k, v in d.items() if k not in ("type", "note", "breakAt", "breakStep", "pick", "max")})) or any(NUM.search(str(ln.get("text", ""))) for ln in s["lines"])
        if has_num and ty not in ("title", "statement", "steps") and not any(notes):
            err.append(f"{tag}（{ty}）屏上有数字，但没有 note 写出处（真实来源 / 示例 / 示意）")
        if brief.get("example") and has_num and any(notes) and not any(n and re.search("示例|示意", n) for n in notes):
            err.append(f"{tag} brief 标了 example（数字不是真实数据），note 必须写「示例」或「示意」")
    every = list(strings(film)) + [str(ln.get("text", "")) for ln in lines]
    for x in every:
        for name, pat, is_err in (("联系方式", CONTACT, True), ("收入承诺", PROMISE, True), ("内部用语", INTERNAL, True), ("绝对化用语", ABSOLUTE, False)):
            m = re.search(pat, x)
            if m: (err if is_err else warn).append(f"屏上出现{name}「{m.group(0)}」：{x}")
    for w in brief.get("banned") or []:
        if any(w in x for x in every): err.append(f"出现了 brief 里禁止的说法「{w}」")
    n = len(lines)
    if brief.get("seconds"):
        want = round(brief["seconds"] / bar)
        if abs(n - want) > 1: err.append(f"{brief['seconds']} 秒 @ {bpm} BPM 应该是 {want} 句（一句一小节 {bar:.2f} 秒），现在 {n} 句")
    if shots and shots[0]["shot"].get("type") not in ("title", "statement", "timeline", "number", "compare"): warn.append("开头第一镜不是钩子类（title / statement / timeline / number / compare），确认前 3 秒能让人停下")
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
