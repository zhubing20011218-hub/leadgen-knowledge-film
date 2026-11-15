#!/usr/bin/env bash
# 第一次用跑一次：在技能目录建一个自己的 Python 环境（.venv，不进 git），装 playwright + pillow，下载字体。
# 装好后 build.sh / ds_make.py 会自动用它，不用再管 PYTHON。
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
command -v python3 >/dev/null || { echo "缺 python3"; exit 2; }
command -v node >/dev/null || echo "缺 node（合成配乐要用）：macOS 用 brew install node"
command -v ffmpeg >/dev/null || echo "缺 ffmpeg（压视频要用）：macOS 用 brew install ffmpeg"
[ -x "$SKILL/.venv/bin/python" ] || python3 -m venv "$SKILL/.venv"
"$SKILL/.venv/bin/python" -m pip install -q --upgrade pip
"$SKILL/.venv/bin/python" -m pip install -q "playwright>=1.45" "pillow>=10"
if [ ! -d "/Applications/Google Chrome.app" ] && ! command -v google-chrome >/dev/null; then
  echo "没找到 Chrome，下载 playwright 自带的 Chromium（约 150MB）"; "$SKILL/.venv/bin/python" -m playwright install chromium
fi
"$SKILL/.venv/bin/python" "$SKILL/engine/get_fonts.py"
"$SKILL/.venv/bin/python" "$SKILL/scripts/env_check.py"
