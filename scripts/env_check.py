# -*- coding: utf-8 -*-
"""看清运行环境：在哪个 AI 助手里、出片要的东西齐不齐、该用哪种方式跑。
  python3 scripts/env_check.py          只检查
  python3 scripts/env_check.py --json   输出机器可读的结果（给脚本用）
不打印任何钥匙的内容，只说有没有。"""
import json, os, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent


def agent():
    e = os.environ
    if e.get("DSH_SESSION_ID") or e.get("DSH_HOME") or e.get("DSH_PROFILE"):
        return "dsh", "DeepSeek Harness", "用 read_image 打开 review/sheet.jpg 自己看"
    if e.get("CLAUDECODE") or e.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude", "Claude Code", "用 Read 打开 review/sheet.jpg 自己看"
    if any(k.startswith("CODEX_") for k in e):
        return "codex", "Codex", "用 view_image 打开 review/sheet.jpg 自己看"
    if e.get("CURSOR_TRACE_ID") or e.get("CURSOR_AGENT"):
        return "cursor", "Cursor", "能看图就自己看 review/sheet.jpg，不能就跑 python3 scripts/ds_make.py <工程> --review-only"
    return "unknown", "没认出来（可能是别的助手或者终端）", "能看图就自己看 review/sheet.jpg，不能就跑 python3 scripts/ds_make.py <工程> --review-only"


def find_python():
    cands = [os.environ.get("PYTHON"), str(SKILL / ".venv/bin/python"), "python3", "python"]
    for c in cands:
        if not c: continue
        p = shutil.which(c) or (c if Path(c).exists() else None)
        if not p: continue
        ok = subprocess.run([p, "-c", "import playwright, PIL"], capture_output=True).returncode == 0
        if ok: return p
    return None


def has_key():
    if os.environ.get("DEEPSEEK_API_KEY"): return "环境变量"
    f = SKILL / ".env"
    if f.exists() and "DEEPSEEK_API_KEY=" in f.read_text(encoding="utf-8", errors="ignore"): return "技能目录 .env"
    return None


def chrome():
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    return Path(mac).exists() or bool(shutil.which("google-chrome") or shutil.which("chrome") or shutil.which("chromium"))


def main():
    a = agent(); py = find_python(); key = has_key()
    fonts = (SKILL / "engine/fonts/NotoSansSC-VF.ttf").exists()
    r = {
        "agent": a[0], "agent_name": a[1], "look": a[2],
        "python": py, "node": shutil.which("node"), "ffmpeg": shutil.which("ffmpeg"), "chrome": chrome(),
        "fonts": fonts, "deepseek_key": key,
    }
    missing = [n for n, ok in (("python 依赖（playwright + pillow）", py), ("node", r["node"]), ("ffmpeg", r["ffmpeg"]), ("字体", fonts)) if not ok]
    r["ready"] = not missing
    if "--json" in sys.argv: print(json.dumps(r, ensure_ascii=False)); return
    print(f"运行环境：{a[1]}")
    print(f"  看拼图：{a[2]}")
    print(f"  python（带 playwright）：{py or '没有'}　node：{'有' if r['node'] else '没有'}　ffmpeg：{'有' if r['ffmpeg'] else '没有'}　Chrome：{'有' if r['chrome'] else '没有（会用 playwright 自带的 Chromium）'}　字体：{'齐' if fonts else '缺'}")
    print(f"  DeepSeek 钥匙：{key or '没有（只有 scripts/ds_make.py 需要它）'}")
    if missing: print("缺：" + "、".join(missing) + "　→ 跑一次 bash scripts/setup.sh")
    print("怎么跑：")
    if a[0] in ("dsh", "claude", "codex", "cursor"):
        print("  你就是写 film.json 的那个模型：照 SKILL.md 先问需求，写 film.json，bash scripts/build.sh <工程> --sheet-only，看拼图，改，再出整片。")
        print("  想省事也可以：python3 scripts/ds_make.py <工程>（全程交给 DeepSeek 接口自动写、查、看、改）。")
    else:
        print("  python3 scripts/ds_make.py <工程>（需要 DeepSeek 钥匙）；或者在 DeepSeek Harness / Claude Code 里装这个技能，让助手来做。")


if __name__ == "__main__":
    main()
