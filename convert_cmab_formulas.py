from pathlib import Path

file_path = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')
text = file_path.read_text(encoding='utf-8')

print(f"Original file length: {len(text)}")

# 简单的字符串替换：[ 改为 $$，] 改为 $$
# 使用正则表达式更精细地处理

import re

# 找到 [\n...\n] 的块级公式并替换
# 这个正则会找到：\n[\n<any content>\n]\n 并替换为 \n$$\n<any content>\n$$\n

# 关键是要处理多行的块级公式
# 用非贪心匹配 .*? 和 DOTALL 标志
text = re.sub(r'\[\n(.*?)\n\]', lambda m: '$$\n' + m.group(1) + '\n$$', text, flags=re.DOTALL)

print(f"After block formula replacement: {len(text)}")

# 处理行内公式的括号
# 匹配 (...) 但排除 \text{...}
import re

def replace_inline_formula(match):
    content = match.group(1)
    # 检查是否包含 \text{
    if '\\text{' in content:
        return f'({content})'
    # 检查是否是中文（通常是描述性文字）
    if any('\u4e00' <= c <= '\u9fff' for c in content):
        return f'({content})'
    # 否则转换为公式
    return f'${content}$'

text = re.sub(r'\(([^()]+)\)', replace_inline_formula, text)

print(f"After inline formula replacement: {len(text)}")

file_path.write_text(text, encoding='utf-8')
print('✓ 公式转换完成！')
