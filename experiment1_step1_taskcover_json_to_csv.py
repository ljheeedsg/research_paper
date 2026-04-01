import json
import csv

files = [
    "experiment1_step1_ours_taskcover.json",
    "experiment1_step1_B4_taskcover.json",
    "experiment1_step1_B3_taskcover.json",
    "experiment1_step1_B2_taskcover.json",
    "experiment1_step1_B1_taskcover.json"
]

data = {}
for i, f in enumerate(files):
    with open(f, encoding='utf-8') as fp:
        d = json.load(fp)
    for item in d:
        r = item['round']
        val = item.get('coverage_rate', item.get('rate'))
        if r not in data:
            data[r] = [0]*5
        data[r][i] = val

with open('expeiment1_step1_all_coverage.csv', 'w', newline='', encoding='utf-8-sig') as fp:
    w = csv.writer(fp)
    w.writerow(['Round','Ours','B4','B3','B2','B1'])
    for r in sorted(data):
        w.writerow([r]+data[r])

print("✅ 成功！直接拖进 Origin 画图！")