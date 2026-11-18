#!/usr/bin/env bash
# 从模板建一个片子工程：bash scripts/new_film.sh ~/Desktop/知识短片/被裁之后
# 工程里只有自己的东西（brief.json、film.json、成片）；引擎和字体留在技能目录，render.py 自己挂进来。
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:?用法: bash scripts/new_film.sh <目标目录>}"
[ -e "$DEST/film.json" ] && { echo "$DEST 里已经有 film.json，不覆盖"; exit 1; }
mkdir -p "$DEST"/{renders,review,scripts}
cp "$SKILL/template/"*.html "$SKILL/template/"*.js "$DEST/"   # 模板里的文件全拷（以后加了新文件也不会漏）
cp "$SKILL/scripts/score.mjs" "$DEST/scripts/score.mjs"
[ -e "$DEST/brief.json" ] || cp "$SKILL/examples/01-被裁之后/brief.json" "$DEST/brief.json"
echo "建好了：$DEST"
echo "下一步：把访谈答案写进 $DEST/brief.json，按 references/03 写 $DEST/film.json，然后"
echo "  bash $SKILL/scripts/build.sh $DEST"
