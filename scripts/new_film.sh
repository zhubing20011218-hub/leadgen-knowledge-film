#!/usr/bin/env bash
# 从模板建一个片子工程：bash scripts/new_film.sh ~/Desktop/film-被裁之后
# 需要：ENGINE 指向竖屏渲染引擎目录（默认 ~/opus5.5-video/film/engine，已改 1080×1920）
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:?用法: bash scripts/new_film.sh <目标目录>}"
ENGINE="${ENGINE:-$HOME/opus5.5-video/film/engine}"

[ -d "$ENGINE" ] || { echo "找不到渲染引擎：$ENGINE（用 ENGINE=... 指定）"; exit 1; }
mkdir -p "$DEST"/{renders,review,audio,public,scripts}
[ -e "$DEST/engine" ] || ln -s "$ENGINE" "$DEST/engine"

cp "$SKILL/assets/film-template/palette.js" "$DEST/palette.js"
cp "$SKILL/assets/film-template/film.js"    "$DEST/film.js"
cp "$SKILL/assets/film-template/scenes.js"  "$DEST/scenes.js"
cp "$SKILL/assets/film-template/index.html" "$DEST/index.html"
cp "$SKILL/assets/score.mjs"                "$DEST/scripts/score.mjs"
cp "$SKILL/assets/cues-120.json"            "$DEST/cues.json"

echo "建好了：$DEST"
echo "下一步："
echo "  1) 改 film.js 里的 GRID（BPM / PHASE / 段落小节号）和 SUBS（字幕）"
echo "  2) python3 engine/render.py $DEST --stills 3 7 13 19 25"
echo "  3) node $DEST/scripts/score.mjs $DEST/cues.json   → public/score.wav"
echo "  4) python3 engine/render.py $DEST --jobs 4"
