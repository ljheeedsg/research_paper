#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完整数据预处理脚本
从原始出租车温度数据集 crowd_temperature.csv 生成：
- step6_vehicle.csv：车辆轨迹段（算法输入）
- step6_grid_partition.png：网格分布可视化图
"""

import csv
import math
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

# ==================== 配置参数 ====================
# 文件路径
INPUT_FILE = 'dataset/crowd_temperature.csv'
OUTPUT_CSV = 'step6_vehicle.csv'
OUTPUT_PLOT = 'step6_grid_partition.png'

# 数据筛选
TARGET_DATE = '02-01-14'          # 目标日期（日-月-年）

# 网格划分
GRID_X_NUM = 10                    # 经度方向网格数
GRID_Y_NUM = 10                    # 纬度方向网格数

# 车辆属性生成
COST_MIN = 5.0
COST_MAX = 20.0
TRUSTED_RATIO = 0.5               # 可信工人比例

# 随机种子（保证可重复）
random.seed(42)
# ==================================================

def time_to_seconds(t_str):
    """将时间字符串转换为从午夜开始的秒数（忽略时区和毫秒）"""
    # 去掉时区（+01）
    t_str = t_str.split('+')[0]
    # 去掉毫秒（.3687）
    t_str = t_str.split('.')[0]
    h, m, s = map(int, t_str.split(':'))
    return h * 3600 + m * 60 + s

def main():
    # ---------- 步骤1-3：读取、筛选、时间转换、添加 region_id ----------
    rows = []               # 存储 (taxi_id, time, lat, lon, temp, region_id)
    lons = []
    lats = []

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)   # 跳过表头
        for row in reader:
            if len(row) < 6:
                continue
            # 步骤1：日期筛选
            if row[1] != TARGET_DATE:
                continue
            # 步骤2：时间转换
            try:
                taxi_id = row[0]
                time_sec = time_to_seconds(row[2])
                lat = float(row[3])
                lon = float(row[4])
                temp = float(row[5])
                rows.append((taxi_id, time_sec, lat, lon, temp))
                lons.append(lon)
                lats.append(lat)
            except:
                continue

    if not rows:
        print(f"错误：未找到日期 {TARGET_DATE} 的数据。")
        return

    # 按 Taxi ID 排序（升序）
    rows.sort(key=lambda x: int(x[0]))

    # 步骤3：计算经纬度范围
    lon_min, lon_max = min(lons), max(lons)
    lat_min, lat_max = min(lats), max(lats)
    print(f"经度范围: {lon_min:.6f} ~ {lon_max:.6f}")
    print(f"纬度范围: {lat_min:.6f} ~ {lat_max:.6f}")

    # 计算网格尺寸
    grid_size_lon = (lon_max - lon_min) / GRID_X_NUM
    grid_size_lat = (lat_max - lat_min) / GRID_Y_NUM
    print(f"网格划分: {GRID_X_NUM} × {GRID_Y_NUM}")
    print(f"网格尺寸: {grid_size_lon:.6f}° × {grid_size_lat:.6f}°")

    # 为每个点计算 region_id
    new_rows = []      # 存储 (taxi_id, time, region_id, temp)
    grid_counts = defaultdict(int)

    for taxi_id, time_sec, lat, lon, temp in rows:
        # 计算网格索引
        ix = int((lon - lon_min) / grid_size_lon)
        iy = int((lat - lat_min) / grid_size_lat)
        if ix == GRID_X_NUM:
            ix -= 1
        if iy == GRID_Y_NUM:
            iy -= 1
        region_id = iy * GRID_X_NUM + ix
        new_rows.append((taxi_id, time_sec, region_id, temp))
        grid_counts[(ix, iy)] += 1

    # ---------- 步骤4：构建基本轨迹段（连续不重叠） ----------
    # 按车辆分组
    taxi_points = defaultdict(list)
    for taxi_id, time_sec, region_id, _ in new_rows:
        taxi_points[taxi_id].append((time_sec, region_id))

    segments = []   # 每个元素 (taxi_id, region_id, start, end)
    for taxi_id, points in taxi_points.items():
        points.sort(key=lambda x: x[0])   # 按时间排序
        for i in range(len(points) - 1):
            if i == 0:
                start = points[i][0]
            else:
                # 上一段的结束时间 + 1
                start = segments[-1][3] + 1
            end = points[i+1][0]
            region = points[i][1]
            segments.append((taxi_id, region, start, end))

    # ---------- 步骤5：按小时切分（跨整点拆分） ----------
    # 生成所有整点时刻（3600, 7200, ..., 82800）
    hour_boundaries = [h * 3600 for h in range(1, 24)]  # 3600, 7200, ..., 82800

    def split_across_hours(s, e):
        """将区间 [s,e] 拆分为多个子区间，每个完全落在单个小时内。
           返回子区间列表 [(start, end), ...]"""
        subs = []
        cur_start = s
        while cur_start < e:
            # 找到下一个整点边界
            next_boundary = ((cur_start // 3600) + 1) * 3600
            cur_end = min(e, next_boundary)
            subs.append((cur_start, cur_end))
            cur_start = cur_end
        return subs

    new_segments = []
    for taxi_id, region, start, end in segments:
        if start // 3600 != end // 3600:
            sub_intervals = split_across_hours(start, end)
            for sub_start, sub_end in sub_intervals:
                new_segments.append((taxi_id, region, sub_start, sub_end))
        else:
            new_segments.append((taxi_id, region, start, end))

    # ---------- 步骤6：重置车辆ID ----------
    # 收集所有唯一的原始 taxi_id
    unique_taxi_ids = sorted(set(tid for tid, _, _, _ in new_segments), key=lambda x: int(x))
    id_mapping = {tid: idx for idx, tid in enumerate(unique_taxi_ids)}

    reset_segments = []
    for taxi_id, region, start, end in new_segments:
        new_id = id_mapping[taxi_id]
        reset_segments.append((new_id, region, start, end))

    # ---------- 步骤7：生成最终 CSV（添加 cost 和 is_trusted） ----------
    # 为每个 new_id 生成固定属性
    vehicle_attrs = {}
    for new_id in set(tid for tid, _, _, _ in reset_segments):
        cost = round(random.uniform(COST_MIN, COST_MAX), 1)
        is_trusted = random.random() < TRUSTED_RATIO
        vehicle_attrs[new_id] = (cost, is_trusted)

    # 写入 CSV
    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['vehicle_id', 'region_id', 'start_time', 'end_time', 'cost', 'is_trusted'])
        for new_id, region, start, end in reset_segments:
            hour = start // 3600
            vehicle_id = f"v{hour:02d}_{new_id:03d}"
            cost, is_trusted = vehicle_attrs[new_id]
            writer.writerow([vehicle_id, region, start, end, cost, is_trusted])

    print(f"已生成 {OUTPUT_CSV}，共 {len(reset_segments)} 条记录。")
    print(f"涉及 {len(unique_taxi_ids)} 辆车。")

    # ---------- 步骤8：生成网格分布图 ----------
    # 绘制散点图（带网格线）和热力图
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # 左边散点图
    lons = [lon for _, _, lat, lon, _ in rows]   # 重新获取经纬度列表（需要之前的 rows 数据）
    lats = [lat for _, _, lat, lon, _ in rows]
    ax1.scatter(lons, lats, s=1, alpha=0.5, c='blue')
    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')
    ax1.set_title('Original GPS Points')
    ax1.grid(True, linestyle='--', alpha=0.6)

    # 绘制网格线
    x_ticks = np.linspace(lon_min, lon_max, GRID_X_NUM + 1)
    y_ticks = np.linspace(lat_min, lat_max, GRID_Y_NUM + 1)
    ax1.set_xticks(x_ticks)
    ax1.set_yticks(y_ticks)
    ax1.set_xticklabels([f"{t:.4f}" for t in x_ticks], rotation=45, fontsize=8)
    ax1.set_yticklabels([f"{t:.4f}" for t in y_ticks], fontsize=8)

    # 右边热力图
    heatmap = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for (ix, iy), cnt in grid_counts.items():
        heatmap[iy, ix] = cnt

    im = ax2.imshow(heatmap, origin='lower',
                    extent=[lon_min, lon_max, lat_min, lat_max],
                    cmap='hot', interpolation='nearest')
    ax2.set_xlabel('Longitude')
    ax2.set_ylabel('Latitude')
    ax2.set_title('Point Density per Grid')
    plt.colorbar(im, ax=ax2, label='Point count')

    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=150)
    print(f"已保存分布图至 {OUTPUT_PLOT}")
    plt.show()

if __name__ == '__main__':
    main()