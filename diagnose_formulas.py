from pathlib import Path

file_path = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')
text = file_path.read_text(encoding='utf-8')

# 找第一个 [ 的位置
pos = text.find('[\n')
print(f"Position of '[\\n': {pos}")

if pos >= 0:
    # 打印这个位置前后的内容
    start = max(0, pos - 20)
    end = min(len(text), pos + 100)
    sample = text[start:end]
    print(f"\nSample text:\n{repr(sample)}")
    
    # 查找对应的 ] 
    close_pos = text.find('\n]', pos)
    print(f"Position of '\\n]': {close_pos}")
    
# 现在找所有的 [\n 和 \n] 的模式
count_open = text.count('[\n')
count_close = text.count('\n]')
print(f"\nFound {count_open} instances of '[\\n'")
print(f"Found {count_close} instances of '\\n]'")

# 检查行内公式
count_parens = len([i for i in range(len(text)) if text[i] == '(' and i < len(text)-3 and text[i:i+1] != '\n'])
print(f"\nFound approximately {count_parens} '(' characters for inline formulas")
