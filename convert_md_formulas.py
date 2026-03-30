from pathlib import Path
path = Path(r'c:\Users\ASUS\Desktop\research_paper\step9_all_set_together.md')
text = path.read_text(encoding='utf-8')
text = text.replace('\\[', '$$').replace('\\]', '$$').replace('\\(', '$').replace('\\)', '$')
path.write_text(text, encoding='utf-8')
print('converted')
