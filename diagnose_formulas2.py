from pathlib import Path

file_path = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')
text = file_path.read_text(encoding='utf-8')

# 找第一个 [ 的位置
pos = text.find('[')
print(f"Position of first '[': {pos}")

if pos >= 0:
    # 打印这个位置前后的内容（用 repr 显示转义字符）
    start = max(0, pos - 20)
    end = min(len(text), pos + 60)
    sample = text[start:end]
    print(f"\nSample (with escapes):\n{repr(sample)}")
    
    # 查找对应的 ]
    close_pos = text.find(']', pos)
    print(f"Position of matching ']': {close_pos}")
    
    # 显示 [ 到 ] 的内容
    if close_pos >= 0:
        content = text[pos:close_pos+1]
        print(f"\nBlock content:\n{repr(content)}")

# 查找 ( 的第一个非文本括号（应该是公式）
count = 0
for i, char in enumerate(text):
    if char == '(' and (i == 0 or text[i-1] in ' \n'):
        if count == 0:
            print(f"\n\nFirst '(' at position {i}")
            start = max(0, i - 10)
            end = min(len(text), i + 30)
            print(f"Context: {repr(text[start:end])}")
        count += 1
        if count >= 3:
            break
