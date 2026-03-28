import csv
import json
import random
from collections import defaultdict

# ==================== 配置 ====================
VEHICLE_FILE = 'step6_vehicle.csv'
OUTPUT_JSON = 'step6_task_segments.json'

TOTAL_TASKS = 200               # 总任务数（可调整）
TIME_MIN = 0                    # 起始时间最小值（秒）
TIME_MAX = 82800                # 起始时间最大值（秒），保证窗口不跨午夜
random.seed(42)                 # 固定随机种子，可重复
# ==============================================

# 1. 统计每个区域的活动密度（轨迹段数）
region_density = defaultdict(int)
with open(VEHICLE_FILE, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        region = int(row['region_id'])
        region_density[region] += 1

if not region_density:
    print("错误：车辆轨迹文件为空或无有效区域。")
    exit()

# 2. 按密度分配任务数量
total_density = sum(region_density.values())
# 按比例计算每个区域的任务数（浮点数）
tasks_per_region_float = {r: (d / total_density) * TOTAL_TASKS for r, d in region_density.items()}
# 取整，并记录余数
tasks_per_region = {r: int(round(val)) for r, val in tasks_per_region_float.items()}
remainder = TOTAL_TASKS - sum(tasks_per_region.values())
# 将余数随机分配给有任务的区域
region_list = list(tasks_per_region.keys())
for _ in range(abs(remainder)):
    r = random.choice(region_list)
    tasks_per_region[r] += 1 if remainder > 0 else -1

# 3. 生成任务并分组
tasks_by_region = defaultdict(list)   # region_id -> list of task dicts
seq_counter = defaultdict(int)        # 每个区域的任务序号计数器

for region, num_tasks in tasks_per_region.items():
    for _ in range(num_tasks):
        # 随机起始时间（保证 end_time ≤ 86400）
        start = random.randint(TIME_MIN, TIME_MAX)
        end = start + 3600
        required = random.randint(1, 3)
        # 生成 task_id
        seq = seq_counter[region]
        task_id = f"t{region:02d}_{seq:02d}"
        tasks_by_region[region].append({
            'task_id': task_id,
            'start_time': start,
            'end_time': end,
            'required_workers': required
        })
        seq_counter[region] += 1

# 4. 构建 JSON 结构
result = {}
for region_id, tasks in tasks_by_region.items():
    result[f"region_{region_id}"] = tasks

# 5. 写入 JSON
with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"已生成 {OUTPUT_JSON}，共 {sum(len(v) for v in tasks_by_region.values())} 个任务，涉及 {len(tasks_by_region)} 个区域。")