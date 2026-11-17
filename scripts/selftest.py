# -*- coding: utf-8 -*-
"""自测（不联网、不花钱，约 1–2 分钟）：改了技能之后跑一遍，确认没改坏。
  python3 scripts/selftest.py            全部
  python3 scripts/selftest.py --quick    跳过渲染和节拍检测（约 5 秒）
查：脚本能编译 → 示例过检查 → 一组故意写错的稿子都被拦下 → 四种配乐能合成 → 节拍检测量得准 → 示例拼图画面体检 0 处。"""
import copy, json, re, subprocess, sys, tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
EX = SKILL / "examples/01-被裁之后"
PY = str(SKILL / ".venv/bin/python") if (SKILL / ".venv/bin/python").exists() else sys.executable
ok = fail = 0


def report(name, good, detail=""):
    global ok, fail
    ok, fail = ok + good, fail + (not good)
    print(("  ✓ " if good else "  ✗ ") + name + ("" if good else f"　{detail}"))


def run(*cmd, **kw):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def check(film, brief):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "film.json").write_text(json.dumps(film, ensure_ascii=False), encoding="utf-8")
        (Path(d) / "brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
        r = run(sys.executable, SKILL / "scripts/check_film.py", Path(d) / "film.json", Path(d) / "brief.json")
        return r.returncode, r.stdout


print("== 1 脚本能编译")
bad = [p.name for p in (SKILL / "scripts").glob("*.py") if run(sys.executable, "-m", "py_compile", p).returncode]
bad += [p.name for p in list((SKILL / "template").glob("*.js")) + list((SKILL / "scripts").glob("*.mjs")) if run("node", "--check", p).returncode]
bad += [p.name for p in (SKILL / "scripts").glob("*.sh") if run("bash", "-n", p).returncode]
report("Python / JS / Shell 语法", not bad, " ".join(bad))

print("== 2 示例过检查")
film = json.loads((EX / "film.json").read_text(encoding="utf-8")); brief = json.loads((EX / "brief.json").read_text(encoding="utf-8"))
code, out = check(film, brief); report("examples/01 film.json 通过", code == 0, out[-300:])
report("examples/01 brief.json 通过", run(sys.executable, SKILL / "scripts/validate_brief.py", EX / "brief.json").returncode == 0)

print("== 3 写错的稿子都被拦下（每条：改坏一处 → 报错里要有这几个字）")
def first_shot(f):
    c = f["chapters"][0]; return c.get("shot") or c["lines"][0]["shot"]
def fork_shot(f):
    return next((c.get("shot") or c["lines"][0].get("shot")) for c in f["chapters"] if (c.get("shot") or c["lines"][0].get("shot") or {}).get("type") == "fork")
CASES = [
    ("字幕带标点", lambda f: f["chapters"][0]["lines"][0].__setitem__("text", "我们，都一样。"), "标点"),
    ("编数字", lambda f: f["chapters"][0]["lines"][0].__setitem__("text", "我投了 777 份简历"), "777"),
    ("联系方式", lambda f: f["chapters"][-1]["lines"][-1].__setitem__("text", "加我微信领资料"), "联系方式"),
    ("收入承诺", lambda f: f["chapters"][-1]["lines"][-1].__setitem__("text", "跟着做月入过万"), "收入承诺"),
    ("死路被点亮", lambda f: fork_shot(f).__setitem__("pick", len(fork_shot(f)["paths"]) - 1), "死路"),
    ("横条乱填数", lambda f: f["chapters"][1].__setitem__("shot", {"type": "bars", "rows": [{"label": "甲", "value": 4}, {"label": "乙", "value": 6}]}), "字幕里没说"),
    ("句数不对", lambda f: f["chapters"][-1]["lines"].extend([{"text": "多出来的一句"}, {"text": "又多一句"}]), "要正好"),
    ("编的经历", lambda f: f["chapters"][0]["lines"][0].__setitem__("text", "房贷压得我喘不过气"), None),
]
for name, mutate, want in CASES:
    f = copy.deepcopy(film); mutate(f); code, out = check(f, brief)
    errs = [l for l in out.splitlines() if l.startswith("✗")]
    if want is None:   # 例句里的经历：brief 里有「房贷」就不该拦（examples/01 的 brief 有），换一份没有的 brief 再看
        b2 = dict(brief); b2["pain"] = ["38 岁，做了十年工厂管理", "厂子搬到越南，他被优化"]; code, out = check(f, b2)
        errs = [l for l in out.splitlines() if l.startswith("✗")]; want = "brief 里没有"
    report(f"拦下：{name}", code == 1 and any(want in e for e in errs), (errs or ["没报错"])[0][:120])

print("== 4 五种配乐都能合成")
with tempfile.TemporaryDirectory() as d:
    for st in ("drive", "tension", "warm", "lofi", "doc"):
        f = copy.deepcopy(film); f["music"] = {"style": st}; (Path(d) / "f.json").write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
        cues = run("node", SKILL / "scripts/make_cues.mjs", Path(d) / "f.json")
        (Path(d) / "c.json").write_text(cues.stdout, encoding="utf-8")
        r = run("node", SKILL / "scripts/score.mjs", Path(d) / "c.json", Path(d) / f"{st}.wav")
        good = r.returncode == 0 and (Path(d) / f"{st}.wav").stat().st_size > 100000 and json.loads(cues.stdout).get("style") == st
        report(f"合成配乐：{st}", good, (r.stderr or cues.stderr)[-200:])
        if st == "drive":   # 配乐跟着画面走：示例片的岔路、算账、人生节点都该有对应的音
            ev = json.loads(cues.stdout)["events"]; kinds = {e["type"] for e in ev}
            report("配乐跟着画面动作（有条目音、划掉的闷击、断开的碎裂）", {"pluck", "knock", "scratch"} <= kinds and sum(e["type"] in ("pluck", "bell") for e in ev) >= 8, str(sorted(kinds)))
        if st == "drive":   # 听感底线：低音、中频大部分时间铺满（11-18 对标参考 BGM 后定的；原来一下一下的拨弦只有 22–41%）
            import array, math
            def fill(lo, hi):
                raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "8", "-t", "16", "-i", str(Path(d) / "drive.wav"), "-af", f"highpass=f={lo},lowpass=f={hi}", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
                x = array.array("h"); x.frombytes(raw[:len(raw) // 2 * 2]); env = []
                for i in range(0, len(x) - 800, 800):
                    env.append(10 * math.log10(sum(v * v for v in x[i:i + 800:2]) / 400 + 1))
                p95 = sorted(env)[int(len(env) * 0.95)]; return sum(1 for v in env if v > p95 - 10) / len(env)
            fb, fm = fill(40, 150), fill(400, 1000)
            report(f"律动配乐铺得满（低音 {fb:.0%}、中频 {fm:.0%}，要 ≥ 75% / 85%）", fb >= 0.75 and fm >= 0.85)
    if "--quick" not in sys.argv:
        print("== 5 节拍检测量得准（合成一首 120 BPM、前面垫 1.37 秒静音的歌）")
        f = copy.deepcopy(film); f["bpm"] = 120; (Path(d) / "f.json").write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
        (Path(d) / "c.json").write_text(run("node", SKILL / "scripts/make_cues.mjs", Path(d) / "f.json").stdout, encoding="utf-8")
        run("node", SKILL / "scripts/score.mjs", Path(d) / "c.json", Path(d) / "raw.wav")
        run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", "1.37", "-i", "anullsrc=r=48000:cl=stereo", "-i", Path(d) / "raw.wav", "-filter_complex", "concat=n=2:v=0:a=1", Path(d) / "song.wav")
        r = run(PY, SKILL / "scripts/fit_song.py", Path(d) / "song.wav")
        m = re.search(r"([\d.]+) BPM", r.stdout)
        report("量出 120 BPM（误差 < 0.5）", bool(m) and abs(float(m.group(1)) - 120) < 0.5, r.stdout[-200:] or r.stderr[-200:])

if "--quick" not in sys.argv:
    print("== 6 示例拼图：画面体检 0 处")
    with tempfile.TemporaryDirectory() as d:
        run("bash", SKILL / "scripts/new_film.sh", d)
        for x in ("film.json", "brief.json"): (Path(d) / x).write_text((EX / x).read_text(encoding="utf-8"), encoding="utf-8")
        r = run(PY, "-W", "ignore", SKILL / "scripts/frame_qa.py", d, "--json")
        try: qa = json.loads(r.stdout or "null")
        except json.JSONDecodeError: qa = None
        report("frame_qa 0 处", qa == [], (r.stdout or r.stderr)[-300:])

print("== 7 卡点：画面变化和音效都落在鼓点上（教程第 02 / 03 条，calmness 11-18 确认）")
f = copy.deepcopy(film); bpm = f.get("bpm", 112.8); beat = 60 / bpm
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "f.json").write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
    ev = json.loads(run("node", SKILL / "scripts/make_cues.mjs", Path(d) / "f.json").stdout)["events"]
    act = [e for e in ev if e["type"] in ("pluck", "bell", "knock", "tick", "scratch")]
    g = beat / 4   # 节奏格子按十六分音符算：大数字涨跌的上行 / 下行音是十六分音符的一串，本来就在格子上
    off = [e["t"] for e in act if abs(e["t"] / g - round(e["t"] / g)) * g > 0.002]
    report(f"音效踩在拍上（{len(act) - len(off)}/{len(act)}）", len(off) <= 1, str(off[:5]))
if "--quick" not in sys.argv:
    with tempfile.TemporaryDirectory() as d:
        run("bash", SKILL / "scripts/new_film.sh", d)
        for x in ("film.json", "brief.json"): (Path(d) / x).write_text((EX / x).read_text(encoding="utf-8"), encoding="utf-8")
        code = (
            "import sys, io, json\n"
            f"sys.path.insert(0, {str(SKILL / 'engine')!r}); import render\n"
            "from PIL import Image\n"
            f"beat = {beat}; T = beat * 4 * 6\n"   # 前 6 小节
            "def go(pg):\n"
            "    return [Image.open(io.BytesIO(render.shot(pg, k / 30))).convert('L').resize((136, 242)).tobytes() for k in range(int(T * 30))]\n"
            f"fr = render.with_page(__import__('pathlib').Path({d!r}), go)\n"
            "W = 136\n"
            "def dd(i): a, b = fr[i-1], fr[i]; return sum(1 for y in range(30, 180, 2) for x in range(0, W, 2) if abs(a[y*W+x] - b[y*W+x]) > 25)\n"
            "m = [0] + [dd(i) for i in range(1, len(fr))]; st = []\n"
            "for i in range(1, len(fr)):\n"
            "    if m[i] >= 8 and m[i-1] < 4 and (not st or i - st[-1] > 4): st.append(i)\n"
            "on = [i for i in st if abs((i/30/beat - round(i/30/beat)) * beat) <= 0.05]\n"
            "print(len(on), len(st))\n")
        r = run(PY, "-W", "ignore", "-c", code)
        try: a, b = map(int, r.stdout.split()[-2:])
        except ValueError: a, b = 0, 0
        report(f"画面变化落在拍上（前 6 小节 {a}/{b}，要 ≥ 75%，且至少 9 次；标杆样片整片 58%，其余是光点、滚数这类连续动作）", b >= 9 and a >= 0.75 * b, (r.stderr or r.stdout)[-300:])

print(f"\n{'全部通过' if not fail else f'{fail} 项没过'}（{ok} 过 / {fail} 没过）")
sys.exit(1 if fail else 0)
