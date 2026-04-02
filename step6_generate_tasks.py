# generate_tasks_and_plot.py
import csv
import random
from collections import defaultdict
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
from matplotlib.patches import Circle

# ==================== 配置参数 ====================
VEHICLE_FILE = 'step6_vehicle.csv'          # 车辆轨迹文件
TASK_FILE = 'step6_tasks.csv'               # 输出任务文件
PLOT_FILE = 'step6_tasks_distribution.png'  # 输出图片

TOTAL_TASKS = 10                           # 总任务数
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
            # 随机起始时间（保证 end_time <= 86400）
            start = random.randint(TIME_MIN, TIME_MAX)
            end = start + 3600
            # 随机所需工人数 1~3
            required = random.randint(1, 3)
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
    fig, ax = plt.subplots(figsize=(12, 9), dpi=120)  # 放大画布，更清晰

    # 热力图：工人密度（保留原YlOrRd，和你截图一致）
    im = ax.imshow(density_matrix, cmap='YlOrRd', interpolation='nearest', origin='lower')
    cbar = plt.colorbar(im, ax=ax, label='Worker Activity (segments)')
    cbar.ax.tick_params(labelsize=10)

    # 【核心优化】高对比度任务圆 + 清晰数字
    max_task = max(1, task_count_matrix.max())  # 避免除0
    for iy in range(GRID_Y_NUM):
        for ix in range(GRID_X_NUM):
            task_num = task_count_matrix[iy, ix]
            if task_num > 0:
                # 网格中心坐标
                x = ix
                y = iy
                # 优化圆的大小：按任务数比例缩放，最大圆不超过网格的80%
                radius = 0.38 * (task_num / max_task)
                # 高对比度深蓝色圆 + 白色边框，在黄/红背景上超清晰
                circle = Circle(
                    (x, y), radius, 
                    color='#4A00E0',  # 深紫蓝色，和你截图一致
                    alpha=0.9, 
                    ec='white',  # 白色边框，进一步区分
                    linewidth=1.2,
                    zorder=3  # 保证圆在热力图上层
                )
                ax.add_patch(circle)
                
                # 【关键优化】数字增强：添加黑色描边效果
                # 方法：通过绘制多层偏移的黑色文字作为阴影，最后覆盖白色文字
                num_str = str(int(task_num))
                # 阴影参数
                shadow_color = 'black'
                shadow_alpha = 0.9
                # 绘制4个方向的阴影文字（粗体）
                ax.text(x+0.02, y, num_str, ha='center', va='center', fontsize=11, 
                        color=shadow_color, fontweight='bold', alpha=shadow_alpha, zorder=3.5)
                ax.text(x-0.02, y, num_str, ha='center', va='center', fontsize=11, 
                        color=shadow_color, fontweight='bold', alpha=shadow_alpha, zorder=3.5)
                ax.text(x, y+0.02, num_str, ha='center', va='center', fontsize=11, 
                        color=shadow_color, fontweight='bold', alpha=shadow_alpha, zorder=3.5)
                ax.text(x, y-0.02, num_str, ha='center', va='center', fontsize=11, 
                        color=shadow_color, fontweight='bold', alpha=shadow_alpha, zorder=3.5)
                # 绘制最上层的白色核心文字
                ax.text(x, y, num_str, ha='center', va='center', fontsize=10, 
                        color='white', fontweight='bold', zorder=4)

    # 坐标轴优化
    ax.set_xticks(range(GRID_X_NUM))
    ax.set_yticks(range(GRID_Y_NUM))
    ax.set_xlabel('Grid X (longitude direction)', fontsize=11, fontweight='medium')
    ax.set_ylabel('Grid Y (latitude direction)', fontsize=11, fontweight='medium')
    ax.set_title('Worker Activity (heatmap) and Task Count (blue circles)', 
                 fontsize=13, fontweight='bold', pad=15)

    # 图例优化
    legend_elements = [
        Patch(
            facecolor='#4A00E0', 
            alpha=0.9, 
            edgecolor='white', 
            label='Task count (circle size proportional)'
        )
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)

    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150, bbox_inches='tight')
    print(f"已保存优化后的任务分布图至 {PLOT_FILE}")
    plt.show()

if __name__ == '__main__':
    main()