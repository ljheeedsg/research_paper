import csv
import json
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Circle

# ==================== 配置 ====================
VEHICLE_FILE = 'step6_vehicle.csv'          # 车辆轨迹文件
TASK_CSV = 'step6_tasks.csv'                # 输出任务 CSV
TASK_JSON = 'step6_task_segments.json'      # 输出任务 JSON
PLOT_FILE = 'step6_tasks_distribution.png'  # 输出图片

TOTAL_TASKS = 200                           # 总任务数（将尽力生成，如果容量不足则输出实际数量）
TIME_SLOT_HOURS = 1                         # 时间片长度（小时），固定为1
HOURS_PER_DAY = 24

random.seed(42)
# ==============================================

def get_hour(t_seconds):
    """秒转小时（0-23）"""
    return t_seconds // 3600

def main():
    # ---------- 1. 读取车辆轨迹，构建工人时空容量 ----------
    # capacity[region][hour] = 不同工人数量
    capacity = defaultdict(lambda: defaultdict(set))
    with open(VEHICLE_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            region = int(row['region_id'])
            start = int(row['start_time'])
            end = int(row['end_time'])
            vehicle = row['vehicle_id']
            # 轨迹段可能跨多个小时，简化：取起始时间所在小时
            hour = get_hour(start)
            capacity[region][hour].add(vehicle)
    
    # 转换为整数数量
    capacity_count = {}
    total_capacity = 0
    for region, hour_dict in capacity.items():
        capacity_count[region] = {}
        for hour, workers in hour_dict.items():
            cnt = len(workers)
            capacity_count[region][hour] = cnt
            total_capacity += cnt
    
    if total_capacity == 0:
        print("错误：没有找到任何工人轨迹。")
        return
    
    # ---------- 2. 计算每个时空单元可支持的最大任务数 ----------
    # 假设平均每个任务需要 required_workers，我们取平均 2，也可以动态分配
    # 为避免过度分配，每个时空单元最多分配 capacity // min_required 个任务（min_required=1）
    # 更合理：按容量比例分配总任务数，但确保不超出 capacity // required
    # 这里采用：生成任务时实时检查，不预先分配，避免复杂整数规划
    
    # 为了方便，我们先生成一个候选任务池：所有 (region, hour) 组合，以及该小时内可用的工人数
    candidate_slots = []
    for region, hour_dict in capacity_count.items():
        for hour, cap in hour_dict.items():
            candidate_slots.append((region, hour, cap))
    
    # 按容量加权随机选择时空单元生成任务
    # 每个任务从候选池中按容量比例选择 (region, hour)，然后随机生成 required_workers <= cap
    # 同时保证每个时空单元生成的任务数不超过其容量（例如 cap // 1，因为 required_workers 至少为1）
    
    # 统计每个时空单元已生成的任务数
    generated_count = defaultdict(int)  # (region, hour) -> 任务数
    
    tasks = []               # (region, start, end, required, task_id)
    tasks_by_region = defaultdict(list)
    seq_counter = defaultdict(int)
    
    # 权重 = 容量（工人数），高容量区域/时段更容易被选中
    weights = [cap for (_, _, cap) in candidate_slots]
    
    # 为了避免死循环，设置最大尝试次数
    max_attempts = TOTAL_TASKS * 10
    attempts = 0
    
    while len(tasks) < TOTAL_TASKS and attempts < max_attempts:
        attempts += 1
        # 按容量加权选择一个时空单元
        slot = random.choices(candidate_slots, weights=weights, k=1)[0]
        region, hour, cap = slot
        
        # 该时空单元还能生成多少任务？简单限制：不超过 cap（因为每个任务至少需要1个工人）
        # 更严格：累计所需工人数不超过 cap * 某个因子，但为了简单，每个任务需要1~3人，限制任务数 <= cap // 1
        max_tasks_in_slot = cap  # 保守：每个任务至少1人，所以最多 cap 个任务
        if generated_count[(region, hour)] >= max_tasks_in_slot:
            continue
        
        # 随机生成 required_workers，不能超过 cap 且不能超过3
        max_req = min(3, cap)
        if max_req < 1:
            continue
        required = random.randint(1, 1)
        
        # 生成起始时间：在 [hour*3600, (hour+1)*3600 - 3600] 内随机（保证任务完全在该小时内）
        start_sec = random.randint(hour * 3600, (hour + 1) * 3600 - 3600)
        end_sec = start_sec + 3600
        
        # 确保不跨午夜（hour 最大23，start_sec <= 23*3600=82800，end_sec <= 86400，没问题）
        # 但如果 hour=23，end_sec 可能等于 86400，刚好午夜，可以接受（86400 视为次日0点，但我们的时间系统不跨日，所以允许边界）
        
        # 生成 task_id
        seq = seq_counter[region]
        task_id = f"t{region:02d}_{seq:02d}"
        
        tasks.append((region, start_sec, end_sec, required, task_id))
        tasks_by_region[region].append({
            'task_id': task_id,
            'start_time': start_sec,
            'end_time': end_sec,
            'required_workers': required
        })
        seq_counter[region] += 1
        generated_count[(region, hour)] += 1
    
    actual_tasks = len(tasks)
    print(f"实际生成任务数: {actual_tasks} / 目标 {TOTAL_TASKS}")
    if actual_tasks < TOTAL_TASKS:
        print(f"警告：工人容量不足，只能生成 {actual_tasks} 个任务。可考虑降低 TOTAL_TASKS 或增加工人轨迹。")
    
    # ---------- 3. 写入 CSV ----------
    with open(TASK_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['task_id', 'region_id', 'start_time', 'end_time', 'required_workers'])
        for region, start, end, required, task_id in tasks:
            writer.writerow([task_id, region, start, end, required])
    print(f"已生成 {TASK_CSV}")
    
    # ---------- 4. 写入 JSON ----------
    result = {}
    for region_id, task_list in tasks_by_region.items():
        result[f"region_{region_id}"] = task_list
    with open(TASK_JSON, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"已生成 {TASK_JSON}")
    
    # ---------- 5. 绘制分布图（与原脚本类似，但使用新生成的任务统计）----------
    # 需要统计每个区域的任务数（tasks_per_region）
    tasks_per_region = {region: len(tasks_by_region[region]) for region in tasks_by_region}
    
    GRID_X_NUM = 10
    GRID_Y_NUM = 10
    
    # 工人密度矩阵（仍然用轨迹段数，保持与原图一致，也可改用工人容量）
    region_density = defaultdict(int)
    with open(VEHICLE_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            region = int(row['region_id'])
            region_density[region] += 1
    
    density_matrix = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for region, dens in region_density.items():
        ix = region % GRID_X_NUM
        iy = region // GRID_X_NUM
        density_matrix[iy, ix] = dens
    
    task_count_matrix = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for region, num in tasks_per_region.items():
        ix = region % GRID_X_NUM
        iy = region // GRID_X_NUM
        task_count_matrix[iy, ix] = num
    
    fig, ax = plt.subplots(figsize=(12, 9), dpi=120)
    im = ax.imshow(density_matrix, cmap='YlOrRd', interpolation='nearest', origin='lower')
    cbar = plt.colorbar(im, ax=ax, label='Worker Activity (segments)')
    cbar.ax.tick_params(labelsize=10)
    
    max_task = max(1, task_count_matrix.max())
    for iy in range(GRID_Y_NUM):
        for ix in range(GRID_X_NUM):
            task_num = task_count_matrix[iy, ix]
            if task_num > 0:
                x, y = ix, iy
                radius = 0.38 * (task_num / max_task)
                circle = Circle((x, y), radius, color='#4A00E0', alpha=0.9, ec='white', linewidth=1.2, zorder=3)
                ax.add_patch(circle)
                num_str = str(int(task_num))
                shadow_color = 'black'
                for dx, dy in [(0.02,0), (-0.02,0), (0,0.02), (0,-0.02)]:
                    ax.text(x+dx, y+dy, num_str, ha='center', va='center', fontsize=11,
                            color=shadow_color, fontweight='bold', alpha=0.9, zorder=3.5)
                ax.text(x, y, num_str, ha='center', va='center', fontsize=10,
                        color='white', fontweight='bold', zorder=4)
    
    ax.set_xticks(range(GRID_X_NUM))
    ax.set_yticks(range(GRID_Y_NUM))
    ax.set_xlabel('Grid X (longitude direction)', fontsize=11)
    ax.set_ylabel('Grid Y (latitude direction)', fontsize=11)
    ax.set_title('Feasible Tasks (based on worker availability)', fontsize=13, fontweight='bold')
    ax.legend(handles=[Patch(facecolor='#4A00E0', alpha=0.9, edgecolor='white', label='Task count')], loc='upper right')
    
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150, bbox_inches='tight')
    print(f"已保存分布图至 {PLOT_FILE}")
    plt.show()

if __name__ == '__main__':
    main()