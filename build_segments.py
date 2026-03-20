import csv
import json

# ================== 配置 ==================
CSV_FILE = "tasks.csv"            # 你之前生成的任务集合文件
JSON_FILE = "task_segments.json" # 要输出的JSON文件
REGIONS = list(range(6))          # 0~5 共6个区域

# ================== 初始化分组字典 ==================
task_segments = {f"region_{r}": [] for r in REGIONS}

# ================== 读取CSV并分组 ==================
with open(CSV_FILE, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        region_id = int(row["region_id"])
        # 构造单条任务的JSON对象
        segment = {
            "task_id": row["task_id"],
            "start_time": int(row["start_time"]),
            "end_time": int(row["end_time"]),
            "required_workers": int(row["required_workers"])
        }
        # 加入对应区域的列表
        task_segments[f"region_{region_id}"].append(segment)

# ================== 写入JSON文件 ==================
with open(JSON_FILE, "w", encoding="utf-8") as f:
    json.dump(task_segments, f, indent=2, ensure_ascii=False)

print(f"✅ 处理完成！已生成 {JSON_FILE}")
print(f"📊 各区域任务数量：")
for r in REGIONS:
    print(f"   region_{r}: {len(task_segments[f'region_{r}'])} 条（目标20条）")