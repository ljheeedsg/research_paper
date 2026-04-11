import csv
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
import random

# ==================== 配置参数 ====================
INPUT_CSV = "dataset/Chicago_points.csv"
OUTPUT_SEG = "experiment3_vehicle.csv"
OUTPUT_PLOT = "experiment3_grid_partition.png"

GRID_X_NUM = 10
GRID_Y_NUM = 10

COST_MIN = 5
COST_MAX = 20
TRUSTED_RATIO = 0.7

POINT_SIZE = 1
POINT_ALPHA = 0.5

SLOT_SEC = 600                     # 10分钟切片（改为600秒）
MAX_VEHICLES = 2000

# 时间重新分配参数
MIN_DURATION_HOURS = 6
MAX_DURATION_HOURS = 15
SECONDS_PER_HOUR = 3600
MAX_DAY_SEC = 86400

random.seed(42)
# =================================================

def read_input_data():
    """读取 Chicago_points.csv，返回点列表和所有车辆ID（按出现顺序）"""
    rows = []               # (orig_id, time_sec, lat, lon)
    taxi_ids = []           # 保持出现顺序
    seen_ids = set()

    with open(INPUT_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        # 识别列名
        taxi_col = time_col = lat_col = lon_col = None
        for col in fieldnames:
            col_lower = col.lower()
            if col_lower in ('ride_id', 'vehicle_id', 'taxi_id', 'id'):
                taxi_col = col
            elif col_lower in ('time_sec', 'time', 'timestamp'):
                time_col = col
            elif col_lower in ('lat', 'latitude'):
                lat_col = col
            elif col_lower in ('lon', 'lng', 'longitude'):
                lon_col = col

        if None in (taxi_col, time_col, lat_col, lon_col):
            raise ValueError(f"CSV 缺少必要的列。检测到列：{fieldnames}")

        for row in reader:
            try:
                orig_id = row[taxi_col].strip()
                time_sec = int(float(row[time_col]))
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                rows.append((orig_id, time_sec, lat, lon))
                if orig_id not in seen_ids:
                    seen_ids.add(orig_id)
                    taxi_ids.append(orig_id)
            except (ValueError, TypeError):
                continue

    # 只保留前 MAX_VEHICLES 辆车
    if len(taxi_ids) > MAX_VEHICLES:
        keep_ids = set(taxi_ids[:MAX_VEHICLES])
        rows = [r for r in rows if r[0] in keep_ids]
        taxi_ids = taxi_ids[:MAX_VEHICLES]

    print(f"读取 {len(rows)} 个点，共 {len(taxi_ids)} 辆车（限制为前{MAX_VEHICLES}辆）")
    return rows, taxi_ids

def get_bbox(rows):
    """直接使用原始数据的最小最大值作为边界"""
    lats = [r[2] for r in rows]
    lons = [r[3] for r in rows]
    lon_min = min(lons)
    lon_max = max(lons)
    lat_min = min(lats)
    lat_max = max(lats)
    print(f"边界: 经度 [{lon_min:.6f}, {lon_max:.6f}], 纬度 [{lat_min:.6f}, {lat_max:.6f}]")
    return lon_min, lon_max, lat_min, lat_max

def compute_grid_counts(rows, lon_min, lon_max, lat_min, lat_max):
    """计算每个网格内的点数，用于热力图"""
    step_lon = (lon_max - lon_min) / GRID_X_NUM
    step_lat = (lat_max - lat_min) / GRID_Y_NUM
    grid_counts = np.zeros((GRID_Y_NUM, GRID_X_NUM))

    for _, _, lat, lon in rows:
        if lon < lon_min: lon = lon_min
        if lon > lon_max: lon = lon_max
        if lat < lat_min: lat = lat_min
        if lat > lat_max: lat = lat_max
        gx = int((lon - lon_min) // step_lon)
        gy = int((lat - lat_min) // step_lat)
        if gx >= GRID_X_NUM: gx = GRID_X_NUM - 1
        if gy >= GRID_Y_NUM: gy = GRID_Y_NUM - 1
        grid_counts[gy, gx] += 1
    return grid_counts

def get_region_id(lon, lat, lon_min, lon_max, lat_min, lat_max):
    """根据经纬度获取 region_id（复用网格参数）"""
    step_lon = (lon_max - lon_min) / GRID_X_NUM
    step_lat = (lat_max - lat_min) / GRID_Y_NUM
    lon = np.clip(lon, lon_min, lon_max)
    lat = np.clip(lat, lat_min, lat_max)
    gx = int((lon - lon_min) // step_lon)
    gy = int((lat - lat_min) // step_lat)
    gx = np.clip(gx, 0, GRID_X_NUM - 1)
    gy = np.clip(gy, 0, GRID_Y_NUM - 1)
    return gy * GRID_X_NUM + gx

def slice_segment(vehicle_id, region_id, start, end, slot_sec):
    """将单个段按固定时间片切分，返回子段列表"""
    sub_segments = []
    cur = start
    while cur <= end:
        next_boundary = ((cur // slot_sec) + 1) * slot_sec
        seg_end = min(end, next_boundary - 1)
        if seg_end >= cur:
            sub_segments.append((vehicle_id, region_id, cur, seg_end))
        cur = seg_end + 1
    return sub_segments

def add_vehicle_attributes(segments):
    """为每个车辆生成随机的 cost 和 is_trusted，vehicle_id 转为字符串"""
    unique_vehicles = sorted(set(seg[0] for seg in segments))
    attrs = {}
    for vid in unique_vehicles:
        cost = round(random.uniform(COST_MIN, COST_MAX), 1)
        is_trusted = random.random() < TRUSTED_RATIO
        attrs[vid] = (cost, is_trusted)

    final_segments = []
    for vid, rid, start, end in segments:
        cost, trusted = attrs[vid]
        final_segments.append((str(vid), rid, start, end, cost, trusted))
    return final_segments

def save_csv(segments, filepath):
    segments_sorted = sorted(segments, key=lambda x: x[0])
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['vehicle_id', 'region_id', 'start_time', 'end_time', 'cost', 'is_trusted'])
        writer.writerows(segments_sorted)
    print(f"已保存 {filepath}，共 {len(segments_sorted)} 个段")

def plot_grid(lon_min, lon_max, lat_min, lat_max, all_points, grid_counts):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    if all_points:
        lons, lats = zip(*all_points)
        ax1.scatter(lons, lats, s=POINT_SIZE, alpha=POINT_ALPHA, c='blue')
    ax1.plot([lon_min, lon_max, lon_max, lon_min, lon_min],
             [lat_min, lat_min, lat_max, lat_max, lat_min], 'k-', linewidth=2)

    x_edges = np.linspace(lon_min, lon_max, GRID_X_NUM+1)
    y_edges = np.linspace(lat_min, lat_max, GRID_Y_NUM+1)
    for x in x_edges:
        ax1.axvline(x=x, linestyle='--', color='gray', linewidth=0.8, alpha=0.7)
    for y in y_edges:
        ax1.axhline(y=y, linestyle='--', color='gray', linewidth=0.8, alpha=0.7)

    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')
    ax1.set_title(f'Chicago Points with {GRID_X_NUM}×{GRID_Y_NUM} grid\n{len(all_points)} points (first {MAX_VEHICLES} vehicles)')
    ax1.set_xticks(x_edges)
    ax1.set_yticks(y_edges)
    ax1.set_xticklabels([f"{t:.4f}" for t in x_edges], rotation=45, fontsize=8)
    ax1.set_yticklabels([f"{t:.4f}" for t in y_edges], fontsize=8)

    im = ax2.imshow(grid_counts, origin='lower',
                    extent=[lon_min, lon_max, lat_min, lat_max],
                    cmap='hot', interpolation='nearest')
    ax2.set_xlabel('Longitude')
    ax2.set_ylabel('Latitude')
    ax2.set_title('Point Density per Grid')
    plt.colorbar(im, ax=ax2, label='Point count')

    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=150, bbox_inches='tight')
    print(f"已保存图片 {OUTPUT_PLOT}")
    plt.close()

def main():
    rows, original_ids = read_input_data()
    if not rows:
        return

    # 1. 计算网格边界（基于所有点）
    lon_min, lon_max, lat_min, lat_max = get_bbox(rows)
    all_points = [(lon, lat) for (_, _, lat, lon) in rows]
    grid_counts = compute_grid_counts(rows, lon_min, lon_max, lat_min, lat_max)

    # 2. 为每辆车生成一个原始段（使用第一个点的位置和起始时间，重新分配持续时间）
    # 按车辆分组，取每组时间最早的点
    groups = defaultdict(list)
    for orig_id, ts, lat, lon in rows:
        groups[orig_id].append((ts, lat, lon))
    
    vehicle_segments = []   # (vehicle_id, region_id, start_time, end_time)
    for orig_id, points in groups.items():
        points.sort(key=lambda x: x[0])          # 按时间排序
        t_start = points[0][0]                  # 第一个点的时间
        lat_start = points[0][1]
        lon_start = points[0][2]
        region = get_region_id(lon_start, lat_start, lon_min, lon_max, lat_min, lat_max)
        # 随机持续时间（6-15小时）
        duration = random.randint(MIN_DURATION_HOURS * SECONDS_PER_HOUR,
                                  MAX_DURATION_HOURS * SECONDS_PER_HOUR)
        end_time = t_start + duration
        if end_time > MAX_DAY_SEC:
            end_time = MAX_DAY_SEC
        vehicle_segments.append((orig_id, region, t_start, end_time))
    print(f"为 {len(vehicle_segments)} 辆车生成原始段（每辆车一个段，持续 {MIN_DURATION_HOURS}-{MAX_DURATION_HOURS} 小时）")

    # 3. 10分钟切片
    sliced_segments = []
    for vid, rid, s, e in vehicle_segments:
        sliced_segments.extend(slice_segment(vid, rid, s, e, SLOT_SEC))
    print(f"{SLOT_SEC}秒切片后共生成 {len(sliced_segments)} 个段")

    # 4. 添加 cost 和 is_trusted 并输出
    final_segments = add_vehicle_attributes(sliced_segments)
    save_csv(final_segments, OUTPUT_SEG)

    # 5. 绘图（使用原始点的分布）
    plot_grid(lon_min, lon_max, lat_min, lat_max, all_points, grid_counts)

    print("全部完成")

if __name__ == '__main__':
    main()