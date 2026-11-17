# -*- coding: utf-8 -*-
"""写「发布说明」：发布标题、话题、封面、要打开的声明、配乐（想换平台曲库的歌怎么搜、怎么对齐）。
  python3 scripts/publish_note.py <工程>      build.sh 出片时自动写到 renders/发布说明.txt
配乐部分不推荐具体歌名：平台热歌每周都在变，名字写死了会过时，也容易让人以为能把歌合进文件里。"""
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
try: b = json.loads((proj / "brief.json").read_text(encoding="utf-8"))
except Exception: b = {}
try: style = json.loads((proj / "scripts/cues_sfx.json").read_text(encoding="utf-8")).get("style", "drive")
except Exception: style = "drive"
bpm = f.get("bpm", 112); bar = 240 / bpm; n = sum(len(c.get("lines") or []) for c in f.get("chapters") or [])
name, kw = STYLE.get(style, STYLE["drive"]); m = f.get("music") or {}; post = f.get("post") or {}
title = f.get("title") or "film"
tags = " ".join("#" + str(x).lstrip("#＃ ") for x in post.get("tags") or [])
used = f"你的歌《{Path(m['song']).name}》，从 {m.get('start', 0):.2f} 秒那一拍起" if m.get("song") else f"技能合成的配乐（风格：{name}），可以直接发，没有版权问题"
warn = "\n⚠ 这条片的数字是示例（brief 里写了 example: true），只能自己看，不能发布。\n" if b.get("example") else ""
print(f"""《{title}》发布说明{warn}
== 发布
视频：{title}.mp4（{n} 句，{n * bar:.0f} 秒）
封面：封面.jpg（在 App 里「选封面」→ 从相册选这张；信息流里先看到的是封面，不是第一帧）
标题：{post.get('title') or '（film.json 没写 post.title，自己写一句：让人想点开、只用真实的事和数）'}
话题：{tags or '（film.json 没写 post.tags，加 3–5 个）'}
发布前：打开平台的「AI 生成内容」声明（作者服务中心 / 发布页的高级设置里）；不在标题、评论里留联系方式

== 配乐
速度 {bpm} BPM · 一句字幕一小节 {bar:.2f} 秒 · 第一句从第 0 秒开始，正好是一小节的第一拍
现在用的配乐：{used}

想换成抖音 / 剪映曲库里的歌（平台曲库的歌有授权，只能在 App 里加；把热歌合进视频文件再发，会被判版权、静音或限流）：
1. 用「{title}-配平台音乐用.mp4」这一版：里面只有卡点音效（换章、片名、反转、盖章、片尾），没有音乐
2. 搜：{kw}；挑速度接近 {round(bpm)} BPM 的（剪映选中音乐后点「踩点」能看到节拍点；拿不准就挑鼓点稳、没有人声的纯音乐）
3. 把歌的第一记重拍对到视频第 0 秒；之后每 {bar:.2f} 秒换一句，换句的地方应该正好踩在重拍上
4. 原声（卡点音效）音量留 50%–70%，音乐 30%–50%：字幕换句那一下还能听到「咚」

想用自己有授权的歌（自己做的、买了授权的、免版税曲库下载的），卡点自动对齐：
  python3 scripts/fit_song.py {proj} <歌或放歌的文件夹> --licensed   然后重新 bash scripts/build.sh {proj}""")
