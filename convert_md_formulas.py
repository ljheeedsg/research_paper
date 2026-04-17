from pathlib import Path
path = Path(r'c:\Users\ASUS\Desktop\research_paper\experiment2_算法流程.md')
text = path.read_text(encoding='utf-8')
text = text.replace('\\[', '$$').replace('\\]', '$$').replace('\\(', '$').replace('\\)', '$')
path.write_text(text, encoding='utf-8')
print('converted')
