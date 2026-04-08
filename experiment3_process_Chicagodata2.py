import csv
import json
from collections import defaultdict

INPUT_CSV = 'experiment3_vehicle.csv'
OUTPUT_JSON = 'experiment3_worker_segments.json'

region_groups = defaultdict(list)

with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 自动处理 BOM
    reader = csv.DictReader(f)
    # 清理列名中的前后空格
    reader.fieldnames = [name.strip() for name in reader.fieldnames]
    print("实际CSV列名：", reader.fieldnames)  # 调试输出

    for row in reader:
        # 清理字典的键（去除空格）
        row = {k.strip(): v for k, v in row.items()}
        
        # 兼容 vehicle_id 或 ride_id
        vehicle_key = None
        if 'vehicle_id' in row:
            vehicle_key = 'vehicle_id'
        elif 'ride_id' in row:
            vehicle_key = 'ride_id'
        else:
            raise KeyError(f"未找到 vehicle_id 或 ride_id 列，实际列名：{list(row.keys())}")
        
        region_id = int(row['region_id'])
        segment = {
            'vehicle_id': row[vehicle_key],
            'start_time': int(row['start_time']),
            'end_time': int(row['end_time']),
            'cost': float(row['cost']),
            'is_trusted': row['is_trusted'].lower() == 'true'
        }
        region_groups[region_id].append(segment)

result = {}
for region_id, segments in region_groups.items():
    result[f"region_{region_id}"] = segments

with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"已生成 {OUTPUT_JSON}，包含 {len(region_groups)} 个区域。")