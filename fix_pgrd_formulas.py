#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 experiment2_第6步加入PGRD.md 中的公式格式问题
"""
from pathlib import Path
import re

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第6步加入PGRD.md')

# 读取文件
text = filepath.read_text(encoding='utf-8')

# 保存备份
backup_path = filepath.with_name(filepath.stem + '_backup.md')
backup_path.write_text(text, encoding='utf-8')
print(f"✓ 已保存备份到: {backup_path}")

replacements = [
    # 1. 修复块级公式：[ 改为 $$，] 改为 $$
    # 但要小心不要改变代码块中的 [ ]
    # 我们用正则表达式来处理
    
    # 2. 修复符号格式：(i), (j), (t) 等应该是 $i$, $j$, $t$
    # 但要注意在代码块和描述性文本中不要改动
    
    # 3. 修复数学模式中的符号
    # 例如：(c_{i,j}) -> $c_{i,j}$
    # 例如：(r_{i,j}) -> $r_{i,j}$
    
    # 简单的替换列表（针对特定的已知模式）
    
    # 块级公式替换
    ('[\n\\Gamma=\\Gamma_{me}\\cup\\Gamma_{no}\n]', 
     '$$\n\\Gamma=\\Gamma_{me}\\cup\\Gamma_{no}\n$$'),
    
    ('[\nr_j =\n\\begin{cases}', 
     '$$\nr_j =\n\\begin{cases}'),
    
    # 匹配 [\nblah\n] 的通用形式
    # 使用正则表达式
]

# 使用正则表达式处理块级公式
# 模式：\n[\n...\n]\n 替换为 \n$$\n...\n$$\n
text = re.sub(r'\n\[\n(.*?)\n\]\n', r'\n$$\n\1\n$$\n', text, flags=re.DOTALL)

print(f"✓ 已替换块级公式 [ ] 为 $$ $$")

# 现在处理 (i), (j), (t) 等单字母符号
# 但要避免改变代码块、URL 或自然文本中的括号
# 策略：只改变在 markdown 正文中的 (single_letter)

# 这个比较复杂，所以我们用具体的字符串替换
specific_replacements = [
    # 在公式描述中的符号
    ('对工人 (i)', '对工人 $i$'),
    ('、任务 (j)', '、任务 $j$'),
    ('、当前轮 (t)', '、当前轮 $t$'),
    
    # 在代码注释中的
    ('# 工人 (i)', '# 工人 $i$'),
    
    # 数学表达式中的括号形式
    # 例如 (c_{i,j}) 应该是 $c_{i,j}$
    # 但这需要小心，因为可能有其他类型的括号
    
    # 让我们处理已知的数学变量模式
    ('(c_{i,j})', '$c_{i,j}$'),
    ('(r_{i,j})', '$r_{i,j}$'),
    ('(r_j)', '$r_j$'),
    ('(i)', '$i$'),
    ('(j)', '$j$'),
    ('(t)', '$t$'),
    ('(k)', '$k$'),
    
    # 集合符号
    ('(\\Gamma=\\Gamma_{me}\\cup\\Gamma_{no})', '$\\Gamma=\\Gamma_{me}\\cup\\Gamma_{no}$'),
    ('(Γ_me)', '$\\Gamma_{me}$'),
    ('(Γ_no)', '$\\Gamma_{no}$'),
    ('(Γ)', '$\\Gamma$'),
    
    # 其他常见的
    ('(R_i(D_A))', '$R_i(D_A)$'),
    ('(R_i(D_B))', '$R_i(D_B)$'),
    ('(b_{i,j}^r)', '$b_{i,j}^r$'),
    ('(\\overline{r_i}^{,hist})', '$\\overline{r_i}^{\\mathrm{hist}}$'),
    ('(V_{loss}^{j})', '$V_{loss}^{j}$'),
    ('(\\zeta_R)', '$\\zeta_R$'),
    ('(\\zeta)', '$\\zeta$'),
    
    # 复杂的表达式需要用正则替换
]

# 应用简单替换
changes = 0
for old, new in specific_replacements:
    if old in text:
        count = text.count(old)
        text = text.replace(old, new)
        changes += count
        print(f"✓ 替换 {count} 处: '{old}' -> '{new}'")

# 用正则表达式处理更复杂的模式
# 修复单独的 (i), (j), (t), (k) 等单字母符号（但要小心不要改代码块）
# 只在 markdown 正文中改（不在代码块 ``` ``` 中）

# 分割代码块和正文
parts = text.split('```')
for i in range(0, len(parts), 2):  # 只处理奇数索引（正文部分）
    # 在正文中用正则替换
    # 避免改变 (something) 这样的长的括号内容
    old_parts = parts[i]
    # 替换单字母：(i) -> $i$，但要确保后面不是字母或数字
    parts[i] = re.sub(r'\(([a-z])\)(?![a-zA-Z0-9])', r'$\1$', parts[i])
    if parts[i] != old_parts:
        print(f"✓ 已替换正文中的单字母符号 ({parts[i].count('$')//2} 处)")

text = '```'.join(parts)

# 保存修改
filepath.write_text(text, encoding='utf-8')
print(f"\n✓ 共替换 {changes} 处")
print(f"✓ 已修复文件: {filepath}")
