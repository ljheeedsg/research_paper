from pathlib import Path

file_path = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_第4步CMAB.md')
text = file_path.read_text(encoding='utf-8')

# 找到第一个 [ 的位置
idx = text.find('[')
if idx >= 0:
    # 打印前后100个字符的十六进制表示
    start = max(0, idx - 50)
    end = min(len(text), idx + 150)
    sample = text[start:end]
    print("Sample with repr():")
    print(repr(sample))
    print("\n---\n")
    print("Sample with escape sequences:")
    for i, char in enumerate(sample):
        if char == '\n':
            print(f"[{i}] newline")
        elif char == '[':
            print(f"[{i}] [bracket]")
        elif char == ']':
            print(f"[{i}] ]bracket]")
        else:
            print(f"[{i}] {char}")
