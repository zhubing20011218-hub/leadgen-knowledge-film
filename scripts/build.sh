#!/usr/bin/env bash
# 一条命令出片：检查 → 配乐 → 渲画面 → 混音（-14 LUFS）→ 写入 AI 生成标记 → 拼图自查
#   bash scripts/build.sh <工程目录> [--sheet-only 只出拼图 | --remix 只重新配乐混音、不重渲画面]
# 需要：python3（装了 playwright 和 pillow）、node、ffmpeg、本机 Chrome。缺什么会直接告诉你。
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
P="$(cd "${1:?用法: bash scripts/build.sh <工程目录>}" && pwd)"
PY="${PYTHON:-python3}"
$PY -c "import playwright, PIL" 2>/dev/null || { echo "缺 Python 依赖：$PY -m pip install playwright pillow（或者用 PYTHON=<装好的 python> 指定）"; exit 2; }
command -v node >/dev/null || { echo "缺 node"; exit 2; }
command -v ffmpeg >/dev/null || { echo "缺 ffmpeg"; exit 2; }
$PY "$SKILL/engine/get_fonts.py" --check >/dev/null || $PY "$SKILL/engine/get_fonts.py"

BRIEF=""; [ -f "$P/brief.json" ] && BRIEF="$P/brief.json"
echo "== 1/5 检查 film.json"
$PY "$SKILL/scripts/check_film.py" "$P/film.json" $BRIEF
if [ "${2:-}" = "--sheet-only" ]; then $PY "$SKILL/engine/render.py" "$P" --sheet 16; exit 0; fi

echo "== 2/5 配乐（按片子结构合成，卡在小节线上）"
mkdir -p "$P/scripts" "$P/public"
cp "$SKILL/scripts/score.mjs" "$P/scripts/score.mjs"
node "$SKILL/scripts/make_cues.mjs" "$P/film.json" > "$P/scripts/cues.json"
node "$P/scripts/score.mjs" "$P/scripts/cues.json"

echo "== 3/5 渲画面"
if [ "${2:-}" = "--remix" ] && [ -f "$P/renders/raw.mp4" ]; then echo "沿用 renders/raw.mp4"; else $PY "$SKILL/engine/render.py" "$P" --jobs 4; fi

echo "== 4/5 混音到 -14 LUFS、真峰 ≤ -1 dBTP，写入 AI 生成标记"
[ "${2:-}" = "--remix" ] && echo "（只重新混音，不重渲画面）"
# 合成鼓点峰值很尖：先压峰值，再提到 -14 LUFS，最后留 1 dB 给 AAC 编码的过冲（11-15 实测：只做 loudnorm 真峰会到 0 dB）
MIX="alimiter=limit=0.4:level=false:attack=1:release=60,loudnorm=I=-14:TP=-2:LRA=11,alimiter=limit=0.79:level=false:attack=1:release=60,aresample=48000"
NAME="$($PY -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8')).get('title') or 'film')" "$P/film.json")"
OUT="$P/renders/${NAME}.mp4"
ffmpeg -v error -y -i "$P/renders/raw.mp4" -i "$P/public/score.wav" \
  -af "$MIX" -c:v copy -c:a aac -b:a 192k -shortest \
  -metadata comment="AIGC: 本视频由 AI 辅助生成" -metadata description="AI-generated content" -movflags +faststart "$OUT"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | tr -s ' ' | sed 's/^/   /'

echo "== 5/5 拼图自查 → $P/review/sheet.jpg"
$PY "$SKILL/engine/render.py" "$P" --sheet 16
echo "成片：$OUT"
echo "发布时记得打开平台的「AI 生成内容」声明。"
