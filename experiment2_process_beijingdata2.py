import csv
import json
from collections import defaultdict

INPUT_CSV = 'experiment2_vehicle.csv'
OUTPUT_JSON = 'experiment2_worker_segments.json'

# 读取 CSV，按 region_id 分组
region_groups = defaultdict(list)
with open(INPUT_CSV, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        region_id = int(row['region_id'])
        # 提取所需字段
        segment = {
            'vehicle_id': row['vehicle_id'],
            'start_time': int(row['start_time']),
            'end_time': int(row['end_time']),
            'cost': float(row['cost']),
            'is_trusted': row['is_trusted'] == 'True'
        }
        region_groups[region_id].append(segment)

# 构建 JSON 结构，键为 "region_0", "region_1", ...
result = {}
for region_id, segments in region_groups.items():
    result[f"region_{region_id}"] = segments

# 写入 JSON
with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"已生成 {OUTPUT_JSON}，包含 {len(region_groups)} 个区域。")