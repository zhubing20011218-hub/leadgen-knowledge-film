# 第三方代码与字体

本仓库自己的代码按 `LICENSE`（MIT）授权；下面这些来自别的开源项目，各按原协议：

| 文件 | 来源 | 协议 | 说明 |
|---|---|---|---|
| `engine/vk.js` `engine/vk-kit.js` `engine/render.py` `engine/audio.py` `engine/get_fonts.py` `engine/index.html` | [HeyChengC/vibe-knowledge-film](https://github.com/HeyChengC/vibe-knowledge-film) 的渲染引擎 | MIT（全文 `engine/LICENSE-vibe-knowledge-film`） | 改成竖屏 1080×1920，加了暖黑背景 |
| `scripts/score.mjs` | [8533502-dev/deepseek-opus-motion-skill](https://github.com/8533502-dev/deepseek-opus-motion-skill) 的 `templates/remotion-starter/scripts/score.mjs`，Copyright (c) 2026 阿宁Neo | MIT（全文 `scripts/LICENSE-score.mjs.txt`） | 有改动：可以多传一个参数把结果写到指定文件；新增 `chord`（厚和弦）、`bass`（持续贝斯）、`piano`（钢琴柱式和弦）三件乐器，都可以带抽吸；原有乐器和合成算法未改 |
| `template/lucide.js` `scripts/icon_index.json` 里的 `tags` | [lucide-icons/lucide](https://github.com/lucide-icons/lucide) 的 `lucide-static@0.469.0`（`icon-nodes.json`、`tags.json`），Copyright (c) Lucide Contributors 2022；部分图标来自 Feather，Copyright (c) Cole Bemis 2013-2022 | ISC（Feather 部分为 MIT；全文 `template/LICENSE-lucide.txt`） | 只把 SVG 元素换算成路径，图标本身未改；由 `tools/build_icons.py` 生成。`icon_index.json` 里的中文词表是本仓库自己写的 |
| `engine/fonts/*`（不在仓库里，`engine/get_fonts.py` 下载） | [google/fonts](https://github.com/google/fonts) | SIL OFL 1.1（各字体的 OFL 文本随字体下载） | 思源黑体、思源宋体等 |

仓库里没有任何第三方音乐；配乐全部由 `scripts/score.mjs` 现场合成。
