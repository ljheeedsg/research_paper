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
TRUSTED_RATIO = 0.5

POINT_SIZE = 1
POINT_ALPHA = 0.5

SLOT_SEC = 60           # 1分钟切片

MAX_VEHICLES = 2000

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

def build_raw_segments(rows):
    """构建相邻点之间的基本段（含起终点经纬度）"""
    groups = defaultdict(list)
    for orig_id, ts, lat, lon in rows:
        groups[orig_id].append((ts, lat, lon))

    raw_segments = []   # (orig_id, start, end, start_lon, start_lat, end_lon, end_lat)
    for orig_id, points in groups.items():
        points.sort(key=lambda x: x[0])
        for i in range(len(points) - 1):
            t1, lat1, lon1 = points[i]
            t2, lat2, lon2 = points[i+1]
            start = t1 if i == 0 else t1 + 1
            end = t2
            if start > end:
                continue
            raw_segments.append((orig_id, start, end, lon1, lat1, lon2, lat2))

    print(f"生成 {len(raw_segments)} 个基本段")
    return raw_segments

def interpolate(lon1, lat1, lon2, lat2, t_ratio):
    return lon1 + (lon2 - lon1) * t_ratio, lat1 + (lat2 - lat1) * t_ratio

def slice_segments_by_minute(segments, lon_min, lon_max, lat_min, lat_max):
    step_lon = (lon_max - lon_min) / GRID_X_NUM
    step_lat = (lat_max - lat_min) / GRID_Y_NUM

    def get_region_id(lon, lat):
        if lon < lon_min: lon = lon_min
        if lon > lon_max: lon = lon_max
        if lat < lat_min: lat = lat_min
        if lat > lat_max: lat = lat_max
        gx = int((lon - lon_min) // step_lon)
        gy = int((lat - lat_min) // step_lat)
        if gx >= GRID_X_NUM: gx = GRID_X_NUM - 1
        if gy >= GRID_Y_NUM: gy = GRID_Y_NUM - 1
        return gy * GRID_X_NUM + gx

    minute_segments = []   # (orig_id, start, end, region_id)

    for orig_id, start, end, lon1, lat1, lon2, lat2 in segments:
        total_duration = end - start + 1
        start_slot = (start - 1) // SLOT_SEC
        end_slot = (end - 1) // SLOT_SEC

        if start_slot == end_slot:
            mid_sec = (start + end) / 2.0
            t_ratio = (mid_sec - start) / total_duration
            lon_mid, lat_mid = interpolate(lon1, lat1, lon2, lat2, t_ratio)
            region = get_region_id(lon_mid, lat_mid)
            minute_segments.append((orig_id, start, end, region))
        else:
            first_end = (start_slot + 1) * SLOT_SEC
            mid_first = (start + first_end) / 2.0
            t_first = (mid_first - start) / total_duration
            lon_first, lat_first = interpolate(lon1, lat1, lon2, lat2, t_first)
            region_first = get_region_id(lon_first, lat_first)
            minute_segments.append((orig_id, start, first_end, region_first))

            for slot in range(start_slot + 1, end_slot):
                slot_start = slot * SLOT_SEC + 1
                slot_end = (slot + 1) * SLOT_SEC
                mid_slot = (slot_start + slot_end) / 2.0
                t_mid = (mid_slot - start) / total_duration
                lon_mid, lat_mid = interpolate(lon1, lat1, lon2, lat2, t_mid)
                region_mid = get_region_id(lon_mid, lat_mid)
                minute_segments.append((orig_id, slot_start, slot_end, region_mid))

            last_start = end_slot * SLOT_SEC + 1
            mid_last = (last_start + end) / 2.0
            t_last = (mid_last - start) / total_duration
            lon_last, lat_last = interpolate(lon1, lat1, lon2, lat2, t_last)
            region_last = get_region_id(lon_last, lat_last)
            minute_segments.append((orig_id, last_start, end, region_last))

    print(f"分钟切片后共 {len(minute_segments)} 个段")
    return minute_segments

def add_vehicle_attributes(segments):
    """为每个车辆生成随机的 cost 和 is_trusted，并将 vehicle_id 转为字符串"""
    unique_vehicles = sorted(set(seg[0] for seg in segments))
    attrs = {}
    for vid in unique_vehicles:
        cost = round(random.uniform(COST_MIN, COST_MAX), 1)
        is_trusted = random.random() < TRUSTED_RATIO
        attrs[vid] = (cost, is_trusted)

    final_segments = []
    for orig_id, start, end, region in segments:
        cost, trusted = attrs[orig_id]
        # ★ 关键修改：将 vehicle_id 转换为字符串，避免后续脚本类型错误
        final_segments.append((str(orig_id), region, start, end, cost, trusted))
    return final_segments

def save_csv(segments, filepath):
    segments_sorted = sorted(segments, key=lambda x: x[0])  # x[0] 现在是字符串，排序正常
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

    lon_min, lon_max, lat_min, lat_max = get_bbox(rows)
    all_points = [(lon, lat) for (_, _, lat, lon) in rows]
    grid_counts = compute_grid_counts(rows, lon_min, lon_max, lat_min, lat_max)

    raw_segments = build_raw_segments(rows)
    minute_segments = slice_segments_by_minute(raw_segments, lon_min, lon_max, lat_min, lat_max)
    final_segments = add_vehicle_attributes(minute_segments)

    save_csv(final_segments, OUTPUT_SEG)
    plot_grid(lon_min, lon_max, lat_min, lat_max, all_points, grid_counts)

    print("全部完成")

if __name__ == '__main__':
    main()