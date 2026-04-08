import csv
import json
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Circle

# ==================== 配置 ====================
VEHICLE_FILE = 'experiment2_vehicle.csv'          # 车辆轨迹文件
TASK_CSV = 'experiment2_tasks.csv'                # 输出任务 CSV
TASK_JSON = 'experiment2_task_segments.json'      # 输出任务 JSON
PLOT_FILE = 'experiment2_tasks_distribution.png'  # 输出图片

TOTAL_TASKS = 400                           # 总任务数
SLOT_SEC = 600                              # 10分钟时段长度
SLOTS_PER_DAY = 86400 // SLOT_SEC           # 144个时段

random.seed(2)
# ==============================================

def get_slot_index(t_seconds):
    """秒转时段索引 (0 ~ SLOTS_PER_DAY-1)"""
    return t_seconds // SLOT_SEC

def main():
    # ---------- 1. 读取车辆轨迹，构建工人时空容量 ----------
    # capacity[region][slot] = 不同工人数量
    capacity = defaultdict(lambda: defaultdict(set))
    with open(VEHICLE_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            region = int(row['region_id'])
            start = int(row['start_time'])
            # 使用起始时间所在的时段（也可考虑整个段覆盖的时段，这里简化）
            slot = get_slot_index(start)
            vehicle = row['vehicle_id']
            capacity[region][slot].add(vehicle)
    
    # 转换为整数数量
    capacity_count = {}
    total_capacity = 0
    for region, slot_dict in capacity.items():
        capacity_count[region] = {}
        for slot, workers in slot_dict.items():
            cnt = len(workers)
            capacity_count[region][slot] = cnt
            total_capacity += cnt
    
    if total_capacity == 0:
        print("错误：没有找到任何工人轨迹。")
        return
    
    # ---------- 2. 生成任务 ----------
    candidate_slots = []
    for region, slot_dict in capacity_count.items():
        for slot, cap in slot_dict.items():
            candidate_slots.append((region, slot, cap))
    
    weights = [cap for (_, _, cap) in candidate_slots]
    generated_count = defaultdict(int)  # (region, slot) -> 任务数
    tasks = []
    tasks_by_region = defaultdict(list)
    seq_counter = defaultdict(int)
    
    max_attempts = TOTAL_TASKS * 10
    attempts = 0
    
    while len(tasks) < TOTAL_TASKS and attempts < max_attempts:
        attempts += 1
        slot = random.choices(candidate_slots, weights=weights, k=1)[0]
        region, slot_idx, cap = slot
        
        max_tasks_in_slot = cap
        if generated_count[(region, slot_idx)] >= max_tasks_in_slot:
            continue
        
        max_req = min(3, cap)
        if max_req < 1:
            continue
        required = random.randint(1, 1)   # 固定需要1个工人
        
        # 起始时间：在该时段内随机
        start_sec = random.randint(slot_idx * SLOT_SEC, (slot_idx + 1) * SLOT_SEC - SLOT_SEC)
        end_sec = start_sec + SLOT_SEC
        
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
        generated_count[(region, slot_idx)] += 1
    
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
    
    # ---------- 5. 绘制分布图 ----------
    tasks_per_region = {region: len(tasks_by_region[region]) for region in tasks_by_region}
    
    GRID_X_NUM = 10
    GRID_Y_NUM = 10
    
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