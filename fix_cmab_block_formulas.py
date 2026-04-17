#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复块级公式中的剩余问题
"""
from pathlib import Path

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')
text = filepath.read_text(encoding='utf-8')

# 块级公式中的问题
replacements = [
    # 在 $$ ... $$ 中的形式
    ('$$\nW_j$t$\n$$', '$$\nW_{j}^{(t)}\n$$'),
    ('$$\nQ_j$t$\n$$', '$$\nQ_{j}^{(t)}\n$$'),
    ('$$\nReward_{t} =', '$$\nReward_{t} ='),
    ('$$\nCost_{t} =', '$$\nCost_{t} ='),
    
    # 在公式中间的 W_j$t$ = { ... }
    ('W_j$t$ = {', 'W_{j}^{(t)} = {'),
    
    # 其他剩余的 X_i$Y$ 形式在公式中
    ('\\bar{q}_{i}^{(t)} + \\sqrt{\\frac{\\alpha \\ln t}{n_i$t-1$+1}}',
     '\\bar{q}_{i}^{(t)} + \\sqrt{\\frac{\\alpha \\ln t}{n_{i}^{(t-1)}+1}}'),
    
    # 修复 { ... } 中的 W_j$t$ 形式
    ('{ i \\in A_t \\mid i \\text{ can execute } j }',
     '{ i \\in A_{t} \\mid i \\text{ can execute } j }'),
]

changes = 0
for old, new in replacements:
    if old in text:
        count = text.count(old)
        text = text.replace(old, new)
        changes += count
        print(f"✓ 替换 {count} 处: '{old}' -> '{new}'")
    else:
        # 尝试更灵活的查找
        if 'W_j$' in text:
            # 直接替换所有 W_j$X$ 形式
            import re
            text = re.sub(r'W_j\$([^$]+)\$', r'W_{j}^{(\1)}', text)
            changes += text.count('W_{j}^{')
            print("✓ 已替换块级公式中的 W_j$X$ 形式")
        if 'Q_j$' in text:
            import re
            text = re.sub(r'Q_j\$([^$]+)\$', r'Q_{j}^{(\1)}', text)
            print("✓ 已替换块级公式中的 Q_j$X$ 形式")

filepath.write_text(text, encoding='utf-8')
print(f"\n✓ 共替换 {changes} 处")
print(f"✓ 块级公式修复完成！")
