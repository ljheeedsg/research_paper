#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最后的修复：处理剩余的公式问题
"""
from pathlib import Path

filepath = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')
text = filepath.read_text(encoding='utf-8')

# 处理 (n_i$X$ = |S_i$X$|) 这样的情况
replacements = [
    ('(n_i$1$', '($n_{i}^{(1)}'),
    ('(n_i$t$', '($n_{i}^{(t)}'),
    ('(n_i$t-1$', '($n_{i}^{(t-1)}'),
    
    ('S_i$1$|)', 'S_{i}^{(1)}|)'),
    ('S_i$t$|)', 'S_{i}^{(t)}|)'),
    ('S_i$t-1$|)', 'S_{i}^{(t-1)}|)'),
    
    # W_j$X$ = 的形式
    ('W_j$t$ =', 'W_{j}^{(t)} ='),
    
    # Reward_t, Cost_t 等形式
    ('Reward_t', 'Reward_{t}'),
    ('Cost_t', 'Cost_{t}'),
    ('CompletionRate_t', 'CompletionRate_{t}'),
    ('AvgQuality_t', 'AvgQuality_{t}'),
    ('Efficiency_t', 'Efficiency_{t}'),
    ('Completed_t', 'Completed_{t}'),
    ('A_t', 'A_{t}'),
    ('\\mathcal{W}_t', '\\mathcal{W}_{t}'),
    ('\\mathcal{T}_t', '\\mathcal{T}_{t}'),
]

changes = 0
for old, new in replacements:
    if old in text:
        count = text.count(old)
        text = text.replace(old, new)
        changes += count
        print(f"✓ 替换 {count} 处: '{old}' -> '{new}'")

filepath.write_text(text, encoding='utf-8')
print(f"\n✓ 共替换 {changes} 处")
print(f"✓ 最终修复完成！")
