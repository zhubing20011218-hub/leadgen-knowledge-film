# 示例 01 ·《被裁之后》（30 秒 · 112 BPM · 14 句）

- `brief.json`：访谈结果。**证据里的数字是示例**（`"example": true`），片上每个数字都标「示例」，这条片不能发布。
- `film.json`：`python3 scripts/ds_make.py` 全自动做出来的（deepseek-flash，不开思考）：
  写 → 检查（第一轮 5 个错，改一轮通过）→ 看图评审（13 条意见）→ 按评审改 → 复查通过。共花 ¥0.039（空闲时段）。
  屏上的数全部来自 brief（两百份、两万、10 / 30 / 8 元），没有编出来的数。
- 出片：`bash scripts/new_film.sh <工程>` → 把这两个文件拷进去 → `bash scripts/build.sh <工程>`。
