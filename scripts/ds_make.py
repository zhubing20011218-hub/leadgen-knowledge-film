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


def chat(key, base, model, messages, ledger, step, json_mode=True, max_tokens=6000):
    ledger.guard()
    body = {"model": model, "messages": messages, "temperature": 0.4, "max_tokens": max_tokens, "thinking": {"type": "disabled"}, "stream": False}
    if json_mode: body["response_format"] = {"type": "json_object"}
    for attempt in range(4):
        try:
            req = urllib.request.Request(base + "/chat/completions", data=json.dumps(body).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=240).read().decode())
            ledger.add(step, model, d.get("usage", {}))
            txt = d["choices"][0]["message"]["content"]
            return json.loads(txt) if json_mode else txt
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code in (401, 402, 403): sys.exit(f"DeepSeek 拒绝（{e.code}）：钥匙不对或余额不足。{msg}")
            if attempt == 3 or e.code not in (429, 500, 502, 503, 504): sys.exit(f"DeepSeek 出错（{e.code}）：{msg}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == 3: sys.exit(f"DeepSeek 没回好：{e}")
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
             "你只做一件事：写 film.json。只输出一个 JSON 对象，不要解释。写之前在心里过一遍：句数对不对、每句 ≤16 字无标点、每章第一句有 shot、"
             "相邻章换色、有数字的镜写 note、开头三句能不能让人停下、结尾落到 cta。\n\n")

REVIEW_SYS = """你是竖屏知识短片的严格评审。给你一张拼图：每一格是第 N 句字幕播到一半时的画面（左下角黄字是秒数，顺序和字幕表一致），再给你字幕表。
逐格检查，只报真正的问题：
1. 遮住字幕，看得出这一格在演什么吗？画面和这句字幕对得上吗？
2. 主体够不够大？画面是不是大半空着、东西挤在一角？
3. 有没有字压字、出画、被截断、小到手机上看不清？
4. 一格里东西是不是太多太乱？
5. 开头三格能不能让人停下来？结尾有没有给出下一步？
不要报：配色风格、霓虹发光、字体（这些是固定的样式）；不要客套。
改法不许：编 brief 里没有的数字、加联系方式或"扣1 / 领资料 / 私我"这类诱导互动的话、承诺收入；结尾的下一步只能是主页 / 合集 / 评论区。
每个问题归一类：
- content：改 film.json 就能解决（换一个件、删几条、缩短一段字、加 head、拆成两镜……），fix 写清楚怎么改；
- engine：画面件自己画坏了（越界、重叠这类排版 bug），改 film.json 解决不了。
只输出 JSON：{"issues":[{"line":句号(从1数),"kind":"content|engine","problem":"…","fix":"…"}],"verdict":"一句话总评"}。没问题就给空数组。"""


MOOD_BPM = {"steady": 112, "tight": 128, "calm": 100}
BEATS = [("① 人生节点 / 处境", 0.18), ("② 断裂 + 片名", 0.12), ("③ 分叉", 0.2), ("④ 收窄 / 证据", 0.22), ("⑤ 出路", 0.16), ("⑥ 行动", 0.12)]


def plan_lines(brief):
    """先替模型把句数算好：总句数 + 每一拍几句（弱模型数不清句数，填空比自己数稳）。"""
    bpm = MOOD_BPM.get(brief.get("mood"), 112); n = round(brief.get("seconds", 30) / (60 / bpm * 4))
    raw = [n * w for _, w in BEATS]; cnt = [max(1, int(x)) for x in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - int(raw[i]), reverse=True):
        if sum(cnt) >= n: break
        cnt[i] += 1
    while sum(cnt) > n: cnt[cnt.index(max(cnt))] -= 1
    if brief.get("angle") == "custom":
        return bpm, n, f"bpm 写 {bpm}。这条片必须正好 {n} 句字幕（写完数一遍），按商量好的结构分 {max(3, n // 4)}–{max(4, n // 3)} 章，每章 2–5 句。"
    lines = "；".join(f"{b} {c} 句" for (b, _), c in zip(BEATS, cnt))
    return bpm, n, f"bpm 写 {bpm}。这条片必须正好 {n} 句字幕（写完数一遍）。按六拍分：{lines}。每拍是 1–2 章，每章 2–5 句。"


def mid_times(proj):
    return subprocess.run([sys.executable, str(SKILL / "scripts/sheet_times.py"), str(proj / "film.json"), "24"], capture_output=True, text=True, check=True).stdout.split()


def line_table(film):
    rows, i = [], 0
    for c in film.get("chapters") or []:
        cur = None
        for ln in c.get("lines") or []:
            i += 1
            if ln.get("shot"): cur = ln["shot"].get("type")
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
    print(f"模型 {model} · 预算 ¥{budget} · {'高峰' if peak_now() else '空闲（半价）'}时段")

    if "--review-only" in a: a.append("--keep")
    if "--keep" in a and (proj / "film.json").exists():
        film = json.loads((proj / "film.json").read_text(encoding="utf-8"))
    else:
        print("== 写 film.json"); film = chat(key, base, model, [system, ask], led, "写")
    convo = [system, ask, {"role": "assistant", "content": json.dumps(film, ensure_ascii=False)}]

    def save(f): (proj / "film.json").write_text(json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")

    def fix_loop(film, tag):
        save(film); warned = False; last = None
        for r in range(rounds + 1):
            ok, out, errs, warns = check(proj)
            stuck = bool(errs) and errs == last; last = errs
            print("   " + out.splitlines()[0] + ("　✓" if ok else f"　✗ {len(errs)} 个错"))
            todo = errs + ([] if warned else warns)
            if (ok and (warned or not warns)) or r == rounds: return film, ok
            if ok: warned = True
            convo.append({"role": "user", "content": "检查结果如下，照着改（只改有问题的地方，其他保持原样），输出完整 film.json：\n" + "\n".join(todo)})
            m = "deepseek-v4-pro" if stuck and model == "deepseek-flash" else model   # 同样的错改不掉：换强一点的模型改这一轮
            if m != model: print("   （同样的错连续两轮没改掉，这一轮换 deepseek-v4-pro）")
            film = chat(key, base, m, convo, led, f"{tag}改第{r + 1}轮" + ("·pro" if m != model else "")); save(film)
            convo.append({"role": "assistant", "content": json.dumps(film, ensure_ascii=False)})
        return film, False

    if "--review-only" in a:   # 只评审：不改 film.json，检查结果原样列出来给助手自己改
        ok, out, errs, warns = check(proj); print("== 检查（只列出，不改）\n   " + out.replace("\n", "\n   "))
    else:
        print("== 检查 + 改"); film, ok = fix_loop(film, "检查")
        if not ok: sys.exit(f"改了 {rounds} 轮还有错，停下。看 {proj}/film.json，手动改或加大 --rounds")

    py = python_bin()
    if "--no-review" not in a:
        print("== 截图 + 看图评审")
        subprocess.run([py, str(SKILL / "engine/render.py"), str(proj), "--sheet", *mid_times(proj)], check=True, stdout=subprocess.DEVNULL)
        img = base64.b64encode((proj / "review/sheet.jpg").read_bytes()).decode()
        rv = chat(key, base, VISION, [{"role": "system", "content": REVIEW_SYS},
                                      {"role": "user", "content": [{"type": "text", "text": "字幕表：\n" + line_table(film)},
                                                                   {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img}}]}], led, "看图评审", max_tokens=2000)
        issues = rv.get("issues") or []
        (proj / "review/review.json").write_text(json.dumps(rv, ensure_ascii=False, indent=1), encoding="utf-8")
        content = [i for i in issues if i.get("kind") == "content"]; engine = [i for i in issues if i.get("kind") != "content"]
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
    print(f"== 完成：{proj}/film.json · 拼图 {proj}/review/sheet.jpg · 这次花 ¥{led.total:.4f}，这条片累计 ¥{sum(r['yuan'] for r in led.before + led.rows):.4f}")
    if "--render" in a:
        subprocess.run(["bash", str(SKILL / "scripts/build.sh"), str(proj)], check=True, env={**os.environ, "PYTHON": py})


if __name__ == "__main__":
    main()
