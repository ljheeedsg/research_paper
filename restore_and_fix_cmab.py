#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
恢复并修复 experiment2_第4步CMAB.md 文件
"""
import re
from pathlib import Path
import subprocess

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')

# 首先尝试从git恢复
try:
    result = subprocess.run(['git', 'checkout', str(filepath)], 
                          cwd=filepath.parent, 
                          capture_output=True, 
                          text=True,
                          timeout=5)
    if result.returncode == 0:
        print("✓ 已从git恢复文件")
    else:
        print(f"Git恢复失败: {result.stderr}")
except:
    print("Git不可用，将使用备份（如果有）")

# 读取当前文件
text = filepath.read_text(encoding='utf-8')

# 保存原始版本作为备份
backup_path = filepath.with_name(filepath.stem + '_backup.md')
backup_path.write_text(text, encoding='utf-8')
print(f"✓ 已保存备份到: {backup_path}")

# 现在进行非常具体的字符串替换
# 我们需要修复的模式都是这种形式：X_i$Y$ 或 X_j$Y$

replacements = [
    # 最常见的模式：形如 \bar{q}_i$t$ 的结构
    (r'\\bar{q}_i$t$', r'\\bar{q}_{i}^{(t)}'),
    (r'\\bar{q}_i$t-1$', r'\\bar{q}_{i}^{(t-1)}'),
    (r'\\bar{q}_i$1$', r'\\bar{q}_{i}^{(1)}'),
    
    (r'\\hat{q}_i$t$', r'\\hat{q}_{i}^{(t)}'),
    (r'\\hat{q}_i$t-1$', r'\\hat{q}_{i}^{(t-1)}'),
    
    (r'W_j$t$', r'W_{j}^{(t)}'),
    (r'Q_j$t$', r'Q_{j}^{(t)}'),
    (r'Q_j$t-1$', r'Q_{j}^{(t-1)}'),
    
    (r'n_i$t$', r'n_{i}^{(t)}'),
    (r'n_i$t-1$', r'n_{i}^{(t-1)}'),
    (r'n_i$1$', r'n_{i}^{(1)}'),
    
    (r'score_i$t$', r'score_{i}^{(t)}'),
    (r'gain_i$t$', r'gain_{i}^{(t)}'),
    (r'S_i$t$', r'S_{i}^{(t)}'),
    (r'S_i$1$', r'S_{i}^{(1)}'),
    (r'S_i$t-1$', r'S_{i}^{(t-1)}'),
    
    # 处理括号内的形式
    (r'(n_i$t$)', r'($n_{i}^{(t)}$)'),
    (r'(n_i$t-1$)', r'($n_{i}^{(t-1)}$)'),
    (r'(n_i$1$)', r'($n_{i}^{(1)}$)'),
    (r'(S_i$t$)', r'($S_{i}^{(t)}$)'),
    (r'(S_i$1$)', r'($S_{i}^{(1)}$)'),
    (r'(\bar{q}_i$t$)', r'($\bar{q}_{i}^{(t)}$)'),
    (r'(\bar{q}_i$t-1$)', r'($\bar{q}_{i}^{(t-1)}$)'),
    (r'(\bar{q}_i$1$)', r'($\bar{q}_{i}^{(1)}$)'),
    
    # 修复美元符号逃逸的问题：$t-1$ 不在美元符号内
    # 不做这个，因为 $t-1$ 实际上应该是 t-1 不在美元符号内
]

# 应用替换
for old, new in replacements:
    if old in text:
        count = text.count(old)
        text = text.replace(old, new)
        print(f"✓ 已替换 {count} 处: {old} -> {new}")
    else:
        print(f"  未找到: {old}")

# 保存修改
filepath.write_text(text, encoding='utf-8')
print(f"\n✓ 已修复文件: {filepath}")
print(f"文件大小: {len(text)} 字符")
