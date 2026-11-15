# 示例 01 ·《被裁之后》（30 秒 · 112 BPM · 15 句）

- `brief.json`：访谈结果。**证据里的数字是示例**（`"example": true`），所以片上每个数字都标「示例」，这条片不能发布。
- `film.json`：DeepSeek（deepseek-flash，不开思考）读 SKILL.md + references/02、03、06 写出来的，
  跑了三轮 `check_film.py`（第一轮 4 个错：多两句、一句超长、一处数字没出处、断点越界；第二轮 2 个错：相邻两章同色、「不用本钱」），
  第三轮通过；之后按两条警告手动删了 bars 里写成单位的 tag 和 steps 里只写编号的 note。
- 出片：`bash scripts/new_film.sh <工程>` → 把这两个文件拷进去 → `bash scripts/build.sh <工程>`。
