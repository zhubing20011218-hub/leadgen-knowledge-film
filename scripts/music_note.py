# -*- coding: utf-8 -*-
"""写「配乐说明」：这条片用的什么配乐、想换成平台曲库里的歌该搜什么、怎么对齐。build.sh 出片时自动写到 renders/配乐说明.txt。
  python3 scripts/music_note.py <工程>
不推荐具体的歌名：平台热歌每周都在变，名字写死了会过时，也容易让人以为能把歌合进文件里。"""
import json, sys
from pathlib import Path

STYLE = {   # 风格 → 给人看的名字、去曲库搜什么
    "drive": ("律动", "知识科普 BGM、卡点 电子 律动、纯音乐 鼓点"),
    "tension": ("紧张", "紧张 悬疑 鼓点、热血 卡点、纯音乐 快节奏"),
    "warm": ("温暖", "温暖 治愈 钢琴、轻快 吉他、纯音乐 温柔"),
    "lofi": ("轻松", "lofi 轻松、咖啡馆 爵士、纯音乐 慵懒"),
}

proj = Path(sys.argv[1]).expanduser()
f = json.loads((proj / "film.json").read_text(encoding="utf-8"))
try: style = json.loads((proj / "scripts/cues_sfx.json").read_text(encoding="utf-8")).get("style", "drive")
except Exception: style = "drive"
bpm = f.get("bpm", 112); bar = 240 / bpm; n = sum(len(c.get("lines") or []) for c in f.get("chapters") or [])
name, kw = STYLE.get(style, STYLE["drive"]); m = f.get("music") or {}
title = f.get("title") or "film"
used = f"你的歌《{Path(m['song']).name}》，从 {m.get('start', 0):.2f} 秒那一拍起" if m.get("song") else f"技能合成的配乐（风格：{name}），可以直接发，没有版权问题"
print(f"""这条片：{title}
速度 {bpm} BPM · 一句字幕一小节 {bar:.2f} 秒 · {n} 句 · 第一句从第 0 秒开始，正好是一小节的第一拍
现在用的配乐：{used}

想换成抖音 / 剪映曲库里的歌（平台曲库的歌有授权，只能在 App 里加；把热歌合进视频文件再发，会被判版权、静音或限流）：
1. 用「{title}-配平台音乐用.mp4」这一版：里面只有卡点音效（换章、片名、反转、盖章、片尾），没有音乐
2. 搜：{kw}；挑速度接近 {round(bpm)} BPM 的（剪映选中音乐后点「踩点」能看到节拍点；拿不准就挑鼓点稳、没有人声的纯音乐）
3. 把歌的第一记重拍对到视频第 0 秒；之后每 {bar:.2f} 秒换一句，换句的地方应该正好踩在重拍上
4. 原声（卡点音效）音量留 50%–70%，音乐 30%–50%：字幕换句那一下还能听到「咚」
5. 发布时打开平台的「AI 生成内容」声明

想用自己有授权的歌（自己做的、买了授权的、免版税曲库下载的），卡点自动对齐：
  python3 scripts/fit_song.py {proj} <歌或放歌的文件夹> --licensed   然后重新 bash scripts/build.sh {proj}""")
