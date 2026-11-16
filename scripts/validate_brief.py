#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验一轮访谈结果（brief.json）。不过就不许开工。

用法：
  python3 scripts/validate_brief.py examples/01-被裁之后/brief.json
退出码 0 = 可以进第 1 步；1 = 有错，按「怎么改」改完再交。

brief.json 字段：
  angle      laid-off | pivot-list | ai-ecommerce | own-mistake | custom（用户自己定的结构）
  outlet     出路：片子最后把观众引向哪个方向（默认「跨境电商」，也可以是用户自己的业务 / 一门技能）
  audience   给谁看（一句话，≤30 字）
  pain       处境三句（每条 ≤30 字，必须有具体年龄/岗位/事件）
  proof      证据 2–4 条（每条 ≤40 字，最好 2 条带数字；没有数字就讲流程和坑）
  hook       可选：开场钩子（references/02 钩子表第一列的名字，如「人生剧本」）；不写就按题材自动挑
  example    true = 这些数字是编的示例（只能用来试做，片上一律标「示例」，不能发布）
  cta        下一步（主页合集 / 评论区 / 收藏）
  seconds    30 | 60 | 90
  mood       steady（默认 112 BPM，和标杆样片同速）| tight（128，紧张）| calm（100，舒缓）
  banned     不出现的说法（数组，可空）
"""
import json
from pathlib import Path
import re
import sys

ANGLES = {
    'laid-off': ('A 被裁之后', '断裂 → 分叉 → 收窄 → 出路', '自己的店 + 真实订单'),
    'pivot-list': ('B 转行盘点', '把 5 条路摊开比门槛', '公开规则 + 成本结构'),
    'ai-ecommerce': ('C 电商+AI', 'AI 复刻「互联网+」的路径', '自己用 AI 干的活'),
    'own-mistake': ('D 我的弯路', '我亏在哪 → 正确算法', '真实亏损数据'),
    'custom': ('自定结构', '用户和我商量出来的结构', '按结构定'),
}
MOODS = {'steady': ('稳（默认）', 112), 'tight': ('紧张', 128), 'calm': ('舒缓', 100)}
SECONDS = (30, 60, 90)

BANNED_WORDS = (
    '微信', '加微', 'QQ', '私信发', '扫码', '手机号', '二维码',
    '月入', '稳赚', '包赚', '包教包会', '回本', '躺赚',
    '最便宜', '全网最低', '第一品牌', '永久', '保证', '绝对',
)


def has_digit(s):
    # 阿拉伯数字或中文数字都算（"两万块"也是数字）
    return bool(re.search(r'\d', s)) or bool(re.search(r'[零一二两三四五六七八九十百千万亿]', s))


def has_person_marker(s):
    return bool(re.search(r'岁|年|工厂|厂子|公司|部门|岗位|店|毕业|结婚|孩子|房贷|工资|裁员|被优化|辞退|失业|简历|打工|上班', s))


def check(b):
    errs, warns = [], []

    if b.get('angle') not in ANGLES:
        errs.append(f'angle 必须是这四个之一：{", ".join(ANGLES)}')

    aud = (b.get('audience') or '').strip()
    if not (2 <= len(aud) <= 30):
        errs.append(f'audience 要 2–30 字（现在 {len(aud)} 字）')

    pain = b.get('pain') or []
    if not (2 <= len(pain) <= 4):
        errs.append(f'pain（处境）要 2–4 句（现在 {len(pain)} 句）')
    concrete = 0
    for i, p in enumerate(pain, 1):
        if len(p) > 30:
            errs.append(f'pain 第 {i} 句超过 30 字（现在 {len(p)} 字）')
        if has_person_marker(p) or has_digit(p): concrete += 1
        else: warns.append(f'pain 第 {i} 句有点抽象（「{p}」）：最好写出具体的时间、数字或发生了什么')
    if pain and concrete < min(2, len(pain)):
        errs.append('pain（处境）至少 2 句要具体：年龄、岗位、多久、多少钱、发生了什么（例：「38 岁，做了十年工厂管理」）')

    proof = b.get('proof') or []
    if not (2 <= len(proof) <= 4):
        errs.append(f'proof（证据）要 2–4 条（现在 {len(proof)} 条）')
    for i, p in enumerate(proof, 1):
        if len(p) > 40:
            errs.append(f'proof 第 {i} 条超过 40 字（现在 {len(p)} 字）')
    if sum(1 for p in proof if has_digit(p)) < 2:
        warns.append('proof 带数字的不到 2 条：这条片改讲流程和坑，不硬上百分比')
    if not (b.get('outlet') or '').strip():
        errs.append('outlet（出路）不能空：片子最后把观众引到哪个方向？默认填「跨境电商」')
    HOOKS = ('熟悉的场景', '人生剧本', '反常识的数', '先让他选', '一句扎心的话', '前后对比', '一大堆', '结局先说')
    if b.get('hook') and b['hook'] not in HOOKS:
        errs.append(f'hook「{b["hook"]}」不认识，只能是：' + ' '.join(HOOKS) + '（或不写）')
    mu = b.get('music') or {}
    if mu and not isinstance(mu, dict): errs.append('music 要写成 {"style": "drive"} 或 {"song": "歌的路径"}（用歌先跑 scripts/fit_song.py）')
    elif mu.get('style') and mu['style'] not in ('drive', 'tension', 'warm', 'lofi'):
        errs.append(f'music.style「{mu["style"]}」不认识，只能是：drive（律动）tension（紧张）warm（温暖）lofi（轻松）')
    elif mu.get('song') and not Path(str(mu['song'])).expanduser().exists():
        errs.append(f'music.song 指向的歌不存在：{mu["song"]}')
    if b.get('example'):
        warns.append('example = true：数字是编的，只能试做；片上每个数字都要标「示例」，这条片不能发布')

    if not (b.get('cta') or '').strip():
        errs.append('cta（下一步）不能空：主页合集 / 评论区 / 收藏')

    if b.get('seconds') not in SECONDS:
        errs.append('seconds 只能是 30 / 60 / 90')
    if b.get('mood') not in MOODS:
        errs.append('mood 只能是 steady / tight / calm')

    text = ' '.join([aud] + list(pain) + list(proof) + [str(b.get('cta', ''))])
    for w in BANNED_WORDS:
        if w in text:
            errs.append(f'出现违规说法「{w}」（见 references/06-合规红线.md）')
    for w in b.get('banned') or []:
        if w and w in text:
            errs.append(f'踩到用户自己的禁用词「{w}」')

    if b.get('seconds') == 90 and len(proof) < 3:
        warns.append('90 秒建议给 3 条以上证据，否则中段会空')
    if b.get('angle') == 'own-mistake' and not any('亏' in p or '赔' in p for p in proof):
        warns.append('D 我的弯路：最好有一条"我自己亏了多少"的证据')
    if b.get('angle') == 'ai-ecommerce' and not any('AI' in p or 'ai' in p for p in proof):
        warns.append('C 电商+AI：需要一条"我自己用 AI 干了什么"的证据')

    return errs, warns


def plan(b):
    name, arc, need = ANGLES[b['angle']]
    mood, bpm = MOODS[b['mood']]
    sec = b['seconds']
    bar = 60 / bpm * 4
    return [
        f'角度：{name}    叙事：{arc}    关键证据：{need}',
        f'配乐：{mood} {bpm} BPM    时长：{sec} 秒 = {round(sec / bar)} 句字幕（一句一小节 {bar:.2f} 秒）',
        f'出路：{b.get("outlet")}',
        f'出口：{b["cta"]}（不出联系方式）',
    ]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    b = json.load(open(sys.argv[1], encoding='utf-8'))
    errs, warns = check(b)
    name = ANGLES.get(b.get('angle'), ('?', '', ''))[0]
    print(f'文件：{sys.argv[1]}')
    print(f'角度：{name}    情绪：{MOODS.get(b.get("mood"), "?")[0]}    时长：{b.get("seconds", "?")} 秒')
    print('—' * 50)
    if errs:
        print(f'不能开工，{len(errs)} 处要改：')
        for e in errs:
            print(f'  ✗ {e}')
    else:
        print('✓ 访谈通过，可以进第 1 步（定角度 → 故事板）')
        for line in plan(b):
            print(f'  · {line}')
    for w in warns:
        print(f'  ! 建议：{w}')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
