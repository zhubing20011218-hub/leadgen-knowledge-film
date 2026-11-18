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
    "ledger": (["rows"], {"rows": (2, 5)}),
    "ring": (["value"], {"rows": (0, 5)}),
    "timeline": (["nodes"], {"nodes": (2, 5)}),
    "fork": (["paths"], {"paths": (2, 5)}),
    "compare": (["left", "right"], {}),
    "checklist": (["rows"], {"rows": (1, 6)}),
    "steps": (["rows"], {"rows": (1, 5)}),
    "cycle": (["nodes"], {"nodes": (3, 6)}),
    "cards": (["items"], {"items": (2, 6)}),
    "object": (["icon"], {}),
    "flow": (["from", "to"], {}),
    "draw": (["items"], {}),   # 自由画面：template/draw.js，检查在 draw_check.py
}
import draw_check
from find_icon import ALL as ICONS, suggest as icon_suggest   # 自带 28 个 + Lucide 1500+ 个（template/lucide.js），所有件的 icon 都能用
# 字幕里允许的字：汉字、字母、数字、空格和少数数字符号；其余标点一律不许（字幕不带标点）
SUB_OK = re.compile(r"^[一-鿿㐀-䶿A-Za-z0-9 %+×¥$/.]+$")
CONTACT = r"微信|vx|VX|加我|私信我|联系方式|电话|二维码|QQ|扣扣|wx号|链接在评论|扣 ?1|扣 ?666|领资料|领取|免费送|私我"   # 后几个是诱导互动 / 导流话术，平台会限流
def pic_max(n): return (n + 1) // 2      # 画面数的目标：平均一个画面至少撑 2 句（标杆样片 3.5 句，上游规矩 2–5 句）。超了警告。和 ds_make.py 同一套
def pic_hard(n): return -(-n * 3 // 5)   # 超过句数的 60% 才报错（11-17 实测：卡死在目标线上，flash 会在拆和合之间来回摆）
def pause_max(n): return max(1, n // 5)  # 最多几句画面不动（停顿句：提问 / 结论）。上游实测约每五句一句
PROMISE = r"月入|日入|年入|稳赚|躺赚|包赚|保证赚|一定赚|回本|暴富|财务自由|零风险|稳挣|零成本|零门槛|不用本钱|不要本钱|不花一分钱"
INTERNAL = r"不含联系方式|访谈|\bbrief\b|作者本人账目|SOP|skill|DeepSeek|Claude|提示词|分镜|示例数据来自"
ABSOLUTE = r"最好|最强|第一(?![步条把个次章句天年件种层])|唯一|100%|绝对|永远"   # 「第一步」「第一把锁」是序数，不算
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
    text = text.replace(",", "")
    for m in re.findall(r"\d+(?:\.\d+)?", text):
        v = float(m); out.add(v)
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([万千亿])", text):   # 「12万」= 12 也 = 120000：字幕写 12万、画面写 120000 是同一个数（11-17 两边各报一个错，模型改不动）
        out.add(round(float(m.group(1)) * {"千": 1e3, "万": 1e4, "亿": 1e8}[m.group(2)], 2))
    text = re.sub(r"(\d)\s*[万千亿]", r"\1 ", text)   # 已经算过的单位，下面不再单独当成 10000
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


def loose_nums(text):   # 宽一点：单个汉字数（三次、两条）也算上，只用来"放行"，不用来抓编造
    out = set(numbers_in(text))
    for ch in re.findall(r"[一二两三四五六七八九十]", text): out.add(float(CN.get(ch, 10)))
    return out


def derive(nums):
    """brief 里的数做一两步加减乘除能得到的数（利润 = 售价 − 进价 − 运费、差几倍……），算出来的不算编。"""
    ns = sorted(n for n in nums if n >= 3)[:20]; out = {}   # 1、2 这种小数太容易凑出任何数（11-18：7 = 8 − 1、5 = 8 − 3 就这么混过去了）
    g = lambda v: round(v, 2)
    for a in ns:
        for b in ns:
            if a == b: continue
            for v, f in ((a + b, f"{a:g}+{b:g}"), (a - b, f"{a:g}−{b:g}"), (a * b, f"{a:g}×{b:g}"), (a / b, f"{a:g}÷{b:g}")):
                if v > 0: out.setdefault(g(v), f)
            for c in ns:
                if c not in (a, b) and a - b - c > 0: out.setdefault(g(a - b - c), f"{a:g}−{b:g}−{c:g}")
    return out   # 去掉了「任何数 ×12、÷100」：20 = 2000 ÷ 100 这种巧合会把编出来的数放过去


# 每种件最多能"变"几次：一镜的句子比这多，多出来的句子画面不动
def capacity(d):
    ty = d.get("type"); L = lambda k: len(d.get(k) or [])
    return {"title": 1, "statement": 1, "number": max(1, L("values")), "bars": L("rows"), "ledger": L("rows") + (1 if d.get("total") else 0), "ring": 1 + L("rows"),
            "timeline": max(L("nodes"), 2 if d.get("breakAt") is not None else 1),   # 一镜撑几句时一句亮一个节点
            "fork": 1 if d.get("focus") is not None else max(2, L("paths") + 1),   # 第一句长出路，之后一句划掉一条，最后一句点亮留下的那条
            "compare": 3 if d.get("badge") else 2,   # 有角标：左 → 右 → 角标
            "checklist": L("rows"), "steps": L("rows"), "cycle": L("nodes"), "cards": L("items"), "object": 1, "flow": 2}.get(ty, 1) + (1 if ty not in ("title", "statement") and (d.get("stamp") if isinstance(d.get("stamp"), str) else (d.get("stamp") or {}).get("text")) else 0)   # 盖章也算一步（大字卡上不画章）


def icon_fields(o, path="shot"):   # 找出所有 icon 字段
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "icon": yield f"{path}.icon", v
            else: yield from icon_fields(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from icon_fields(v, f"{path}[{i}]")


def width(s):   # 估算一行字幕的宽度（一个汉字 = 1）
    return sum(1 if "㐀" <= ch <= "鿿" else 0.3 if ch == " " else 0.58 for ch in s)


HIDDEN = {"icon", "type", "color", "pics", "pic", "kind", "id", "do"}   # 这些字段不上屏（图标名、件名、颜色名、写给自己看的分镜清单），不拿来查屏上用语


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
    post = film.get("post")
    if post is not None:   # 发布文案：发布标题 + 话题（+ 封面第二行）。联系方式、收入承诺、禁用词照样查（strings 会扫到它）
        if not isinstance(post, dict) or not str(post.get("title", "")).strip(): err.append('post 要写成 {"title": "发布标题", "tags": ["话题1", "话题2", "话题3"]}')
        else:
            if len(str(post["title"])) > 30: err.append(f"post.title「{post['title']}」超过 30 字：发布标题一句钩子就够")
            tags = [str(x).lstrip("#＃ ") for x in post.get("tags") or []]
            if not (3 <= len(tags) <= 5): err.append(f"post.tags 要 3–5 个话题（现在 {len(tags)} 个），不带 #")
            if any(len(x) > 12 or " " in x for x in tags): err.append("post.tags 每个话题 ≤ 12 字、中间不带空格（平台会从空格断开）")
            if post.get("cover") and len(str(post["cover"])) > 10: err.append(f"post.cover「{post['cover']}」是封面第二行小字，≤ 10 字")
    elif brief: warn.append('没写 post（发布标题 + 3–5 个话题）：在 film.json 顶层加 "post": {"title": "…", "tags": ["…"]}')
    mu = film.get("music") or {}
    if mu.get("style") and mu["style"] not in ("drive", "tension", "warm", "lofi", "doc"): err.append(f"music.style「{mu['style']}」不认识，只能是 drive / tension / warm / lofi / doc")
    if mu.get("song") and not Path(str(mu["song"])).expanduser().exists(): err.append(f"music.song 指向的歌不存在：{mu['song']}（重跑 scripts/fit_song.py，或删掉 music.song 改用合成配乐）")
    for ci, ch in enumerate(chs, 1):   # 画面写在章上（chapter.shot）= 这章第一句的 shot
        if ch.get("shot") and (ch.get("lines") or []):
            if ch["lines"][0].get("shot"): err.append(f"第{ci}章「{ch.get('name', '')}」章上写了 shot，第一句又写了 shot：只留章上那个")
            else: ch["lines"][0] = {**ch["lines"][0], "shot": ch["shot"]}
    lines, shots, pauses = [], [], []
    for ci, ch in enumerate(chs, 1):
        tag = f"第{ci}章「{ch.get('name', '')}」"
        if not ch.get("name"): err.append(f"{tag} 没有 name")
        if ch.get("color") not in COLORS: err.append(f"{tag} color 只能是 {sorted(COLORS)}")
        if ci > 1 and ch.get("color") == chs[ci - 2].get("color"): err.append(f"{tag} 和上一章同一个颜色「{ch.get('color')}」，相邻两章要换色")
        if re.search(r"[\u4e00-\u9fff]", str(ch.get("en", ""))): err.append(f"{tag} en 只能写英文")
        ls = ch.get("lines") or []
        if not ls: err.append(f"{tag} 没有字幕"); continue
        key = str(ch.get("key", ""))
        if key and (len(key) > 6 or not SUB_OK.match(key)): err.append(f"{tag} key「{key}」要 2–6 个字、不带标点（整章顶上的大关键词，比如「三把锁」「换个市场」）")
        plain_ch = all((ln.get("shot") or {}).get("type") in ("title", "statement") for ln in ls if ln.get("shot"))
        if not key and not plain_ch: warn.append(f"{tag} 没写 key：给这一章一个 2–5 字的大关键词（观众记住的那个词），整章顶在画面上")
        if len(ls) == 1 and not plain_ch and ci < len(chs): warn.append(f"{tag} 只有 1 句：一章 2–5 句围着一个画面讲，这句并进前后一章，或者再写一两句演这个画面")
        if len(ls) > 5: warn.append(f"{tag} 有 {len(ls)} 句：一章最多 5 句，拆成两章（换个关键词）")
        if ch.get("pics") is not None and len(ch.get("pics") or []) != len(ls): warn.append(f"{tag} pics 写了 {len(ch.get('pics') or [])} 条，字幕有 {len(ls)} 句：一句对一条")
        if not ls[0].get("shot"): err.append(f"{tag} 没有画面：章上写 \"shot\"（这章的画面，在 lines 前面），比如 \"shot\": {{\"type\": \"statement\", \"big\": \"两到六个字\"}}")
        for ln in ls:
            n = len(lines) + 1
            if ln.get("shot"): shots.append({"shot": ln["shot"], "lines": [], "tag": f"第{n}句起的镜", "first": n})
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
            if not (lo <= len(v) <= hi):
                tip = ""
                if len(v) < lo:
                    tip = ("：只有一个数就别用 bars，换成 number（values 写这一个数，units 写一句说明）——bars 是几样东西比大小" if ty == "bars"
                           else "：补齐条目，补的条目里不许编数字")
                err.append(f"{tag}（{ty}）{f} 要 {lo}–{hi} 个，现在 {len(v)} 个{tip}")
        if ty == "number":   # 「12 万」「30 块」放进同一个 number：suffix 只写一个「万」，第二个值就成了「30万」（11-17 实测）
            vals = d.get("values") or []
            for k, (v, ln) in enumerate(zip(vals, s["lines"])):
                u = d["suffix"][k] if isinstance(d.get("suffix"), list) and k < len(d["suffix"]) else ("" if isinstance(d.get("suffix"), list) else str(d.get("suffix") or ""))
                t = re.sub(r"\s", "", str(ln.get("text", ""))); vs = f"{float(v):g}" if str(v).replace(".", "", 1).isdigit() else str(v)
                if u and re.search(r"[一-鿿]", u) and vs in t and vs + u not in t:
                    err.append(f"第{s['first'] + k}句说的是「{ln.get('text')}」，画面上却是「{vs}{u}」：几个值单位不一样时 suffix 写成列表，一个值一个，比如 \"suffix\": [\"万\", \"\"]（prefix 也一样）")
        TIMEW = r"年|月|天|前|后|今|去|现在|以前|当时|第|原来|后来|最后|开始|一开始"
        us = [str(u) for u in (d.get("units") or [])]
        if ty == "number" and len(us) >= 2 and len(set(us)) == len(us) and not all(re.search(TIMEW, u) for u in us):
            warn.append(f"{tag} number 的几个值说的是不同东西（{' / '.join(us)}）：number 是「同一个数在变」，旧值会被划掉，看着像「{us[0]}」变成了「{us[1]}」。两样不同的东西用 compare（左右各一个）或 bars")
        if ty == "number" and len(d.get("values") or []) > len(s["lines"]) + 3: warn.append(f"{tag} number 的值比句子多太多，挤在一句里会看不清")
        if ty == "bars" and any(r.get("tag") and (len(str(r["tag"])) <= 2 or str(r["tag"]) in str(d.get("unit", ""))) for r in d.get("rows") or []): warn.append(f"{tag} bars 的 tag 像是单位（单位写在 unit 里，tag 写一句补充或留空）")
        dup = [str(r.get("note")) for r in (d.get("rows") or []) if isinstance(r, dict) and r.get("note") and str(r["note"]).replace(" ", "") in str(r.get("text", "")).replace(" ", "")]
        if dup: warn.append(f"{tag} 条目下面的小字「{'」「'.join(dup)}」和上面的大字重复了：小字写一句补充（数字、条件、结果），没有就不写")
        if ty == "steps" and any(re.fullmatch(r"\s*0?\d+\s*", str(r.get("note", "x"))) for r in d.get("rows") or []): warn.append(f"{tag} steps 的 note 只写了编号，编号会自动画，note 留空或写一句补充")
        if ty == "fork" and d.get("focus") is not None and not (0 <= int(d["focus"]) < len(d.get("paths") or [])): err.append(f"{tag} focus 超出 paths 范围")
        if ty == "fork" and d.get("pick") not in (None, -1, "none") and not (0 <= int(d["pick"]) < len(d.get("paths") or [])): err.append(f"{tag} pick 超出 paths 范围（几条全是死路就写 -1）")
        DEAD = r"没回音|没人|卡住|卡在|不够|没了|亏|难|贵|太高|进不去|没戏|走不通|换不了"
        if ty == "fork" and d.get("focus") is None and d.get("pick") not in (-1, "none"):
            pk = (d.get("paths") or [])[int(d["pick"]) if d.get("pick") is not None else -1] if d.get("paths") else {}
            if isinstance(pk, dict) and re.search(DEAD, str(pk.get("label", "")) + str(pk.get("sub", ""))):
                err.append(f"{tag} 最后点亮的那条「{pk.get('label')}」（{pk.get('sub', '')}）看着是死路：pick 是留下来、能走的那条。几条全是死路就写 \"pick\": -1（一条条全划掉）；能走的路在后面的章讲")
        if ty == "ledger":
            if not isinstance(d.get("suffix", ""), str) or not isinstance(d.get("prefix", ""), str) or "%" in str(d.get("suffix", "")) or any(re.search(r"率|转化|%|百分", str(r.get("label", ""))) for r in d.get("rows") or [] if isinstance(r, dict)):
                err.append(f"{tag} ledger 只算钱：每行同一个单位（prefix / suffix 只写一个，比如 ¥），百分比、转化率不放进来——那是另一件事，用 number 或 ring 单独演")
            for i, r in enumerate(d.get("rows") or []):
                if not isinstance(r, dict) or not isinstance(r.get("value"), (int, float)) or r.get("op", "+") not in ("+", "-", "−"):
                    err.append(f"{tag} ledger 的 rows[{i}] 要写成 {{\"label\": \"卖价\", \"value\": 30}}（减的加 \"op\": \"-\"），value 写数字"); break
        if ty == "ledger" and d.get("total") and brief_nums is not None and isinstance(d.get("rows"), list):   # 合计是程序算的：算出来要和 brief 说的总数对得上（11-18：三笔账合计亏 7.8 万，开头却说亏了 9 万）
            rows_ok = [r for r in d["rows"] if isinstance(r, dict) and isinstance(r.get("value"), (int, float))]
            tot = abs(sum((-1 if r.get("op") in ("-", "−") else 1) * float(r["value"]) for r in rows_ok))
            if rows_ok and round(tot, 2) not in brief_nums and round(tot, 2) not in derived and "按" not in str(d.get("note", "")):
                big = sorted(v for v in brief_nums if v >= 100)
                err.append(f"{tag} ledger 合计算出来是 {tot:g}，brief 里没有这个数（brief 的数：{'、'.join(f'{v:g}' for v in big[:8])}）：几笔账加起来要等于 brief 说的总数。"
                           f"最小改法：删掉 / 改掉不在 brief 里的那一笔，让合计对上；真是这么算的，note 写「按 … 算」")
        if ty == "bars":   # 横条的数要是字幕里说到的（11-17：模型为了躲"清单最多 2 个"，编了「1 条规矩 / 3 条规矩」这种没意义的数）
            said = set().union(set(), *[loose_nums(str(ln.get("text", ""))) for ln in s["lines"]])
            bad = [f"rows[{i}]「{r.get('label')} {r.get('value')}」" for i, r in enumerate(d.get("rows") or []) if isinstance(r, dict) and isinstance(r.get("value"), (int, float)) and float(r["value"]) not in said]
            if bad: err.append(f"{tag} bars 的 {'、'.join(bad)} 这个数字幕里没说：横条只用来比字幕里说到的几个数。最小改法：没有数可比就换成 cards（一项一样东西）；是一笔笔账就换成 ledger")
        if ty == "timeline" and d.get("breakAt") is not None and not (0 <= int(d["breakAt"]) < len(d.get("nodes") or []) - 1): err.append(f"{tag} breakAt 要小于节点数 - 1")
        if ty == "timeline" and d.get("breakStep") is not None and int(d["breakStep"]) >= len(s["lines"]): err.append(f"{tag} breakStep={d['breakStep']} 但这一镜只有 {len(s['lines'])} 句，裂不到")
        if ty != "draw":   # draw 的图标在 draw_check 里查
            for pth, v in [(p, v) for p, v in icon_fields(d)]:
                if v not in ICONS: err.append(f"{tag} {pth} 的图标「{v}」没有。像的有：{' '.join(icon_suggest(v)) or '（没有）'}。查图标：python3 scripts/find_icon.py <中文或英文词>")
        if ty == "object" and d.get("count") is not None and int(d["count"]) < 2: err.append(f"{tag} object 的 count 至少 2（一个就别写 count）")
        span, cap = len(s["lines"]), capacity(d)
        st = d.get("stamp")
        if isinstance(st, str): st = d["stamp"] = {"text": st}   # "stamp": "白干" 也认
        draw_moving = draw_shown = None
        if ty == "draw": draw_moving, draw_shown = draw_check.check(d, span, tag, err, warn, stamp=st)
        if st is not None:
            if not isinstance(st, dict) or not (1 <= len(str(st.get("text", "")).replace(" ", "")) <= 5) or not SUB_OK.match(str(st.get("text", "x"))): err.append(f"{tag} stamp「{(st or {}).get('text', '') if isinstance(st, dict) else st}」要 2–5 个字、不带标点，写成 {{\"text\": \"白干\"}}")
            elif st.get("at") is not None and int(st["at"]) != span - 1: err.append(f"{tag} stamp 的 at={st['at']}：章是这一段的结论，只盖在这一镜最后一句。最小改法：删掉 \"at\"")
            if ty in ("title", "statement"): warn.append(f"{tag} {ty} 上不画盖章，stamp 放到有画面的那一镜")
        def leaves(o, top=True):   # 这一镜的 note 是出处小字，不算；条目里的 note（steps / cards 每条下面那行）是上屏的，算（11-18：「收了六百」写在条目 note 里被当成没画，白花一轮 pro）
            if isinstance(o, bool): return
            if isinstance(o, (int, float, str)): yield str(o)
            elif isinstance(o, dict): yield from (x for k, v in o.items() if k not in HIDDEN | {"breakAt", "breakStep", "pick", "focus", "at", "max", "pct"} and not (top and k == "note") for x in leaves(v, False))
            elif isinstance(o, list): yield from (x for v in o for x in leaves(v, False))
        on_screen = set().union(set(), *[numbers_in(str(x)) for x in (draw_shown if ty == "draw" else leaves(d)) if x is not None])
        on_screen |= {float(len(d[k])) for k in ("rows", "items", "paths", "nodes", "values") if isinstance(d.get(k), list)}   # 画了 5 条路，字幕说「列了 5 条」就是画面上的数
        if ty == "ledger" and d.get("total"):   # 合计是程序算出来画上去的
            tot = sum((-1 if r.get("op") in ("-", "−") else 1) * float(r.get("value") or 0) for r in d.get("rows") or [] if isinstance(r, dict) and isinstance(r.get("value"), (int, float)))
            on_screen |= {round(tot, 2), round(abs(tot), 2)}
        for j, ln in enumerate(s["lines"]):   # 字幕说的数，这一镜画面上要有（说"上了40个商品"，画面上就得有 40）
            same = lambda v: {round(v * k, 2) for k in (1, 1e3, 1e4, 1e8, 1e-3, 1e-4)}   # 12万 / 120000 / 12（suffix 写「万」）是同一个数
            miss = sorted(v for v in numbers_in(str(ln.get("text", ""))) if v >= 3 and not (same(v) & on_screen) and not (1900 <= v <= 2100))
            if miss: err.append(f"第{s['first'] + j}句「{ln.get('text')}」说了 {'、'.join(f'{v:g}' for v in miss)}，可这一镜（{ty}）画面上没有：把它写成这一镜的一条（values / rows / items 里，或 count、label），换不进去就换一个能放下它的件；或者这句不说数")
        still = [j for j in range(span) if j not in draw_moving and not (st and j == span - 1)] if ty == "draw" else range(cap, span)
        for j in still:   # 画面不动的句子（停顿句）
            pauses.append((s["first"] + j, s["lines"][j], tag, ty))
        if ty in ("checklist", "steps", "cycle", "cards", "bars") and span >= 2:
            said = " ".join(str(ln.get("text", "")) for ln in s["lines"])
            items = d.get("rows") or d.get("nodes") or d.get("items") or []
            lost = [str(x.get("text") or x.get("label") or x.get("name") or "") for x in items if isinstance(x, dict)]
            lost = [t for t in lost if len(t) >= 2 and not any(t[i:i + 2] in said for i in range(len(t) - 1))]
            if lost: warn.append(f"{tag}（{ty}）的条目「{'」「'.join(lost)}」这一镜的字幕里都没说：合镜时每句加的那条要是这句说的东西，字幕没说的删掉或换成字幕说的")
        if ty in ("steps", "checklist", "cards", "cycle", "fork"):
            k = len(d.get("rows") or d.get("items") or d.get("nodes") or d.get("paths") or [])
            unit = "条路" if ty == "fork" else "步|件事"   # 「5 条路」只和岔路对；片尾说"前面那 5 条路"时不拿步骤件去比（11-18 误报）
            for ln in s["lines"]:
                m = re.search(rf"(?<!第)([0-9]+|[二两三四五六七八九十]) ?({unit})", str(ln.get("text", "")))   # "一条视频"的"条"是量词，不核对；「先走一步」「第一步」是说法，不是条数
                if m and int(cn2num(m.group(1)) if not m.group(1).isdigit() else m.group(1)) != k:
                    err.append(f"{tag} 字幕说「{m.group(0)}」，但画面只有 {k} 条：让两边对上（改字幕里的数，或补齐条目）")
        if ty == "bars" and len({str(r.get("value")) for r in d.get("rows") or []}) == 1 and len(d.get("rows") or []) > 1: err.append(f"{tag} bars 每条的值都一样，比不出大小：换成有差别的真实数，或者换件（checklist / steps）")
        zero = (ty == "number" and any(str(x).strip() in ("0", "0.0") for x in d.get("values") or []) and (str(d.get("prefix", "")) in ("¥", "$") or "元" in str(d.get("suffix", "")))) \
            or any(re.search(r"[¥$]\s*0(?![.\d])|(?<![\d.])0\s*元", x) for x in strings(d)) \
            or any(re.search(r"[¥$]\s*0(?![.\d])|(?<![\d.])0\s*元|零元", str(ln.get("text", ""))) for ln in s["lines"])
        if zero and not re.search(r"免费|(?<![\d.])0\s*元|零元|¥\s*0(?![.\d])", json.dumps(brief, ensure_ascii=False)):
            err.append(f"{tag} 屏上出现了 ¥0 / 0 元：等于说不花钱（零成本承诺），brief 里没有这个依据。删掉这个 0，只留 brief 里有的那个数（比如只放「请人拍一张 ¥50」）")
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
                        if k not in ("type", "note", "breakAt", "breakStep", "pick", "max", "ok", "pct", "from") and not (ty == "draw" and (k in draw_check.brief_walk_skip() or (k == "value" and o.get("kind") == "bar") or (k == "to" and o.get("do") == "fill"))): yield from walk(v, f"{path}.{k}")
                elif isinstance(o, list):
                    for i, v in enumerate(o): yield from walk(v, f"{path}[{i}]")
            where = {}
            for pth, x in walk(d, "shot"):
                for v in numbers_in(x): where.setdefault(v, []).append(f"{pth}「{x}」")
            for j, ln in enumerate(s["lines"]):
                for v in numbers_in(str(ln.get("text", ""))): where.setdefault(v, []).append(f"第{s['first'] + j}句字幕「{ln.get('text')}」")
            where = {v: " 和 ".join(w) for v, w in where.items()}   # 一个数常常字幕和画面里都有：全列出来，只删一处会和"字幕说的数画面上要有"来回打架（11-17 实测）
            odd = sorted(v for v in where if v > 2 and v not in brief_nums and not (1900 <= v <= 2100))
            for v in [v for v in odd if v in derived]:
                if brief.get("example") or "按" in note_txt: warn.append(f"{tag} 数字 {v:g} 是从 brief 算出来的（{derived[v]}），放行")
                else: err.append(f"{tag} 数字 {v:g} 不在 brief 里，看着像 {derived[v]} 算出来的：真是这么算的，note 写「按 {derived[v]} 算」；不是就删掉这个数（凑巧算得出的数最容易混成编造）")
            odd = [v for v in odd if v not in derived]
            if odd:
                nums = "、".join(f"{v:g}（在 {where[v]}）" for v in odd)
                if re.search("按.*算|来源", note_txt): warn.append(f"{tag} 数字 {nums} 不在 brief 里（note 写了怎么算的 / 来源，放行，自己再核对一遍）")
                elif ty == "timeline" and "示意" in note_txt: warn.append(f"{tag} 人生节点的数字 {nums} 是示意（放行）")
                else:
                    tip = ""
                    rows_bad = sorted({int(m) for v in odd for m in re.findall(r"rows\[(\d+)\]", where[v])})
                    if rows_bad and isinstance(d.get("rows"), list):
                        left = [r for i, r in enumerate(d["rows"]) if i not in rows_bad]
                        tip = f"最小改法：删掉 rows[{'] / rows['.join(map(str, rows_bad))}]"
                        if ty == "bars" and len(left) == 1:
                            r = left[0]; tip += f"；删完 bars 只剩一条，比不了大小，整镜换成 number：\"values\": [{r.get('value')}]，\"units\": [\"{r.get('label', '')}\"]，unit 写进 suffix"
                        tip += "。"
                    err.append(f"{tag} 数字 {nums} 在 brief 里找不到：疑似编造（多半是照抄了 references 里的例句）。{tip}字幕和画面里出现的地方一起删掉或改掉；用 brief 里的数；从 brief 算出来的，note 写「按 … 算」；公开规则写「来源：…」；拿不出依据就别放数字（「示意」只给人生节点用）")
        has_num = any(NUM.search(str(x)) for x in (draw_shown if ty == "draw" else strings({k: v for k, v in d.items() if k not in ("type", "note", "breakAt", "breakStep", "pick", "max")})) if x is not None and not isinstance(x, bool)) or any(NUM.search(str(ln.get("text", ""))) for ln in s["lines"])
        if has_num and ty not in ("title", "statement", "steps") and not any(notes):
            err.append(f"{tag}（{ty}）屏上有数字，但没有 note 写出处（真实来源 / 示例 / 示意）")
        if brief.get("example") and has_num and any(notes) and not any(n and re.search("示例|示意", n) for n in notes):
            err.append(f"{tag} brief 标了 example（数字不是真实数据），note 必须写「示例」或「示意」")
    for a, b in zip(shots, shots[1:]):   # 先揭晓（pick）再逐条讲（focus）：答案提前露了底
        da, db = a["shot"], b["shot"]
        if da.get("type") == db.get("type") == "fork" and da.get("focus") is None and db.get("focus") is not None and da.get("paths") == db.get("paths"):
            err.append(f"{a['tag']} 先用 pick 把答案亮出来了，后面几镜才逐条讲同一组路，顺序反了：这一镜改成 \"focus\": 0（讲第一条），最后讲到的那条就是答案，不用 pick")
    for a, b in zip(shots, shots[1:]):   # 连着几镜逐条讲同一组岔路：每镜的 paths 要一模一样，只改 focus
        da, db = a["shot"], b["shot"]
        if da.get("type") == db.get("type") == "fork" and da.get("focus") is not None and db.get("focus") is not None and da.get("paths") != db.get("paths"):
            warn.append(f"{b['tag']} 和上一镜是同一组岔路，但 paths 写得不一样（前后会对不上）：照抄上一镜的 paths，只改 focus")
    every = list(strings(film)) + [str(ln.get("text", "")) for ln in lines]
    for x in every:
        for name, pat, is_err in (("联系方式或诱导互动", CONTACT, True), ("收入承诺", PROMISE, True), ("内部用语", INTERNAL, True), ("绝对化用语", ABSOLUTE, False)):
            m = re.search(pat, x)
            if m: (err if is_err else warn).append(f"屏上出现{name}「{m.group(0)}」：{x}")
    btxt = json.dumps(brief, ensure_ascii=False)
    for w in ("被裁", "裁员", "被优化", "失业", "厂子", "越南", "房贷", "孩子"):   # references 的例句是"被裁之后"写的，别的题目会被带偏（11-18：转行盘点写出了「被裁之后」）
        hit = [str(ln.get("text", "")) for ln in lines if w in str(ln.get("text", ""))]
        if brief and hit and w not in btxt: err.append(f"字幕「{hit[0]}」说到「{w}」，brief 里没有这件事：别把 references 例句里的经历搬过来，只写 brief 里有的")
    for w in brief.get("banned") or []:
        if any(w in x for x in every): err.append(f"出现了 brief 里禁止的说法「{w}」")
    n = len(lines)
    if brief.get("seconds"):
        want = round(brief["seconds"] / bar)
        if abs(n - want) > 1:
            per = "，".join(f"「{c.get('name')}」{len(c.get('lines') or [])} 句" for c in chs)
            order = sorted(range(len(chs)), key=lambda i: len(chs[i].get("lines") or []), reverse=n > want)   # 多了从句子最多的章删，少了往句子最少的章加
            pick = "、".join(f"「{chs[i].get('name')}」" for i in sorted(order[:abs(n - want)]))
            how = (f"还差 {want - n} 句。最小改法：在 {pick} 各加一句（这章画面的条目同时加一条，就是这句说的东西）" if n < want
                   else f"多了 {n - want} 句。最小改法：{pick} 各删一句（这章画面的条目同时删掉那一条），其他章一句都不动")
            err.append(f"{brief['seconds']} 秒 @ {bpm} BPM 要正好 {want} 句（一句一小节 {bar:.2f} 秒），现在 {n} 句。{how}。现在各章：{per}")
    if shots and shots[0]["shot"].get("type") not in ("title", "statement", "timeline", "number", "compare", "fork", "object", "draw"): warn.append("开头第一镜不是钩子类（title / statement / timeline / number / compare / fork / object / draw，见 references/02 的钩子表），确认前 3 秒能让人停下")
    if len(lines) >= 8:   # 首尾回扣：倒数两句里要有第一句的词（看完想再刷一遍开头）
        first = re.sub(r"\s", "", str(lines[0].get("text", "")))
        tail = "".join(str(ln.get("text", "")) for ln in lines[-3:-1])
        if not any(first[i:i + 2] in tail for i in range(len(first) - 1)):
            warn.append(f"结尾没回扣开头：倒数第二、三句用回第一句「{lines[0].get('text')}」里的词或画面，但意思变了")
    pics = sum(1 for i, x in enumerate(shots) if not (i and x["shot"].get("type") == "fork" and x["shot"].get("focus") is not None
                                                      and shots[i - 1]["shot"].get("type") == "fork" and shots[i - 1]["shot"].get("paths") == x["shot"].get("paths")))   # 逐条讲同一组岔路只换高亮，算一个画面
    if len(pauses) > pause_max(n):
        lst = "、".join(f"第{no}句「{ln.get('text')}」" for no, ln, _, _ in pauses)
        HOW = {"object": "object 只演一步：换成 cards 或 checklist（一句一条，条目就是这几句说的东西）",
               "statement": "大字卡只演一步：这几句并进前后有画面的章，或者这章换成有条目的件",
               "title": "片名卡只演一步：后面几句另开一章，或删掉",
               "compare": "加 badge（第三句单独出），还不够就把后面几句改成说左右两边的东西",
               "number": "values 再加这句说的那个数（units 跟着加），或者结论句加 stamp",
               "draw": "这句说到的东西加一样进 items（at 写这一句），或者给已有的东西加一个 acts 动作（划掉 / 打勾 / 数字变 / 挪过去），at 写这一句"}
        by = {}
        for no, ln, tag, ty in pauses: by.setdefault((tag, ty), []).append(f"第{no}句「{ln.get('text')}」")
        fixes = "；".join(f"{tag}（{ty}）后面 {'、'.join(x)} 不动 → {HOW.get(ty, 'rows / nodes / items 多写一条（就是这句说的东西），或者结论句加 stamp 盖个章')}" for (tag, ty), x in by.items())
        err.append(f"{len(pauses)} 句画面不动，{n} 句最多 {pause_max(n)} 句（只留给提问 / 结论）。最小改法：{fixes}")
    elif pauses:
        warn.append("停顿句（画面不动，留给观众想一下）：" + "、".join(f"第{no}句「{ln.get('text')}」" for no, ln, _, _ in pauses) + "。只适合提问 / 结论；不是的话给那一镜加一步")
    if len(lines) >= 8 and pics > pic_max(n):
        same = []   # 同一章里连着两镜用同一种件：最好并（两个 number 并成一个 values 列表）
        for a, b in zip(shots, shots[1:]):
            ta, tb = a["shot"].get("type"), b["shot"].get("type")
            if ta == tb and ta not in ("fork", "statement", "title") and any(b["lines"][0] is ln for c in chs for ln in (c.get("lines") or [])[1:] if any(a["lines"][0] is x for x in c.get("lines") or [])):
                f = {"number": "values（units 跟着加）", "object": "（换成 steps / checklist，一条一样东西）", "compare": "（换成 steps / checklist）"}.get(ta, "rows / nodes / items")
                same.append(f"删掉第{b['first']}句的 shot，把它的内容并进第{a['first']}句那一镜的 {f}")
        busy = "；".join(f"「{c.get('name')}」{len(c.get('lines') or [])} 句 {sum(1 for l in c.get('lines') or [] if l.get('shot'))} 镜" for c in chs if sum(1 for l in c.get("lines") or [] if l.get("shot")) > 1)
        msg = (f"画面换得太勤：{n} 句换了 {pics} 个画面（目标 ≤ {pic_max(n)} 个，一个画面撑 2 句以上；标杆样片 3.5 句）。"
               + (f"最小改法：{'；'.join(same)}。" if same else "最小改法：一章只在第一句写 shot，把这章的几句改写成在说这个画面上的第 1、2、3 条。")
               + f"开了好几镜的章：{busy or '无'}")
        (err if pics > pic_hard(n) else warn).append(msg)
    stamps = [x["tag"] for x in shots if x["shot"].get("stamp")]
    if len(stamps) > 2: warn.append(f"盖了 {len(stamps)} 个章（{'、'.join(stamps)}）：章是全片的重音，最多 2 个，只留最狠的那一两句（样片全片只盖一次）")
    lists = [x for x in shots if x["shot"].get("type") in ("steps", "checklist")]   # 纯文字清单：什么都装得下，模型会全往里塞，整片像几页 PPT（11-17 实测 4 章全是 steps）
    if len(shots) >= 3 and len(lists) > max(2, len(shots) // 3):
        tips = []
        for x in lists[:-1]:   # 留最后一个（片尾的「下一步」用 steps 正合适），前面的给出换法
            rows = [str(r.get("text", "")) for r in x["shot"].get("rows") or [] if isinstance(r, dict)]
            if sum(1 for r in rows if re.search(r"\d", r)) >= 2: how = "ledger（一句记一笔账，合计自动算）、number（一个数在变）或 bars（几样东西比大小）"
            elif re.search(r"路|选|还是", " ".join(str(l.get("text", "")) for l in x["lines"])): how = "fork（paths 一条路一个，第一句长出来，之后一句划掉一条）"
            else: how = "cards（items 一项一样东西，配 icon）或 object（一样认得出的东西）"
            tips.append(f"{x['tag']} 的 {x['shot'].get('type')} 换成 {how}")
        err.append(f"{len(lists)} 个画面都是文字清单（steps / checklist），全片最多 {max(2, len(shots) // 3)} 个：清单只是一行行字，不是画面。最小改法：{'；'.join(tips)}。字幕不用动")
    run = 0
    for x in shots:
        run = run + 1 if x["shot"].get("type") in ("statement", "title") else 0
        if run == 3: warn.append(f"{x['tag']} 已经连着 3 镜是纯大字（statement / title），画面单调：中间换一镜有东西的（object / steps / compare），或把两句合进同一镜"); break
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
