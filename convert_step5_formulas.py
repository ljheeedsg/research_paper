from pathlib import Path
import re

# 使用相对路径
file_path = Path(r'experiment2_第5步加入验证任务.md')
if not file_path.exists():
    # 如果相对路径不存在，使用绝对路径
    file_path = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第5步加入验证任务.md')

text = file_path.read_text(encoding='utf-8')

print(f"Original file size: {len(text)} bytes")

# 处理块级公式：[ ... ] 改为 $$ ... $$
text = re.sub(r'\[\n(.+?)\n\]', r'$$\n\1\n$$', text, flags=re.DOTALL)

# 处理没有换行的块级公式情况
text = re.sub(r'\[([^\[\]]+?)\]', r'$\1$', text)

# 处理行内公式的括号：(...) 改为 $...$
def replace_parens(match):
    content = match.group(1)
    # 检查是否是 \text{...}
    if content.startswith('\\text{') and content.endswith('}'):
        return f'({content})'
    # 检查是否包含中文（通常是描述，不转换）
    if any('\u4e00' <= c <= '\u9fff' for c in content):
        return f'({content})'
    # 否则转换为公式
    return f'${content}$'

text = re.sub(r'\(([^()]+?)\)', replace_parens, text)

print(f"Final file size: {len(text)} bytes")

file_path.write_text(text, encoding='utf-8')
print('✓ 公式转换完成！')
