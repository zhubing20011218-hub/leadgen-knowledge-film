# -*- coding: utf-8 -*-
"""出封面：python3 scripts/cover.py <工程>  → <工程>/renders/封面.jpg（1080×1920）
上面是片名大字（film.json 的 title，下面一行是 post.cover，没写就用开场章的 key），下面是开场那一章演完的画面。
抖音 / 视频号选封面时用它：信息流里先看到的是封面，不是第一帧。"""
import io, json, sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL / "engine"))
import render  # noqa: E402

proj = Path(sys.argv[1]).expanduser().resolve()
f = json.loads((proj / "film.json").read_text(encoding="utf-8"))
bar = 60 / (f.get("bpm") or 112) * 4; first = len((f.get("chapters") or [{}])[0].get("lines") or [1])
t = (f.get("phase") or 0) + (first - 1 + 0.85) * bar          # 开场章最后一句播到 85%：东西都出齐了

def go(pg):
    pg.evaluate("window.COVER = true"); png = render.shot(pg, t); pg.evaluate("window.COVER = false"); return png

from PIL import Image  # noqa: E402
(proj / "renders").mkdir(exist_ok=True)
Image.open(io.BytesIO(render.with_page(proj, go))).convert("RGB").save(proj / "renders/封面.jpg", quality=90)
print(f"封面：{proj / 'renders/封面.jpg'}")
