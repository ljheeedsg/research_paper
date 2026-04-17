#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 experiment2_第6步加入PGRD.md 中的公式格式问题（更完整版）
"""
from pathlib import Path
import re

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第6步加入PGRD.md')

# 读取文件
text = filepath.read_text(encoding='utf-8')

changes = 0

# 1. 修复块级公式：\n[\n...\n]\n 替换为 \n$$\n...\n$$\n
# 更灵活的正则
text_new = re.sub(r'\n\[\n((?:[^\n]|\n)*?)\n\]\n', r'\n$$\n\1\n$$\n', text)
if text_new != text:
    changes += text.count('[')  # 粗估计
    text = text_new
    print(f"✓ 已替换块级公式 [ ] 为 $$ $$")

# 2. 处理行内的 [ ... ] 形式（不在行首）
# 模式：[ \n ... \n ]
text = re.sub(r'\[\n(.*?)\n\]', lambda m: f'$$\n{m.group(1)}\n$$', text, flags=re.DOTALL)
print(f"✓ 已替换所有 [ ... ] 块级公式")

# 3. 修复 (X) 这样的符号形式
# 在 markdown 正文中的 (i), (j), (t) 等应改为 $i$, $j$, $t$
# 但要避免改变代码块中的内容

# 分离代码块
parts = text.split('```')
for i in range(len(parts)):
    if i % 2 == 0:  # 非代码块部分
        # 替换 (single_letter) 为 $single_letter$
        # 模式：( + 字母 + ) 且后面不是字母或数字
        parts[i] = re.sub(r'\(([a-z])\)(?![a-zA-Z0-9_])', r'$\1$', parts[i])

text = '```'.join(parts)
print(f"✓ 已替换单字母符号 (i), (j), (t) 等")

# 4. 处理有下标的数学表达式 (X_{...})
# 例如：(c_{i,j}) -> $c_{i,j}$
# 模式：( + 字母 + { ... } + )
# 这个比较复杂，用具体列表比较安全

math_replacements = [
    # 核心变量
    ('(c_{i,j})', '$c_{i,j}$'),
    ('(r_{i,j})', '$r_{i,j}$'),
    ('(r_j)', '$r_j$'),
    ('(r_i)', '$r_i$'),
    ('(b_{i,j}^r)', '$b_{i,j}^r$'),
    ('(b_{i,j}^{me})', '$b_{i,j}^{me}$'),
    ('(b_{i,j}^{no})', '$b_{i,j}^{no}$'),
    ('(V_{loss}^{j})', '$V_{loss}^{j}$'),
    ('(\\zeta_R)', '$\\zeta_R$'),
    ('(\\zeta)', '$\\zeta$'),
    ('(R_i(D_A))', '$R_i(D_A)$'),
    ('(R_i(D_B))', '$R_i(D_B)$'),
    ('(\\Gamma)', '$\\Gamma$'),
    ('(\\Gamma_{me})', '$\\Gamma_{me}$'),
    ('(\\Gamma_{no})', '$\\Gamma_{no}$'),
    ('(\\alpha)', '$\\alpha$'),
    ('(\\beta)', '$\\beta$'),
    ('(\\lambda)', '$\\lambda$'),
    ('(\\phi_t)', '$\\phi_t$'),
    ('(\\overline{r_i}^{,hist})', '$\\overline{r_i}^{\\text{hist}}$'),
    ('(\\overline{r_i}^{hist})', '$\\overline{r_i}^{\\text{hist}}$'),
    ('(r^{me})', '$r^{me}$'),
    ('(r^{no})', '$r^{no}$'),
    ('(r^{me} > r^{no})', '$r^{me} > r^{no}$'),
    
    # 集合和索引
    ('(T_i^{me})', '$T_i^{me}$'),
    ('(T_i^{no})', '$T_i^{no}$'),
    ('(D_A)', '$D_A$'),
    ('(D_B)', '$D_B$'),
    ('(e^{...})', '$e^{...}$'),
]

count_math = 0
for old, new in math_replacements:
    if old in text:
        cnt = text.count(old)
        text = text.replace(old, new)
        count_math += cnt

if count_math > 0:
    print(f"✓ 已替换 {count_math} 处数学表达式")

# 保存
filepath.write_text(text, encoding='utf-8')
print(f"\n✓ 已修复文件: {filepath}")
