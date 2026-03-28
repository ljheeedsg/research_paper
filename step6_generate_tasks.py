# generate_tasks_and_plot.py
import csv
import random
from collections import defaultdict
import math

import matplotlib.pyplot as plt
import numpy as np

# ==================== 配置参数 ====================
VEHICLE_FILE = 'step6_vehicle.csv'          # 车辆轨迹文件
TASK_FILE = 'step6_tasks.csv'               # 输出任务文件
PLOT_FILE = 'step6_tasks_distribution.png'  # 输出图片

TOTAL_TASKS = 200                           # 总任务数
TIME_MIN = 0                                 # 任务起始时间最小值（秒）
TIME_MAX = 82800                             # 最大起始时间（23:00），保证窗口不跨午夜

random.seed(42)                             # 固定随机种子，可重复
# ==================================================

def time_to_hour(t):
    """秒转小时（0-23）"""
    return t // 3600

def main():
    # 1. 读取车辆轨迹，统计每个区域的活动密度（轨迹段数量）
    region_density = defaultdict(int)        # region_id -> 轨迹段数
    with open(VEHICLE_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            region = int(row['region_id'])
            region_density[region] += 1

    if not region_density:
        print("错误：车辆轨迹文件为空或无有效区域。")
        return

    # 2. 按密度分配任务数量
    total_density = sum(region_density.values())
    # 按比例计算每个区域的任务数
    tasks_per_region = {}
    remainder = TOTAL_TASKS
    for region, dens in region_density.items():
        n = int(round(dens / total_density * TOTAL_TASKS))
        tasks_per_region[region] = n
        remainder -= n
    # 处理余数：将剩余任务随机分配给有任务的区域
    if remainder != 0:
        region_list = list(tasks_per_region.keys())
        for _ in range(abs(remainder)):
            region = random.choice(region_list)
            tasks_per_region[region] += 1 if remainder > 0 else -1

    # 3. 生成任务
    tasks = []   # 列表，每个元素为 (region_id, start_time, end_time, required_workers)
    task_counter = defaultdict(int)  # 每个区域的序号计数器

    for region, num in tasks_per_region.items():
        for _ in range(num):
            # 随机起始时间（保证 end_time ≤ 86400）
            start = random.randint(TIME_MIN, TIME_MAX)
            end = start + 3600
            # 随机所需工人数 1~3
            required = random.randint(1, 1)
            tasks.append((region, start, end, required))
            task_counter[region] += 1

    # 写入任务文件
    with open(TASK_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['task_id', 'region_id', 'start_time', 'end_time', 'required_workers'])
        for region, start, end, required in tasks:
            # 生成 task_id：t{region:02d}_{序号:02d}
            seq = task_counter[region] - 1   # 因为上面每生成一个就递增，现在用减1
            task_id = f"t{region:02d}_{seq:02d}"
            writer.writerow([task_id, region, start, end, required])

    print(f"已生成 {TASK_FILE}，共 {len(tasks)} 个任务，涉及 {len(tasks_per_region)} 个区域。")

    # 4. 绘制复合图：热力图（工人密度） + 散点（任务）
    # 需要获取经纬度范围（从原始数据中读取，或从 vehicle 文件中推导）
    # 这里我们用车辆文件中的 region_id 映射到网格中心坐标。
    # 由于我们只有 region_id，没有原始经纬度，需要根据网格划分规则重建网格。
    # 假设网格划分与之前预处理时相同：grid_x_num=10, grid_y_num=10，经度范围已知。
    # 我们需要从 step6_vehicle.csv 读取所有经纬度？实际上 vehicle 文件里没有经纬度。
    # 简便方法：从车辆文件中获取所有 region_id，然后根据 region_id 反推网格索引（ix, iy），再计算网格中心。
    # 但我们需要原始的经纬度范围 lon_min, lon_max, lat_min, lat_max。
    # 这些信息在预处理时曾计算过，但当前脚本没有保存。我们可重新计算：遍历车辆文件中的 region_id 无法得到经纬度。
    # 更合理的方式：在预处理脚本中保存这些范围到配置文件，或让任务生成脚本也访问原始点数据。
    # 这里提供一个变通方案：假设我们已经知道这些范围（可从预处理日志中获取），或者直接从车辆文件中提取每个区域的一个代表点。
    # 实际上车辆文件中没有经纬度，因此无法绘制精确位置。
    # 替代方案：绘制网格热力图（区域索引）和任务数量叠加，但不显示实际地理坐标。
    # 我采用简单方案：用区域编号（0-99）作为 x 轴，y 轴为密度，或绘制矩阵热力图。
    # 更直观：绘制一个网格矩阵，每个格子颜色表示工人密度，格子内叠加圆形表示任务数量。
    # 因此不需要经纬度，只需区域索引。

    # 构造网格矩阵 (grid_y_num, grid_x_num)
    GRID_X_NUM = 10
    GRID_Y_NUM = 10

    # 创建工人密度矩阵
    density_matrix = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for region, dens in region_density.items():
        ix = region % GRID_X_NUM
        iy = region // GRID_X_NUM
        density_matrix[iy, ix] = dens

    # 创建任务数量矩阵（用于叠加散点大小）
    task_count_matrix = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for region, num in tasks_per_region.items():
        ix = region % GRID_X_NUM
        iy = region // GRID_X_NUM
        task_count_matrix[iy, ix] = num

    # 绘图
    fig, ax = plt.subplots(figsize=(10, 8))

    # 热力图：工人密度
    im = ax.imshow(density_matrix, cmap='YlOrRd', interpolation='nearest', origin='lower')
    plt.colorbar(im, ax=ax, label='Worker Activity (segments)')

    # 叠加任务点：用圆形大小表示任务数量
    # 为每个有任务的网格画一个圆，半径与任务数量成正比
    for iy in range(GRID_Y_NUM):
        for ix in range(GRID_X_NUM):
            task_num = task_count_matrix[iy, ix]
            if task_num > 0:
                # 网格中心坐标
                x = ix
                y = iy
                # 半径与任务数成正比（可调整缩放）
                radius = 0.2 * (task_num / max(1, task_count_matrix.max())) * 1.5
                circle = plt.Circle((x, y), radius, color='blue', alpha=0.7, ec='black', linewidth=0.5)
                ax.add_patch(circle)
                # 可选：标注任务数量
                ax.text(x, y, str(int(task_num)), ha='center', va='center', fontsize=8, color='white', fontweight='bold')

    ax.set_xticks(range(GRID_X_NUM))
    ax.set_yticks(range(GRID_Y_NUM))
    ax.set_xlabel('Grid X (longitude direction)')
    ax.set_ylabel('Grid Y (latitude direction)')
    ax.set_title('Worker Activity (heatmap) and Task Count (blue circles)')

    # 添加图例（示意）
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='blue', alpha=0.7, edgecolor='black', label='Task count (circle size proportional)')]
    ax.legend(handles=legend_elements, loc='upper right')

    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150)
    print(f"已保存任务分布图至 {PLOT_FILE}")
    plt.show()

if __name__ == '__main__':
    main()