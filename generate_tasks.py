import random
import csv

# ================== 核心参数（贴合文档规则） ==================
REGION_COUNT = 6                # 区域数：0~5
TASKS_PER_REGION = 20           # 每个区域任务数：20
TOTAL_TASKS = REGION_COUNT * TASKS_PER_REGION  # 总任务数：120

TASK_DURATION = 3600            # 任务固定时长：3600秒（1小时）
MAX_START_TIME = 6 * 3600 - TASK_DURATION  # 最大开始时间：21600-3600=18000秒
MIN_WORKERS = 1
MAX_WORKERS = 3


# ================== 生成单区域任务 ==================
def generate_region_tasks(region_id):
    tasks = []
    for task_idx in range(TASKS_PER_REGION):
        # 生成任务ID：t{region补两位}_{idx补两位}
        task_id = f"t{str(region_id).zfill(2)}_{str(task_idx).zfill(2)}"
        
        # 随机生成开始时间（保证结束时间≤21600）
        start_time = random.randint(0, MAX_START_TIME)
        end_time = start_time + TASK_DURATION
        
        # 随机生成所需工人数（1~3）
        required_workers = random.randint(MIN_WORKERS, MAX_WORKERS)
        
        tasks.append([
            task_id,
            region_id,
            start_time,
            end_time,
            required_workers
        ])
    return tasks


# ================== 生成完整tasks.csv ==================
def generate_tasks_csv(filename="tasks.csv"):
    all_tasks = []
    # 遍历6个区域，每个区域生成20个任务
    for region_id in range(REGION_COUNT):
        region_tasks = generate_region_tasks(region_id)
        all_tasks.extend(region_tasks)
    
    # 写入CSV文件
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 写入表头
        writer.writerow(["task_id", "region_id", "start_time", "end_time", "required_workers"])
        # 写入数据
        writer.writerows(all_tasks)
    
    print(f"✅ 任务数据生成完成！文件已保存为：{filename}")
    print(f"📊 总任务数：{len(all_tasks)} 条（目标120条）")


# ================== 运行生成 ==================
if __name__ == "__main__":
    generate_tasks_csv()