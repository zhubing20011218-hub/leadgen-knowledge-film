#!/usr/bin/env bash
# 一条命令出片：检查 → 配乐 → 渲画面 → 混音（-14 LUFS）→ 写入 AI 生成标记 → 拼图自查
#   bash scripts/build.sh <工程目录> [--sheet-only 只出拼图 | --remix 只重新配乐混音、不重渲画面 | --update-template 先换成最新模板]
# 需要：python3（装了 playwright 和 pillow）、node、ffmpeg、本机 Chrome。缺什么会直接告诉你。
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
P="$(cd "${1:?用法: bash scripts/build.sh <工程目录>}" && pwd)"
PY="${PYTHON:-}"; [ -z "$PY" ] && [ -x "$SKILL/.venv/bin/python" ] && PY="$SKILL/.venv/bin/python"; PY="${PY:-python3}"
shift; SHEET=0; REMIX=0; UPD=0   # 开关不分先后，可以一起用（11-16 修：原来 --update-template 会把后面的 --sheet-only 吃掉，变成整片渲染）
for a in "$@"; do case "$a" in --sheet-only) SHEET=1;; --remix) REMIX=1;; --update-template) UPD=1;; *) echo "不认识的参数：$a"; exit 2;; esac; done
$PY -c "import playwright, PIL" 2>/dev/null || { echo "缺 Python 依赖：先跑一次 bash $SKILL/scripts/setup.sh"; exit 2; }
command -v node >/dev/null || { echo "缺 node"; exit 2; }
command -v ffmpeg >/dev/null || { echo "缺 ffmpeg"; exit 2; }
$PY "$SKILL/engine/get_fonts.py" --check >/dev/null || $PY "$SKILL/engine/get_fonts.py"

# 工程里的模板是建工程时拷的；技能升级后旧工程不会自己变。--update-template 换成技能里最新的（工程里自己写的件会被覆盖）
if [ "$UPD" = 1 ]; then cp "$SKILL/template/"{index.html,palette.js,icons.js,film.js,scenes.js} "$P/"; echo "模板已换成技能里最新的"; fi
for f in index.html palette.js icons.js film.js scenes.js; do
  cmp -s "$SKILL/template/$f" "$P/$f" || { echo "提醒：$P/$f 和技能里的模板不一样（技能升级过，或者你改过）。要换成最新的：bash $SKILL/scripts/build.sh $P --update-template"; break; }
done
BRIEF=""; [ -f "$P/brief.json" ] && BRIEF="$P/brief.json"
echo "== 1/5 检查 film.json"
$PY "$SKILL/scripts/check_film.py" "$P/film.json" $BRIEF
TIMES="$(python3 "$SKILL/scripts/sheet_times.py" "$P/film.json")"   # 每句播到一半的那一帧，不截在换句的瞬间
if [ "$SHEET" = 1 ]; then $PY "$SKILL/engine/render.py" "$P" --sheet $TIMES; exit 0; fi

echo "== 2/5 配乐（卡在小节线上）"
mkdir -p "$P/scripts" "$P/public" "$P/renders"
cp "$SKILL/scripts/score.mjs" "$P/scripts/score.mjs"
# 卡点音效（换章、片名、反转、盖章、片尾）单独一层：叠在你的歌上面，也单独给「配平台音乐用」那一版
node "$SKILL/scripts/make_cues.mjs" "$P/film.json" --sfx-only > "$P/scripts/cues_sfx.json"
node "$P/scripts/score.mjs" "$P/scripts/cues_sfx.json" "$P/public/sfx.wav" >/dev/null
IFS=$'\x1f' read -r SONG START DUR STYLE < <(python3 -c "
import json,sys; f=json.load(open(sys.argv[1],encoding='utf-8')); c=json.load(open(sys.argv[2],encoding='utf-8')); m=f.get('music') or {}
print(m.get('song',''), m.get('start',0), c['duration'], c.get('style',''), sep=chr(31))" "$P/film.json" "$P/scripts/cues_sfx.json")
if [ -n "$SONG" ]; then
  [ -f "$SONG" ] || { echo "film.json 的 music.song 指向的歌不存在：$SONG（重跑 scripts/fit_song.py，或删掉 music.song 改用合成配乐）"; exit 2; }
  echo "用你的歌：$(basename "$SONG")，从 ${START} 秒起，卡点音效叠在上面"
  FADE=$(python3 -c "print(max(0, $DUR - 1.5))")
  ffmpeg -v error -y -ss "$START" -t "$DUR" -i "$SONG" -i "$P/public/sfx.wav" -filter_complex \
    "[0]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.04,afade=t=out:st=$FADE:d=1.5[s];[1]volume=0.5[x];[s][x]amix=inputs=2:normalize=0:duration=first" \
    -c:a pcm_s16le "$P/public/score.wav"
else
  node "$SKILL/scripts/make_cues.mjs" "$P/film.json" > "$P/scripts/cues.json"
  node "$P/scripts/score.mjs" "$P/scripts/cues.json"
fi

echo "== 3/5 渲画面"
if [ "$REMIX" = 1 ] && [ -f "$P/renders/raw.mp4" ]; then echo "沿用 renders/raw.mp4"; else $PY "$SKILL/engine/render.py" "$P" --jobs 4; fi

echo "== 4/5 混音到 -14 LUFS、真峰 ≤ -1 dBTP，写入 AI 生成标记"
[ "$REMIX" = 1 ] && echo "（只重新混音，不重渲画面）"
# 合成鼓点峰值很尖：先压峰值，再提到 -14 LUFS，最后留 1 dB 给 AAC 编码的过冲（11-15 实测：只做 loudnorm 真峰会到 0 dB）
MIX="alimiter=limit=0.4:level=false:attack=1:release=60,loudnorm=I=-14:TP=-2:LRA=11,alimiter=limit=0.79:level=false:attack=1:release=60,aresample=48000"
[ -n "$SONG" ] && MIX="loudnorm=I=-14:TP=-3:LRA=11,alimiter=limit=0.68:level=false:attack=1:release=60,aresample=48000"   # 成品歌已经混过音，不再先压一道；歌比合成配乐密，AAC 编码后峰值冲得更高，多留 1 dB   # 成品歌已经混过音，不再先压一道
NAME="$($PY -c "import json,sys; print(json.load(open(sys.argv[1],encoding='utf-8')).get('title') or 'film')" "$P/film.json")"
OUT="$P/renders/${NAME}.mp4"
mux() {   # $1 = 额外的音量修正（dB）
  ffmpeg -v error -y -i "$P/renders/raw.mp4" -i "$P/public/score.wav" \
    -af "$MIX,volume=${1}dB" -c:v copy -c:a aac -b:a 192k -shortest \
    -metadata comment="AIGC: 本视频由 AI 辅助生成" -metadata description="AI-generated content" -movflags +faststart "$OUT"
}
measure() { ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | python3 -c "import sys,re; s=sys.stdin.read(); i=re.findall(r'I:\s+(-?[\d.]+) LUFS', s)[-1]; p=re.findall(r'Peak:\s+(-?[\d.]+) dBFS', s)[-1]; print(i, p)"; }
# 第一遍混完实测，再按差多少修正一次：响度对到 -14 LUFS，真峰不超过 -1.2 dBFS（AAC 编码会让峰值冲高一点，所以留余量）
mux 0; read I PK < <(measure)
G=$(python3 -c "print(round(min(-14 - $I, -1.2 - $PK), 2))")
mux "$G"; read I PK < <(measure)
if python3 -c "import sys; sys.exit(0 if $PK > -1.2 else 1)"; then   # 真峰还超：再往下压一点，宁可响度低一点点
  G=$(python3 -c "print(round($G + (-1.3 - $PK), 2))"); mux "$G"; read I PK < <(measure)
fi
echo "    响度 $I LUFS · 真峰 $PK dBFS（修正 ${G} dB）"
# 「配平台音乐用」：只有卡点音效、没有音乐。想用抖音 / 剪映曲库里的热歌（有平台授权，合进文件里发会被判版权），用这一版在 App 里加歌
PLAT="$P/renders/${NAME}-配平台音乐用.mp4"
ffmpeg -v error -y -i "$P/renders/raw.mp4" -i "$P/public/sfx.wav" -af "loudnorm=I=-18:TP=-2,aresample=48000" -c:v copy -c:a aac -b:a 160k -shortest \
  -metadata comment="AIGC: 本视频由 AI 辅助生成" -metadata description="AI-generated content" -movflags +faststart "$PLAT"
python3 "$SKILL/scripts/music_note.py" "$P" > "$P/renders/配乐说明.txt"
echo "    另出了一版只有卡点音效的：$PLAT（配乐说明：$P/renders/配乐说明.txt）"

echo "== 5/5 拼图自查 → $P/review/sheet.jpg"
$PY "$SKILL/engine/render.py" "$P" --sheet $TIMES
echo "成片：$OUT"
echo "发布时记得打开平台的「AI 生成内容」声明。"
