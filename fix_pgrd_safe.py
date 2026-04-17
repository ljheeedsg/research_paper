#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仔细修复 PGRD 文件的公式格式 - 不要删除内容！
"""
from pathlib import Path

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第6步加入PGRD.md')

# 读取文件
text = filepath.read_text(encoding='utf-8')
print(f"原始文件大小: {len(text)} 字符")

# 不要用复杂的正则，用简单的行级替换
lines = text.split('\n')
new_lines = []

for line in lines:
    # 处理单独一行的 [
    if line.strip() == '[':
        new_lines.append('$$')
    # 处理单独一行的 ]
    elif line.strip() == ']':
        new_lines.append('$$')
    else:
        # 在这一行中，进行数学符号替换
        line = line.replace('(i)', '$i$')
        line = line.replace('(j)', '$j$')
        line = line.replace('(t)', '$t$')
        line = line.replace('(k)', '$k$')
        
        # 但要避免改变代码行
        if not line.strip().startswith('#'):
            line = line.replace('(c_{i,j})', '$c_{i,j}$')
            line = line.replace('(r_{i,j})', '$r_{i,j}$')
            line = line.replace('(r_j)', '$r_j$')
            line = line.replace('(r_i)', '$r_i$')
            line = line.replace('(b_{i,j}^r)', '$b_{i,j}^r$')
            line = line.replace('(b_{i,j}^{me})', '$b_{i,j}^{me}$')
            line = line.replace('(b_{i,j}^{no})', '$b_{i,j}^{no}$')
            line = line.replace('(V_{loss}^{j})', '$V_{loss}^{j}$')
            line = line.replace('(\\zeta_R)', '$\\zeta_R$')
            line = line.replace('(\\zeta)', '$\\zeta$')
            line = line.replace('(R_i(D_A))', '$R_i(D_A)$')
            line = line.replace('(R_i(D_B))', '$R_i(D_B)$')
            line = line.replace('(\\Gamma)', '$\\Gamma$')
            line = line.replace('(\\Gamma_{me})', '$\\Gamma_{me}$')
            line = line.replace('(\\Gamma_{no})', '$\\Gamma_{no}$')
            line = line.replace('(\\alpha)', '$\\alpha$')
            line = line.replace('(\\beta)', '$\\beta$')
            line = line.replace('(\\lambda)', '$\\lambda$')
            line = line.replace('(\\phi_t)', '$\\phi_t$')
            line = line.replace('(\\overline{r_i}^{,hist})', '$\\overline{r_i}^{\\text{hist}}$')
            line = line.replace('(\\overline{r_i}^{hist})', '$\\overline{r_i}^{\\text{hist}}$')
            line = line.replace('(r^{me})', '$r^{me}$')
            line = line.replace('(r^{no})', '$r^{no}$')
            line = line.replace('(r^{me} > r^{no})', '$r^{me} > r^{no}$')
            line = line.replace('(T_i^{me})', '$T_i^{me}$')
            line = line.replace('(T_i^{no})', '$T_i^{no}$')
            line = line.replace('(D_A)', '$D_A$')
            line = line.replace('(D_B)', '$D_B$')
        
        new_lines.append(line)

text_new = '\n'.join(new_lines)
print(f"修改后文件大小: {len(text_new)} 字符")

# 验证内容没有丢失
if len(text_new) < len(text) * 0.9:
    print("⚠️ 警告：文件大小减少超过10%，可能有问题")
else:
    filepath.write_text(text_new, encoding='utf-8')
    print(f"✓ 已修复文件: {filepath}")
