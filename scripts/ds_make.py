# -*- coding: utf-8 -*-
"""全程交给 DeepSeek 接口：写 film.json → 检查不过自动改 → 截图让 DeepSeek 看图评审 → 按意见改 → （可选）出整片。
  python3 scripts/ds_make.py <工程目录>                 需要 <工程>/brief.json（访谈答案）；没有工程会自动建
  python3 scripts/ds_make.py <工程目录> --render        评审完直接出整片
  python3 scripts/ds_make.py <工程目录> --keep          已有 film.json：不重写，只检查 + 评审 + 改
  python3 scripts/ds_make.py <工程目录> --review-only   只看图评审、列出问题，不改（给不能看图的助手用：它自己按意见改）
  选项：--model deepseek-flash（默认）| deepseek-v4-pro    --budget 0.5（这条片最多花几元，默认 0.5）
        --rounds 3（检查不过最多改几轮）   --no-review（不看图）
钥匙：环境变量 DEEPSEEK_API_KEY，或技能目录的 .env（不进 git）。
省钱的做法：固定的说明放在最前面（DeepSeek 自动缓存，命中部分约 1/50 价）；关掉思考；改稿接着上一轮对话；每一步记账，超预算就停。
花了多少写在 <工程>/review/cost.json。"""
import base64, datetime, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
# 元 / 百万 tokens：(缓存命中, 未命中, 输出)；空闲时段半价。来源：DeepSeek 官方价格页（2026-11-15 核对）
PRICE = {"deepseek-flash": (0.04, 2.0, 8.0), "deepseek-v4-pro": (0.30, 9.0, 27.0)}
VISION = "deepseek-flash"   # 只有 flash 能看图


# ---------- 接口 ----------
def load_env():
    env = dict(os.environ)
    f = SKILL / ".env"
    if f.exists():
        for k, v in re.findall(r"^(\w+)=(.*)$", f.read_text(encoding="utf-8"), re.M):
            env.setdefault(k, v.strip().strip('"').strip("'"))
    if not env.get("DEEPSEEK_API_KEY"): sys.exit("没有 DeepSeek 钥匙：设 DEEPSEEK_API_KEY，或写进技能目录的 .env")
    return env["DEEPSEEK_API_KEY"], env.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")


def peak_now():
    bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return bj.weekday() < 5 and (9 <= bj.hour < 12 or 14 <= bj.hour < 18)   # 法定节假日按高峰算，只会多估


class Ledger:
    def __init__(self, path, budget):
        self.path, self.budget, self.rows = path, budget, []
        try: self.before = json.loads(path.read_text(encoding="utf-8")).get("calls_all", [])   # 这条片以前几次跑的账
        except Exception: self.before = []

    @property
    def total(self): return sum(r["yuan"] for r in self.rows)

    def add(self, step, model, u):
        hit = u.get("prompt_cache_hit_tokens", 0); miss = u.get("prompt_cache_miss_tokens", u.get("prompt_tokens", 0) - hit); out = u.get("completion_tokens", 0)
        p = PRICE.get(model, PRICE["deepseek-flash"]); k = 1 if peak_now() else 0.5
        yuan = (hit * p[0] + miss * p[1] + out * p[2]) / 1e6 * k
        self.rows.append({"step": step, "model": model, "cache_hit": hit, "cache_miss": miss, "out": out, "yuan": round(yuan, 5)})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        allc = self.before + self.rows
        self.path.write_text(json.dumps({"this_run_yuan": round(self.total, 4), "film_total_yuan": round(sum(r["yuan"] for r in allc), 4), "peak": peak_now(), "calls": self.rows, "calls_all": allc}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"   · {step}：缓存命中 {hit} / 未命中 {miss} / 输出 {out} tokens，¥{yuan:.4f}（累计 ¥{self.total:.4f}）")

    def guard(self):
        if self.total >= self.budget: sys.exit(f"已花 ¥{self.total:.3f}，到了预算 ¥{self.budget}，停下（加大 --budget 再跑）")


def chat(key, base, model, messages, ledger, step, json_mode=True, max_tokens=6000, soft=False):
    """soft=True：失败时返回 None，不退出（看图评审这种可选的步骤用）"""
    ledger.guard()
    body = {"model": model, "messages": messages, "temperature": 0.4, "max_tokens": max_tokens, "thinking": {"type": "disabled"}, "stream": False}
    if json_mode: body["response_format"] = {"type": "json_object"}
    for attempt in range(4):
        try:
            req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=240).read().decode())
            ledger.add(step, model, d.get("usage", {}))
            txt = d["choices"][0]["message"]["content"]
            if json_mode and d["choices"][0].get("finish_reason") == "length":   # 写到上限被截断：原样重发还会截在同一处（11-18 白花 ¥0.03），上限翻倍再来
                body["max_tokens"] = min(16000, body["max_tokens"] * 2); print(f"   （回答太长被截断，上限加到 {body['max_tokens']} 再来）"); continue
            return json.loads(txt) if json_mode else txt
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (401, 402, 403): sys.exit(f"DeepSeek 拒绝（{e.code}）：钥匙不对或余额不足。{msg}")
            if attempt == 3 or e.code not in (429, 500, 502, 503, 504):
                if soft: print(f"   DeepSeek 出错（{e.code}），跳过这一步"); return None
                sys.exit(f"DeepSeek 出错（{e.code}）：{msg}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == 3:
                if soft: print(f"   DeepSeek 没回好（{e}），跳过这一步"); return None
                sys.exit(f"DeepSeek 没回好：{e}")
        time.sleep(2 * (attempt + 1))


# ---------- 本地工具 ----------
def python_bin():
    for c in (os.environ.get("PYTHON"), str(SKILL / ".venv/bin/python"), sys.executable):
        if c and Path(c).exists() and subprocess.run([c, "-c", "import playwright, PIL"], capture_output=True).returncode == 0: return c
    sys.exit("缺 Python 依赖（playwright + pillow）：先跑 bash scripts/setup.sh")


def check(proj):
    r = subprocess.run([sys.executable, str(SKILL / "scripts/check_film.py"), str(proj / "film.json"), str(proj / "brief.json")], capture_output=True, text=True)
    out = r.stdout.strip()
    return r.returncode == 0, out, [l for l in out.splitlines() if l.startswith("✗")], [l for l in out.splitlines() if l.startswith("⚠")]


def docs():
    parts = ["SKILL.md", "references/02-引流叙事骨架.md", "references/03-分镜与画面件.md", "references/06-合规红线.md"]
    return "\n\n".join((SKILL / p).read_text(encoding="utf-8") for p in parts)


WRITE_SYS = ("你在用下面这个技能做一条竖屏引流知识短片。需求访谈已经做完（brief.json），结构用推荐骨架，出路按 brief.outlet。"
             "你只做一件事：写 film.json。只输出一个 JSON 对象，不要解释。写之前在心里过一遍：句数对不对、每句 ≤16 字无标点、每章有 shot（写在章上、lines 前面）、"
             "相邻章换色、有数字的镜写 note、开头三句能不能让人停下、结尾落到 cta。\n\n")

REVIEW_SYS = """你是竖屏知识短片的严格评审。给你一张拼图：每一格是第 N 句字幕播到一半时的画面（左下角黄字是秒数，顺序和字幕表一致），再给你字幕表。
逐格检查，只报真正的问题：
1. 遮住字幕，看得出这一格在演什么吗？画面和这句字幕对得上吗？
   一章顶上的大字是这一章的关键词，整章不变，不算问题。连着几格是同一个画面、每格多出一样东西（一条、一个点、一个数、一个盖章）是正常的做法：只看"这一格新多出来的那样"是不是这句字幕说的东西，
   对得上就不算问题，不要因为"画面和上一格差不多"就让它拆镜；对不上（这句说十七单、新多出来的却是别的）才报，改法是"这句开新镜演它"或"把这一条改成这句说的"。
2. 主体够不够大？画面是不是大半空着、东西挤在一角？
3. 有没有字压字、出画、被截断、小到手机上看不清？
4. 一格里东西是不是太多太乱？
5. 开头三格能不能让人停下来？结尾有没有给出下一步？
不要报：配色风格、霓虹发光、字体（这些是固定的样式）；不要客套。
改法不许：编 brief 里没有的数字、加联系方式或"扣1 / 领资料 / 私我"这类诱导互动的话、承诺收入；结尾的下一步只能是主页 / 合集 / 评论区。
改法只能用现有的件：title statement number bars ledger ring timeline fork(可加 focus) compare checklist steps cycle cards object flow；
"缺一样认得出的东西"就建议 object（一堆写 count）或给条目加 icon，图标只能从这些里选：{ICONS}。
每个问题归一类：
- content：改 film.json 就能解决（换一个件、删几条、缩短一段字、加 head、加图标、加 stamp……），fix 写清楚怎么改；
  改法只在同一镜里改：让第 k 条就是第 k 句说的东西、改这一条的字、加 icon、结论句加 stamp；字幕里没说的东西不许加进画面。
  不许建议开新镜、拆镜、换成别的件（一个画面撑好几句是这种片子的做法，全片画面数有上限）；同一镜实在演不了，就建议改这句的说法；
  "加个图标更好认"这类锦上添花的不报，只报对不上、看不出、看不清的；
- engine：画面件自己画坏了（越界、重叠这类排版 bug），改 film.json 解决不了。
最多报 12 条，挑最影响观感的报；只输出 JSON：{"issues":[{"line":句号(从1数),"kind":"content|engine","problem":"…","fix":"…"}],"verdict":"一句话总评"}。没问题就给空数组。"""


MOOD_BPM = {"steady": 112.8, "tight": 128, "calm": 100}   # 112.8：标杆样片那首 BGM（We Never · 若如初见）三个来源量出来都是 112.8，原来写 112 差 0.7%，90 秒片尾会错开 0.6 秒
BEATS = [("① 开场钩子 + 处境", 0.18), ("② 断裂 + 片名", 0.12), ("③ 分叉", 0.2), ("④ 收窄 / 证据", 0.22), ("⑤ 出路", 0.16), ("⑥ 行动", 0.12)]
# 每种角度的六拍说法不一样（references/02 的角度表）。11-18 实测：只给「被裁」那套说法时，转行盘点也写出了「被裁之后」
ANGLE_BEATS = {
    "laid-off": ["① 开场钩子 + 处境", "② 断裂 + 片名", "③ 分叉：几条路摆出来", "④ 收窄：用数字讲门槛", "⑤ 出路", "⑥ 行动"],
    "pivot-list": ["① 开场钩子 + 处境", "② 为什么想换", "③ 摊开几条路", "④ 每条路的门槛", "⑤ 门槛最低的那条", "⑥ 行动"],
    "ai-ecommerce": ["① 开场钩子", "② 以前一个人做不了的事", "③ AI 接过去了哪些活", "④ 证据：自己用 AI 干的活", "⑤ 出路", "⑥ 行动"],
    "own-mistake": ["① 开场钩子：亏了多少", "② 我是怎么做的", "③ 亏在哪几处", "④ 改法 / 正确的算法", "⑤ 改完的结果", "⑥ 行动"],
}


def pic_max(n): return (n + 1) // 2      # 和 check_film.py 同一套：一个画面至少撑 2 句
def pause_max(n): return max(1, n // 5)  # 最多几句画面不动（提问 / 结论）

# 开场钩子（references/02 的表）：(名字, 写法, 第一镜用)
HOOKS = {
    "熟悉的场景": ("一个他天天见的画面，第一句就让他认出自己", "object（配图标）"),
    "人生剧本": ("一条人人走过的路，走到一半断掉", "timeline"),
    "反常识的数": ("一个让人「啊？」的数，下一句说它从哪来", "number"),
    "先让他选": ("抛一个二选一，下一句才揭晓", "fork"),
    "一句扎心的话": ("说出他心里不敢说的那句", "statement"),
    "前后对比": ("同一件事换个地方 / 时间就不一样", "compare"),
    "一大堆": ("用数量压人（投了几十份简历）", "object（写 count）"),
    "结局先说": ("先给结局，再倒回去讲怎么走到这", "title"),
}


def pick_hook(brief):
    """挑开场钩子：brief.hook 指定就用它；否则按 brief 里有什么真东西挑，挑不出就按题目轮换——同一个账号天天发，开头不能每条都是人生时间轴。"""
    if brief.get("hook") in HOOKS: return brief["hook"]
    txt = " ".join(map(str, (brief.get("pain") or []) + (brief.get("proof") or [])))
    cands = []
    if re.search(r"几十|上百|上千|\d{2,}\s*(份|个|次|家|条)", txt): cands.append("一大堆")
    if len(re.findall(r"\d+(?:\.\d+)?", txt)) >= 2: cands.append("反常识的数")
    if re.search(r"床|躺|简历|工位|手机|电脑|店|仓库|包裹|孩子", txt): cands.append("熟悉的场景")
    cands += ["结局先说", "一句扎心的话", "前后对比", "先让他选", "人生剧本"]
    seed = sum(ord(ch) for ch in str(brief.get("audience", "")) + str(brief.get("outlet", "")))
    return cands[seed % len(cands)]


def platform_song(brief):
    """brief.music.platform_song 写的歌名 → scripts/platform_songs.json 里那一条（认别名）"""
    name = str((brief.get("music") or {}).get("platform_song") or "").strip()
    if not name: return None, None
    songs = json.loads((SKILL / "scripts/platform_songs.json").read_text(encoding="utf-8"))
    for k, v in songs.items():
        if k.startswith("_"): continue
        if name == k or name in v.get("aliases", []): return k, v
    return name, None


def plan_lines(brief):
    """先替模型把句数、镜数、开头结尾怎么写算好（弱模型数不清句数，填空比自己数稳）。"""
    ps = platform_song(brief)[1]
    bpm = (brief.get("music") or {}).get("bpm") or (ps or {}).get("bpm") or MOOD_BPM.get(brief.get("mood"), 112.8); n = round(brief.get("seconds", 30) / (60 / bpm * 4))   # 用自己的歌：按歌的速度排句数（fit_song.py 写进 brief.music.bpm）
    raw = [n * w for _, w in BEATS]; cnt = [max(1, int(x)) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - int(raw[i]), reverse=True):
        if sum(cnt) >= n: break
        cnt[i] += 1
    while sum(cnt) > n: cnt[cnt.index(max(cnt))] -= 1
    hook = pick_hook(brief); how, first = HOOKS[hook]
    m = max(4, round(n / 3.5)); per = [n // m + (1 if i < n % m else 0) for i in range(m)]   # 弱模型数不清句数：直接把每章几句算好给它（标杆样片一章 3.5 句）
    if len(per) > 2 and per[-1] > 2: per[-1] -= 1; per[1] += 1   # 最后一章（落到 cta）短一点
    method = (f"按「画面先行」写（标杆样片和上游项目都是这么做的：一章一个画面，一个画面撑 2–5 句，每句只往上加一样东西）。"
              f"全片分 {m} 章，每章的句数照这个写：{' '.join(map(str, per))}（加起来正好 {n} 句，pics 和 lines 都按这个数写）。每章照这四步："
              "① key：这章的大关键词，2–5 个字，观众看完记住的那个词（比如「价格战」「换个市场」），整章顶在画面上；"
              "② 在这章的 lines 前面先写 pics：这章每一句画面上多出来的那一条，一句一条（这就是分镜）；"
              "③ 照 pics 在章上写 shot（这章的画面，写在 lines 前面）：挑一个能把这几条都装下的件（几条说的是不同的事就用 steps / checklist / cards，条目里可以写数），values / rows / nodes / items 按 pics 的顺序一次写好，stamp 盖章也算一条；"
              "最后写 lines：句子里不写 shot，第 k 句说的就是第 k 条，字幕里说的数画面上必须有；"
              "④ 某条装不进这个件：先换个说法，让这句说画面上有的东西；还不行，才在这章里开第二镜。"
              "相邻两章换不同的件；steps / checklist 只是一行行字，全片最多用 2 次（片尾「下一步」用 steps 正合适）——有数就用 number / bars / ring，一笔笔算账用 ledger（合计程序自动算），几条路用 fork（全是死路写 pick: -1，pick 不能是死路），几样东西用 cards / object，从 A 到 B 用 flow，同一件事两种情况用 compare。"
              f"全片 {n} 句最多 {pic_max(n)} 个画面；最多 {pause_max(n)} 句可以画面不动（只给提问、结论，而且不许说数字）；"
              "一章最后那句是结论或情绪落点（白干、没回音、做成了）时，给这一镜加 stamp 盖一个 2–5 字的章，这句就有画面了。")
    ends = ("只写 brief 里有的经历和数：brief 没说被裁就不写被裁，references 里的例句（被裁、厂子搬去越南、房贷孩子）只是写法示范，不许搬过来。"
            f"开场用「{hook}」：{how}，第一镜用 {first}；不要用「大家好」「你知道吗」。"
            "film.json 顶层最后写 post：{\"title\": 发布标题（≤ 30 字，一句让人想点开的话，可以是问句，只用 brief 里有的事和数）, \"tags\": 3–5 个话题（不带 #，比如 跨境电商、副业、转行）, \"cover\": 封面第二行小字（≤ 10 字，可不写）}。"
            "倒数第二句回扣第一句：用回第一句里的那个词或那个画面，但意思变了（比如开头问一个选择，结尾给出答案；开头是一张床，结尾还是那张床、但人已经起来了）。用你自己的话写，不要照抄这里和 references 里的例句；最后一句落到 cta。")
    if brief.get("angle") == "custom":
        return bpm, n, f"bpm 写 {bpm}。这条片必须正好 {n} 句字幕（写完数一遍），按商量好的结构走。{method}{ends}"
    names = ANGLE_BEATS.get(brief.get("angle"), [b for b, _ in BEATS])
    lines = "；".join(f"{b} {c} 句" for b, c in zip(names, cnt))
    return bpm, n, f"bpm 写 {bpm}。这条片必须正好 {n} 句字幕（写完数一遍）。情绪顺序按六拍走：{lines}——拍不是章，相邻两拍可以放进同一章、同一个画面。{method}{ends}"


ICON_NAMES = " ".join(re.findall(r"^  (\w+)\(fr, c\)", (SKILL / "template/icons.js").read_text(encoding="utf-8"), re.M))
REVIEW_SYS = REVIEW_SYS.replace("{ICONS}", ICON_NAMES)


def mid_times(proj):
    return subprocess.run([sys.executable, str(SKILL / "scripts/sheet_times.py"), str(proj / "film.json"), "24"], capture_output=True, text=True, check=True).stdout.split()


def line_table(film):
    rows, i = [], 0
    for c in film.get("chapters") or []:
        cur = None
        for j, ln in enumerate(c.get("lines") or []):
            i += 1
            sh = ln.get("shot") or (c.get("shot") if j == 0 else None)
            if sh: cur = sh.get("type")
            rows.append(f"第{i}句 [{c.get('name')}/{cur}] {ln.get('text')}")
    return "\n".join(rows)


# ---------- 主流程 ----------
def main():
    a = sys.argv[1:]
    if not a or a[0].startswith("-"): sys.exit(__doc__)
    proj = Path(a[0]).expanduser().resolve()
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    model, budget, rounds = opt("--model", "deepseek-flash"), float(opt("--budget", "0.5")), int(opt("--rounds", "3"))
    key, base = load_env()
    if not (proj / "index.html").exists():
        subprocess.run(["bash", str(SKILL / "scripts/new_film.sh"), str(proj)], check=True, stdout=subprocess.DEVNULL)
    if not (proj / "brief.json").exists(): sys.exit(f"{proj}/brief.json 不存在：先做需求访谈（references/01）")
    vb = subprocess.run([sys.executable, str(SKILL / "scripts/validate_brief.py"), str(proj / "brief.json")], capture_output=True, text=True)
    if vb.returncode: sys.exit("brief.json 没过校验：\n" + vb.stdout)
    led = Ledger(proj / "review/cost.json", budget)
    brief = (proj / "brief.json").read_text(encoding="utf-8")
    system = {"role": "system", "content": WRITE_SYS + docs()}
    bpm, n_lines, plan = plan_lines(json.loads(brief))
    ask = {"role": "user", "content": "brief.json：\n" + brief + "\n\n" + plan + "\n按 references/03 的格式写 film.json（只输出 JSON）。"}
    print(f"开场：{pick_hook(json.loads(brief))} · " + f"模型 {model} · 预算 ¥{budget} · {'高峰' if peak_now() else '空闲（半价）'}时段")

    if "--review-only" in a: a.append("--keep")
    if "--keep" in a and (proj / "film.json").exists():
        film = json.loads((proj / "film.json").read_text(encoding="utf-8"))
    else:
        print("== 写 film.json"); film = chat(key, base, model, [system, ask], led, "写")
        mu = json.loads(brief).get("music") or {}
        if mu.get("style"): film["music"] = {**(film.get("music") or {}), "style": mu["style"]}   # 配乐风格照 brief，不交给模型
        pk, pv = platform_song(json.loads(brief))
        if pv: film["music"] = {**(film.get("music") or {}), "platform_song": pk}; film["bpm"] = pv["bpm"]   # 速度对准这首歌，模型写错了也改回来
    convo = [system, ask, {"role": "assistant", "content": json.dumps(film, ensure_ascii=False)}]

    def save(f): (proj / "film.json").write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")

    def fix_loop(film, tag):
        save(film); warned = False; last = None; used_pro = False; retried = False; good = None
        shots_of = lambda out: int((re.search(r"(\d+) 镜", out) or [0, 999])[1])
        for r in range(rounds + 2):
            ok, out, errs, warns = check(proj)
            if good and (not ok or shots_of(out) > good[1]):   # 按警告润色是"试一下"：润色后出错或画面变多（实测它一润色就拆镜），退回润色前那一版
                print(f"   （按警告改的这一版{'出了错' if not ok else f'画面从 {good[1]} 个变成 {shots_of(out)} 个'}，退回上一版）")
                film = good[0]; save(film); convo.append({"role": "assistant", "content": json.dumps(film, ensure_ascii=False)}); return film, True
            stuck = bool(errs) and last is not None and len(errs) >= len(last); last = errs   # 错误没减少 = 卡住
            final = r >= rounds and errs and not used_pro and model == "deepseek-flash"   # 轮数用完还有错：最后给 pro 一次机会
            if r > rounds or (r == rounds and not final): print("   " + out.splitlines()[0] + ("　✓" if ok else f"　✗ {len(errs)} 个错")); return film, ok
            print("   " + out.splitlines()[0] + ("　✓" if ok else f"　✗ {len(errs)} 个错"))
            warns = [w for w in warns if "放行" not in w]   # 「放行」只是告诉人这个数核对过了，发给模型它会去乱改
            todo = errs + ([] if warned else warns)
            if ok and (warned or not warns): return film, ok
            if ok: warned = True; good = (film, shots_of(out))
            ask_fix = "检查结果如下，照着改（只改有问题的地方，其他保持原样），输出完整 film.json：\n" + "\n".join(todo)
            if stuck and not retried and model == "deepseek-flash":
                # 第一次卡住先不换 pro：多半是报错没看懂。flash 只看说明 + 当前稿 + 这几条错再改一次（说明部分照样命中缓存，pro 一轮要 ¥0.05–0.09）
                print("   （同样的错没改掉，flash 只盯这几处再改一次）"); retried = True
                film = chat(key, base, model, [system, ask, {"role": "assistant", "content": json.dumps(film, ensure_ascii=False)},
                                               {"role": "user", "content": "上一轮这几处没改掉。逐条照报错里的「最小改法」做，别的地方一个字都不动，输出完整 film.json：\n" + "\n".join(errs)}], led, f"{tag}改第{r + 1}轮·盯错")
                save(film); convo.append({"role": "assistant", "content": json.dumps(film, ensure_ascii=False)}); continue
            if (stuck or final) and model == "deepseek-flash" and not used_pro:
                # 换 pro 改这一轮。pro 上没有缓存，只发说明 + brief + 当前稿 + 报错，不发前面几轮的来回（实测整段对话发过去一轮要 ¥0.2）
                print("   （" + ("同样的错没改掉" if stuck else "轮数用完还有错") + "，这一轮换 deepseek-v4-pro）"); used_pro = True
                film = chat(key, base, "deepseek-v4-pro", [system, ask, {"role": "assistant", "content": json.dumps(film, ensure_ascii=False)}, {"role": "user", "content": ask_fix}], led, f"{tag}改第{r + 1}轮·pro")
            else:
                convo.append({"role": "user", "content": ask_fix})
                film = chat(key, base, model, convo, led, f"{tag}改第{r + 1}轮")
            save(film); convo.append({"role": "assistant", "content": json.dumps(film, ensure_ascii=False)})
        return film, False

    if "--review-only" in a:   # 只评审：不改 film.json，检查结果原样列出来给助手自己改
        ok, out, errs, warns = check(proj); print("== 检查（只列出，不改）\n   " + out.replace("\n", "\n   "))
    else:
        print("== 检查 + 改"); film, ok = fix_loop(film, "检查")
        if not ok: sys.exit(f"改了 {rounds} 轮还有错，停下。看 {proj}/film.json，手动改或加大 --rounds")

    py = python_bin()
    if "--no-review" not in a:
        print("== 截图 + 画面体检 + 看图评审")
        subprocess.run([py, str(SKILL / "engine/render.py"), str(proj), "--sheet", *mid_times(proj)], check=True, stdout=subprocess.DEVNULL)
        qa = json.loads(subprocess.run([py, "-W", "ignore", str(SKILL / "scripts/frame_qa.py"), str(proj), "--json"], capture_output=True, text=True, check=True).stdout or "[]")
        print(f"   画面体检（按像素量，不花钱）：{len(qa)} 处")
        for q in qa: print(f"   - 第{q['line']}句（{q['type']}）{q['problem']}")
        img = base64.b64encode((proj / "review/sheet.jpg").read_bytes()).decode()
        rv = chat(key, base, VISION, [{"role": "system", "content": REVIEW_SYS},
                                      {"role": "user", "content": [{"type": "text", "text": "字幕表：\n" + line_table(film)},
                                                                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img}}]}], led, "看图评审", max_tokens=3000, soft=True) or {"issues": [], "verdict": "（评审没回好，跳过；画面体检照常）"}
        issues = rv.get("issues") or []
        (proj / "review/review.json").write_text(json.dumps(rv, ensure_ascii=False, indent=1), encoding="utf-8")
        content = [i for i in issues if i.get("kind") == "content"] + [{"line": q["line"], "kind": "content", "problem": q["problem"], "fix": "照上面说的改"} for q in qa]
        engine = [i for i in issues if i.get("kind") != "content"]
        print(f"   总评：{rv.get('verdict', '')}　内容问题 {len(content)} 个 · 画面件问题 {len(engine)} 个")
        for i in issues: print(f"   - 第{i.get('line')}句 [{i.get('kind')}] {i.get('problem')} → {i.get('fix')}")
        if engine:
            (proj / "review/engine_issues.md").write_text("# 画面件问题（改 film.json 解决不了，交给维护技能的人）\n\n" + "\n".join(f"- 第{i.get('line')}句：{i.get('problem')}" for i in engine) + "\n", encoding="utf-8")
        if content and "--review-only" not in a:
            convo.append({"role": "user", "content": "看图评审发现这些问题，能改的照改（只改这些地方），输出完整 film.json：\n" + "\n".join(f"第{i.get('line')}句：{i.get('problem')} → {i.get('fix')}" for i in content)})
            film = chat(key, base, model, convo, led, "按评审改"); convo.append({"role": "assistant", "content": json.dumps(film, ensure_ascii=False)})
            film, ok = fix_loop(film, "复查")
            if not ok: sys.exit("按评审改完又出了检查错误，停下，看 film.json")
    subprocess.run([py, str(SKILL / "engine/render.py"), str(proj), "--sheet", *mid_times(proj)], check=True, stdout=subprocess.DEVNULL)   # 最后一版的拼图
    qa = json.loads(subprocess.run([py, "-W", "ignore", str(SKILL / "scripts/frame_qa.py"), str(proj), "--json"], capture_output=True, text=True).stdout or "[]")
    print(f"== 最后一版画面体检：{len(qa)} 处" + ("（不影响出片，想更好就手动改 film.json）" if qa else " ✓"))
    for q in qa: print(f"   - 第{q['line']}句（{q['type']}）{q['problem']}")
    print(f"== 完成：{proj}/film.json · 拼图 {proj}/review/sheet.jpg · 这次花 ¥{led.total:.4f}，这条片累计 ¥{sum(r['yuan'] for r in led.before + led.rows):.4f}")
    song = (json.loads(brief).get("music") or {}).get("song")
    if song and not (film.get("music") or {}).get("song"):   # brief 里登记了自己的歌（fit_song.py 写的，已确认能商用）：按这一稿的句数重新挑段落、对齐
        print("== 对齐你的歌"); subprocess.run([py, str(SKILL / "scripts/fit_song.py"), str(proj), str(song), "--licensed"], check=True)
    if "--render" in a:
        subprocess.run(["bash", str(SKILL / "scripts/build.sh"), str(proj)], check=True, env={**os.environ, "PYTHON": py})


if __name__ == "__main__":
    main()
