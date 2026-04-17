#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 CMAB 文档中的所有公式格式问题（完整版）
"""
from pathlib import Path

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')

# 读取文件
text = filepath.read_text(encoding='utf-8')

# 定义所有需要替换的模式
replacements = [
    # 形如 \bar{q}*i$X$ 的模式（原始文件中的格式）
    ('\\bar{q}*i$t$', '\\bar{q}_{i}^{(t)}'),
    ('\\bar{q}*i$t-1$', '\\bar{q}_{i}^{(t-1)}'),
    ('\\bar{q}*i$1$', '\\bar{q}_{i}^{(1)}'),
    ('\\bar{q}_i$t$', '\\bar{q}_{i}^{(t)}'),
    ('\\bar{q}_i$t-1$', '\\bar{q}_{i}^{(t-1)}'),
    ('\\bar{q}_i$1$', '\\bar{q}_{i}^{(1)}'),
    
    # \hat{q} 的变体
    ('\\hat{q}*i$t$', '\\hat{q}_{i}^{(t)}'),
    ('\\hat{q}*i$t-1$', '\\hat{q}_{i}^{(t-1)}'),
    ('\\hat{q}_i$t$', '\\hat{q}_{i}^{(t)}'),
    ('\\hat{q}_i$t-1$', '\\hat{q}_{i}^{(t-1)}'),
    
    # 已经被部分修复的，我们需要修复剩余部分
    # n_i$X$ 的模式（在分母中可能没被替换）
    ('\\frac{1}{n_i$1$}', '\\frac{1}{n_{i}^{(1)}}'),
    ('\\frac{1}{n_i$t$}', '\\frac{1}{n_{i}^{(t)}}'),
    ('\\frac{1}{n_i$t-1$}', '\\frac{1}{n_{i}^{(t-1)}}'),
    ('\\frac{n_i$t-1$', '\\frac{n_{i}^{(t-1)}'),
    
    # \sum*{ 的问题 - 这不是标准LaTeX
    ('\\sum*{', '\\sum_{'),
    
    # S_i$X$ 在不同上下文中
    # (S_i$1$) -> $S_{i}^{(1)}$ 
    ('(S_i$1$)', '($S_{i}^{(1)}$)'),
    ('(S_i$t$)', '($S_{i}^{(t)}$)'),
    ('(S_i$t-1$)', '($S_{i}^{(t-1)}$)'),
    
    # 在数学模式中：{j \in S_i$1$}
    ('{j \\in S_i$1$}', '{j \\in S_{i}^{(1)}}'),
    ('{j \\in S_i$t$}', '{j \\in S_{i}^{(t)}}'),
    ('{i \\mid t \\in available_slots_i}', '{i \\mid t \\in available\\_slots_i}'),
    
    # (n_i$X$ 的形式（在括号中）
    ('(n_i$1$)', '($n_{i}^{(1)}$)'),
    ('(n_i$t-1$)', '($n_{i}^{(t-1)}$)'),
    
    # m_i$t$ 的形式
    ('m_i$t$', 'm_{i}^{(t)}'),
    ('m_i$t-1$', 'm_{i}^{(t-1)}'),
    
    # 已修复的，但可能还有其他情况
    # W_j$X$ - 应该已经被修复了
    # Q_j$X$ - 应该已经被修复了
    # n_i$X$ - 应该已经被修复了
    # score_i$X$ - 应该已经被修复了
    
    # 处理块级公式中的问题：$$\bar{q}_i$t$$$
    # 这应该是 $$\bar{q}_{i}^{(t)}$$
    ('$$\\bar{q}_i$t$$$', '$$\\bar{q}_{i}^{(t)}$$'),
    ('$$\\bar{q}*i$t$$$', '$$\\bar{q}_{i}^{(t)}$$'),
    
    # 修复公式块中的等号
    ('\\bar{q}*i$1$ =', '\\bar{q}_{i}^{(1)} ='),
    ('\\bar{q}*i$t$ =', '\\bar{q}_{i}^{(t)} ='),
    ('\\bar{q}_i$1$ =', '\\bar{q}_{i}^{(1)} ='),
    ('\\bar{q}_i$t$ =', '\\bar{q}_{i}^{(t)} ='),
]

# 应用所有替换
changes_count = 0
for old, new in replacements:
    if old in text:
        count = text.count(old)
        text = text.replace(old, new)
        changes_count += count
        print(f"✓ 替换 {count} 处: '{old}' -> '{new}'")

# 保存修改
filepath.write_text(text, encoding='utf-8')
print(f"\n✓ 共替换 {changes_count} 处")
print(f"✓ 已修复文件: {filepath}")
