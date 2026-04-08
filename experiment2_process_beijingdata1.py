import csv
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
import random

# ==================== 配置参数 ====================
INPUT_CSV = "dataset/beijing_300_cars_2008-02-03.csv"
OUTPUT_SEG = "experiment2_vehicle.csv"
OUTPUT_PLOT = 'experiment2_grid_partition.png'

LOW_PERCENTILE = 1
HIGH_PERCENTILE = 99
SHIFT_LON = -0.08
SHIFT_LAT = -0.08
GRID_X_NUM = 10
GRID_Y_NUM = 10

COST_MIN = 5
COST_MAX = 20
TRUSTED_RATIO = 0.5

POINT_SIZE = 1
POINT_ALPHA = 0.5

SLOT_SEC = 600   # 10分钟切片

random.seed(2)
# =================================================

def read_input_data():
    rows = []
    taxi_ids = set()
    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        taxi_col = time_col = lat_col = lon_col = None
        for col in fieldnames:
            col_lower = col.lower()
            if col_lower in ('taxi_id', 'taxiid', 'id'):
                taxi_col = col
            elif col_lower in ('time_sec', 'time', 'timestamp'):
                time_col = col
            elif col_lower in ('lat', 'latitude'):
                lat_col = col
            elif col_lower in ('lon', 'longitude'):
                lon_col = col
        if None in (taxi_col, time_col, lat_col, lon_col):
            raise ValueError("CSV 缺少必要的列")
        for row in reader:
            try:
                orig_id = row[taxi_col].strip()
                time_sec = int(float(row[time_col]))
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                rows.append((orig_id, time_sec, lat, lon))
                taxi_ids.add(orig_id)
            except:
                continue
    print(f"读取 {len(rows)} 个点，共 {len(taxi_ids)} 辆不同的车")
    return rows, sorted(taxi_ids, key=lambda x: int(x))

def get_shifted_bbox(rows):
    lats = [r[2] for r in rows]
    lons = [r[3] for r in rows]
    lon_min_orig = np.percentile(lons, LOW_PERCENTILE)
    lon_max_orig = np.percentile(lons, HIGH_PERCENTILE)
    lat_min_orig = np.percentile(lats, LOW_PERCENTILE)
    lat_max_orig = np.percentile(lats, HIGH_PERCENTILE)
    width = lon_max_orig - lon_min_orig
    height = lat_max_orig - lat_min_orig
    center_lon_orig = (lon_min_orig + lon_max_orig) / 2.0
    center_lat_orig = (lat_min_orig + lat_max_orig) / 2.0
    center_lon_new = center_lon_orig + SHIFT_LON
    center_lat_new = center_lat_orig + SHIFT_LAT
    lon_min_new = center_lon_new - width / 2.0
    lon_max_new = center_lon_new + width / 2.0
    lat_min_new = center_lat_new - height / 2.0
    lat_max_new = center_lat_new + height / 2.0
    print(f"原始矩形大小: 经度宽度 {width:.6f}, 纬度高度 {height:.6f}")
    print(f"移动后矩形: 经度 [{lon_min_new:.6f}, {lon_max_new:.6f}], 纬度 [{lat_min_new:.6f}, {lat_max_new:.6f}]")
    return lon_min_new, lon_max_new, lat_min_new, lat_max_new

def assign_region_ids(rows, lon_min, lon_max, lat_min, lat_max):
    step_lon = (lon_max - lon_min) / GRID_X_NUM
    step_lat = (lat_max - lat_min) / GRID_Y_NUM
    region_rows = []
    all_points = []
    grid_counts = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for orig_id, ts, lat, lon in rows:
        if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
            continue
        gx = int((lon - lon_min) // step_lon)
        gy = int((lat - lat_min) // step_lat)
        if gx >= GRID_X_NUM:
            gx = GRID_X_NUM - 1
        if gy >= GRID_Y_NUM:
            gy = GRID_Y_NUM - 1
        region_id = gy * GRID_X_NUM + gx
        region_rows.append((orig_id, ts, region_id))
        all_points.append((lon, lat))
        grid_counts[gy, gx] += 1
    print(f"矩形内点数: {len(region_rows)} (占比 {len(region_rows)/len(rows)*100:.1f}%)")
    return region_rows, all_points, grid_counts

def build_trajectory_segments(region_rows):
    groups = defaultdict(list)
    for orig_id, ts, rid in region_rows:
        groups[orig_id].append((ts, rid))
    segments = []
    for orig_id, points in groups.items():
        points.sort(key=lambda x: x[0])
        for i in range(len(points) - 1):
            start = points[i][0] if i == 0 else points[i][0] + 1
            end = points[i+1][0]
            segments.append((orig_id, points[i][1], start, end))
    return segments

def merge_segments(segments):
    groups = defaultdict(list)
    for orig_id, rid, start, end in segments:
        groups[orig_id].append((rid, start, end))
    merged = []
    for orig_id, segs in groups.items():
        if not segs:
            continue
        cur_rid, cur_start, cur_end = segs[0]
        for rid, start, end in segs[1:]:
            if rid == cur_rid:
                cur_end = end
            else:
                merged.append((orig_id, cur_rid, cur_start, cur_end))
                cur_rid, cur_start, cur_end = rid, start, end
        merged.append((orig_id, cur_rid, cur_start, cur_end))
    return merged

def split_by_slot(merged_segments):
    """按固定时间片（SLOT_SEC秒）切分段，确保每个段不跨片"""
    result = []
    for orig_id, rid, start, end in merged_segments:
        cur = start
        while cur <= end:
            next_boundary = ((cur // SLOT_SEC) + 1) * SLOT_SEC
            seg_end = min(end, next_boundary)
            result.append((orig_id, rid, cur, seg_end))
            cur = seg_end + 1
    return result

def final_renumber_and_attributes(segments, original_ids_sorted):
    present_orig_ids = sorted(set(orig for orig, _, _, _ in segments), key=lambda x: int(x))
    new_id_map = {orig: idx+1 for idx, orig in enumerate(present_orig_ids)}
    attributes = {}
    for new_id in new_id_map.values():
        cost = round(random.uniform(COST_MIN, COST_MAX), 1)
        is_trusted = random.random() < TRUSTED_RATIO
        attributes[new_id] = (cost, is_trusted)
    new_segments = []
    for orig_id, rid, start, end in segments:
        new_id = new_id_map[orig_id]
        cost, is_trusted = attributes[new_id]
        new_segments.append((new_id, rid, start, end, cost, is_trusted))
    print(f"实际有轨迹段的车辆数: {len(present_orig_ids)}，新ID范围 1 ~ {len(present_orig_ids)}")
    return new_segments

def save_csv(segments, filepath):
    segments_sorted = sorted(segments, key=lambda x: x[0])
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['vehicle_id', 'region_id', 'start_time', 'end_time', 'cost', 'is_trusted'])
        writer.writerows(segments_sorted)
    print(f"已保存 {filepath}，共 {len(segments_sorted)} 个段，已按 vehicle_id 排序")

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
    ax1.set_title(f'Shifted dense region (Δlon={SHIFT_LON}, Δlat={SHIFT_LAT})\n{GRID_X_NUM}×{GRID_Y_NUM} grid')
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
    lon_min, lon_max, lat_min, lat_max = get_shifted_bbox(rows)
    region_rows, all_points, grid_counts = assign_region_ids(rows, lon_min, lon_max, lat_min, lat_max)
    if not region_rows:
        print("矩形内无点")
        return
    segments = build_trajectory_segments(region_rows)
    merged = merge_segments(segments)
    slot_split = split_by_slot(merged)
    final_segments = final_renumber_and_attributes(slot_split, original_ids)
    save_csv(final_segments, OUTPUT_SEG)
    plot_grid(lon_min, lon_max, lat_min, lat_max, all_points, grid_counts)
    print("全部完成")

if __name__ == '__main__':
    main()