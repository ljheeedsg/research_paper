#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接修复 PGRD 文件的公式格式
"""
from pathlib import Path

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第6步加入PGRD.md')

# 读取文件
text = filepath.read_text(encoding='utf-8')

# 简单直接的替换：所有的 [ 和对应的 ] 换成 $$ 和 $$
# 策略：查找 \n[ 然后找到对应的 ]\n
import re

# 处理块级公式：找到 \n[\n ... \n]\n 的模式
# 使用非贪心匹配
text = re.sub(r'\n\[\n(.*?)\n\]\n', r'\n$$\n\1\n$$\n', text, flags=re.DOTALL)

# 检查是否还有剩余的 [ 和 ]
remaining_brackets = text.count('[') + text.count(']')
print(f"替换后剩余 [ ] 数量: {remaining_brackets}")

if remaining_brackets > 0:
    # 手工处理仍然存在的情况
    # 可能是格式不完全一样
    print("仍有未处理的括号，尝试更激进的替换...")
    
    # 用另一种方法：找所有的 [ 后面的非空行
    lines = text.split('\n')
    new_lines = []
    in_formula = False
    
    for line in lines:
        if line.strip() == '[':
            new_lines.append('$$')
            in_formula = True
        elif line.strip() == ']':
            new_lines.append('$$')
            in_formula = False
        else:
            new_lines.append(line)
    
    text = '\n'.join(new_lines)
    print(f"✓ 已处理行级公式括号")

# 现在修复数学符号格式
replacements = {
    # 核心变量（按出现频率）
    '(i)': '$i$',
    '(j)': '$j$',
    '(t)': '$t$',
    '(k)': '$k$',
    
    # 带下标的
    '(c_{i,j})': '$c_{i,j}$',
    '(r_{i,j})': '$r_{i,j}$',
    '(r_j)': '$r_j$',
    '(r_i)': '$r_i$',
    '(b_{i,j}^r)': '$b_{i,j}^r$',
    '(b_{i,j}^{me})': '$b_{i,j}^{me}$',
    '(b_{i,j}^{no})': '$b_{i,j}^{no}$',
    '(V_{loss}^{j})': '$V_{loss}^{j}$',
    '(\\zeta_R)': '$\\zeta_R$',
    '(\\zeta)': '$\\zeta$',
    '(R_i(D_A))': '$R_i(D_A)$',
    '(R_i(D_B))': '$R_i(D_B)$',
    '(\\Gamma)': '$\\Gamma$',
    '(\\Gamma_{me})': '$\\Gamma_{me}$',
    '(\\Gamma_{no})': '$\\Gamma_{no}$',
    '(\\alpha)': '$\\alpha$',
    '(\\beta)': '$\\beta$',
    '(\\lambda)': '$\\lambda$',
    '(\\phi_t)': '$\\phi_t$',
    '(\\overline{r_i}^{,hist})': '$\\overline{r_i}^{\\text{hist}}$',
    '(\\overline{r_i}^{hist})': '$\\overline{r_i}^{\\text{hist}}$',
    '(r^{me})': '$r^{me}$',
    '(r^{no})': '$r^{no}$',
    '(r^{me} > r^{no})': '$r^{me} > r^{no}$',
    '(T_i^{me})': '$T_i^{me}$',
    '(T_i^{no})': '$T_i^{no}$',
    '(D_A)': '$D_A$',
    '(D_B)': '$D_B$',
}

change_count = 0
for old, new in replacements.items():
    if old in text:
        count = text.count(old)
        text = text.replace(old, new)
        change_count += count
        # print(f"  替换 {count} 处: {old}")

if change_count > 0:
    print(f"✓ 已替换 {change_count} 处数学符号格式")

# 保存
filepath.write_text(text, encoding='utf-8')
print(f"✓ 已修复文件: {filepath}")
print(f"  文件大小: {len(text)} 字符")
