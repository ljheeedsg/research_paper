#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 experiment2_第4步CMAB.md 中的公式格式问题
"""
import re
from pathlib import Path

def fix_cmab_formulas(filepath):
    """修复 CMAB 文档中的公式格式"""
    
    text = Path(filepath).read_text(encoding='utf-8')
    
    # 首先处理所有 X_i$Y$ 和 X_i$Y-Z$ 这样的模式
    # 这是最常见的错误：应该是 X_{i}^{(Y)}
    
    # 1. 修复 n_i$t-1$ 形式的上标
    text = re.sub(r'n_i\$([^$]+)\$', lambda m: f'n_{{{m.group(1)}}}', text)
    # 不对，这样会变成 n_{t-1} 而不是 n_{i}^{(t-1)}
    
    # 让我重新思考这个问题。需要分两步：
    # 1. 首先把所有 X_i$Y$ 的形式改为 X_{i}^{(Y)}
    
    # 更仔细的方法：
    # 匹配 \bar{q}_i$X$ 或 n_i$X$ 或 Q_j$X$ 等等
    
    # 用一个更通用的模式：
    # ([a-z\\]+)_([ij])\$([^$]+)\$
    # 将其替换为 \1_{\2}^{(\3)}
    
    text = re.sub(
        r'([a-z]+(?:\\[a-z]*)?{[^}]*}|[a-z]+)_([ij])\$([^$]+)\$',
        lambda m: f'{m.group(1)}_{{{m.group(2)}}}^{{({m.group(3)})}}'.replace('{{', '{').replace('}}', '}'),
        text
    )
    
    # 对于 bar{q}_i$X$ 这样带反斜杠的
    text = re.sub(
        r'(\\(?:bar|hat)\{[^}]*\})_([ij])\$([^$]+)\$',
        lambda m: f'{m.group(1)}_{{{m.group(2)}}}^{{({m.group(3)})}}'.replace('{{', '{').replace('}}', '}'),
        text
    )
    
    # 2. 修复 (X_i$Y$) 这样被括号包围的形式，应该变成 $X_{i}^{(Y)}$
    text = re.sub(
        r'\(([a-zA-Z_]+)_([ij])\$([^$]+)\$\)',
        lambda m: f'${m.group(1)}_{{{m.group(2)}}}^{{({m.group(3)})}}'.replace('{{', '{').replace('}}', '}') + '$',
        text
    )
    
    # 3. 修复 S_i$X$ 和 |S_i$X$| 这样的形式
    text = re.sub(
        r'S_i\$([^$]+)\$',
        lambda m: f'S_{{{m.group(1)}}}',
        text
    )
    
    # 不对，应该改为正确的上标。让我直接做字符串替换
    
    # 重新读取文件，用更直接的方法
    text = Path(filepath).read_text(encoding='utf-8')
    
    # 找出所有的 X_i$Y$ 模式并替换
    replacements = [
        # \bar{q}_i$X$ -> \bar{q}_{i}^{(X)}
        (r'\\bar\{q\}_i\$([^$]+)\$', r'\\bar{q}_{i}^{(\1)}'),
        (r'\\hat\{q\}_i\$([^$]+)\$', r'\\hat{q}_{i}^{(\1)}'),
        
        # Q_j$X$ -> Q_{j}^{(X)}
        (r'Q_j\$([^$]+)\$', r'Q_{j}^{(\1)}'),
        
        # W_j$X$ -> W_{j}^{(X)}
        (r'W_j\$([^$]+)\$', r'W_{j}^{(\1)}'),
        
        # n_i$X$ -> n_{i}^{(X)}
        (r'n_i\$([^$]+)\$', r'n_{i}^{(\1)}'),
        
        # score_i$X$ -> score_{i}^{(X)}
        (r'score_i\$([^$]+)\$', r'score_{i}^{(\1)}'),
        
        # gain_i$X$ -> gain_{i}^{(X)}
        (r'gain_i\$([^$]+)\$', r'gain_{i}^{(\1)}'),
        
        # S_i$X$ -> S_{i}^{(X)}
        (r'S_i\$([^$]+)\$', r'S_{i}^{(\1)}'),
        
        # 修复括号包围的形式
        # (n_i$X$) -> $n_{i}^{(X)}$
        (r'\(n_{i}\^{\(([^)]+)\)}\)', r'$n_{i}^{(\1)}$'),
        (r'\(S_{i}\^{\(([^)]+)\)}\)', r'$S_{i}^{(\1)}$'),
        (r'\(\\bar\{q\}_{i}\^{\(([^)]+)\)}\)', r'$\\bar{q}_{i}^{(\1)}$'),
    ]
    
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    
    # 修复 {i \mid ...} 中的花括号（在公式中应该转义）
    # 查找在 $$ 块中的 {i \mid
    def escape_braces_in_formula(match):
        content = match.group(1)
        # 不要转义，因为在数学模式中 { 和 } 是合法的
        return f'${{{content}}}$' if content.startswith('{') else f'${content}$'
    
    # 修复 { 为 \{（在公式中）
    # 只在以下情况下转义：在 $$ 或 $ 中，且是集合表示法
    # 简单处理：在 ... \mid ... 的格式中，{ 应该转义
    text = re.sub(r'\$(\{[^}]*\|[^}]*\})\$', lambda m: f'${{{m.group(1).replace("{", "").replace("}", "")}}}$', text)
    
    # 保存修改后的文件
    Path(filepath).write_text(text, encoding='utf-8')
    print(f"✓ 已修复文件：{filepath}")
    print(f"文件长度：{len(text)} 字符")
    
    return text

if __name__ == '__main__':
    filepath = r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md'
    fix_cmab_formulas(filepath)
    print('✓ 公式修复完成！')
