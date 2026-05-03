import csv
import json
import random
import argparse
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
DATASET_NAME = "rome"

DATASET_REGISTRY = {
    "beijing": {
        "input_csv": "dataset/beijing_300_cars_2008-02-03.csv",
        "preprocessor": "beijing",
    },
    "rome": {
        "input_csv": "dataset/crowd_temperature.csv",
        "preprocessor": "rome",
    },
    "chicago": {
        "input_csv": "dataset/Chicago_points.csv",
        "preprocessor": "chicago",
    },
}

OUTPUT_SEG = "experiment2_vehicle.csv"
OUTPUT_PLOT = "experiment2_grid_partition.png"
SUMMARY_FILE = "experiment2_vehicle_summary.json"
ALL_RUNS_SUMMARY_FILE = "experiment2_vehicle_summary_all_runs.json"

LOW_PERCENTILE = 1
HIGH_PERCENTILE = 99
SHIFT_LON = -0.08
SHIFT_LAT = -0.08
GRID_X_NUM = 10
GRID_Y_NUM = 10

COST_MIN = 5
COST_MAX = 20

# 三类工人比例
TRUSTED_RATIO = 0.2
MALICIOUS_RATIO = 0.4

SLOT_SEC = 600
RANDOM_SEED = 10
NUM_EXPERIMENT_RUNS = 1
SEED_STEP = 1
MAX_DAY_SEC = 86400
ROME_TARGET_DATE = "02-01-14"
CHICAGO_MAX_VEHICLES = 2000
CHICAGO_MIN_DURATION_HOURS = 6
CHICAGO_MAX_DURATION_HOURS = 15
SECONDS_PER_HOUR = 3600

# 三类工人质量区间
TRUSTED_QUALITY_MIN = 0.80
TRUSTED_QUALITY_MAX = 0.9

# unknown 改回原始单一区间分布，不分好中坏。
UNKNOWN_QUALITY_MIN = 0.5
UNKNOWN_QUALITY_MAX = 1

MALICIOUS_QUALITY_MIN = 0.05
MALICIOUS_QUALITY_MAX = 0.25

POINT_SIZE = 1
POINT_ALPHA = 0.5
# =======================================================


random.seed(RANDOM_SEED)


def set_random_seed(seed):
    random.seed(seed)
    np.random.seed(seed)


def average_numeric_values(values):
    if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return int(round(float(np.mean(values))))
    return round(float(np.mean(values)), 4)


def average_dict_records(records):
    averaged = {}
    for key in records[0].keys():
        values = [record[key] for record in records]
        first_value = values[0]
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            averaged[key] = average_numeric_values(values)
        else:
            averaged[key] = first_value
    return averaged


def safe_int_key(value):
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def detect_columns(fieldnames):
    taxi_col = time_col = lat_col = lon_col = None
    for col in fieldnames or []:
        col_lower = col.lower()
        if col_lower in ("ride_id", "vehicle_id", "taxi_id", "taxiid", "id"):
            taxi_col = col
        elif col_lower in ("time_sec", "time", "timestamp"):
            time_col = col
        elif col_lower in ("lat", "latitude"):
            lat_col = col
        elif col_lower in ("lon", "lng", "longitude"):
            lon_col = col

    if None in (taxi_col, time_col, lat_col, lon_col):
        raise ValueError(f"CSV 缺少必要的列，检测到的表头为: {fieldnames}")
    return taxi_col, time_col, lat_col, lon_col


def resolve_dataset_config():
    dataset_key = str(DATASET_NAME).strip().lower()
    if dataset_key not in DATASET_REGISTRY:
        raise ValueError(
            f"不支持的数据集 DATASET_NAME={DATASET_NAME!r}，可选: {sorted(DATASET_REGISTRY.keys())}"
        )
    return dataset_key, DATASET_REGISTRY[dataset_key]


def preprocess_beijing_like(input_csv):
    rows = []
    taxi_ids = set()

    with open(input_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        taxi_col, time_col, lat_col, lon_col = detect_columns(reader.fieldnames)

        for row in reader:
            try:
                orig_id = row[taxi_col].strip()
                time_sec = int(float(row[time_col]))
                lat = float(row[lat_col])
                lon = float(row[lon_col])
            except (TypeError, ValueError, KeyError, AttributeError):
                continue

            rows.append((orig_id, time_sec, lat, lon))
            taxi_ids.add(orig_id)

    print(f"读取 {len(rows)} 个点，共 {len(taxi_ids)} 辆不同的车")
    return rows


def preprocess_beijing(input_csv):
    return preprocess_beijing_like(input_csv)


def time_to_seconds_rome(time_str):
    time_str = str(time_str).strip().split("+")[0]
    time_str = time_str.split(".")[0]
    hour, minute, second = map(int, time_str.split(":"))
    return hour * 3600 + minute * 60 + second


def preprocess_rome(input_csv):
    rows = []
    renumbered_rows = []

    with open(input_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                if str(row["Date"]).strip() != ROME_TARGET_DATE:
                    continue
                orig_id = str(row["Taxi ID"]).strip()
                time_sec = time_to_seconds_rome(row["Time"])
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
            except (TypeError, ValueError, KeyError, AttributeError):
                continue

            rows.append((orig_id, time_sec, lat, lon))

    if not rows:
        raise ValueError(f"Rome 数据集中未找到日期 {ROME_TARGET_DATE} 的有效记录")

    rows.sort(key=lambda item: (safe_int_key(item[0]), item[1], item[2], item[3]))
    unique_ids = sorted({row[0] for row in rows}, key=safe_int_key)
    id_mapping = {orig_id: str(index) for index, orig_id in enumerate(unique_ids, start=1)}

    for orig_id, time_sec, lat, lon in rows:
        renumbered_rows.append((id_mapping[orig_id], time_sec, lat, lon))

    print(
        f"Rome 原始数据筛选日期 {ROME_TARGET_DATE} 后，"
        f"读取 {len(renumbered_rows)} 个点，共 {len(unique_ids)} 辆不同的车"
    )
    return renumbered_rows


def preprocess_chicago(input_csv):
    rows = []
    taxi_ids_in_order = []
    seen_ids = set()

    with open(input_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        taxi_col, time_col, lat_col, lon_col = detect_columns(reader.fieldnames)

        for row in reader:
            try:
                orig_id = row[taxi_col].strip()
                time_sec = int(float(row[time_col]))
                lat = float(row[lat_col])
                lon = float(row[lon_col])
            except (TypeError, ValueError, KeyError, AttributeError):
                continue

            rows.append((orig_id, time_sec, lat, lon))
            if orig_id not in seen_ids:
                seen_ids.add(orig_id)
                taxi_ids_in_order.append(orig_id)

    if len(taxi_ids_in_order) > CHICAGO_MAX_VEHICLES:
        keep_ids = set(taxi_ids_in_order[:CHICAGO_MAX_VEHICLES])
        rows = [row for row in rows if row[0] in keep_ids]
        taxi_ids_in_order = taxi_ids_in_order[:CHICAGO_MAX_VEHICLES]

    print(
        f"Chicago 读取 {len(rows)} 个点，共 {len(taxi_ids_in_order)} 辆车"
        f"（限制为前 {CHICAGO_MAX_VEHICLES} 辆）"
    )
    return rows


def read_input_data():
    dataset_key, dataset_config = resolve_dataset_config()
    input_csv = dataset_config["input_csv"]
    preprocessor_name = dataset_config["preprocessor"]

    preprocessor_map = {
        "beijing": preprocess_beijing,
        "rome": preprocess_rome,
        "chicago": preprocess_chicago,
    }
    if preprocessor_name not in preprocessor_map:
        raise ValueError(
            f"数据集 {dataset_key} 的预处理器 {preprocessor_name!r} 未注册"
        )

    print(f"当前数据集: {dataset_key}")
    print(f"输入文件: {input_csv}")
    return preprocessor_map[preprocessor_name](input_csv)


def get_shifted_bbox(rows):
    lats = np.array([row[2] for row in rows], dtype=float)
    lons = np.array([row[3] for row in rows], dtype=float)

    lon_min_orig = np.percentile(lons, LOW_PERCENTILE)
    lon_max_orig = np.percentile(lons, HIGH_PERCENTILE)
    lat_min_orig = np.percentile(lats, LOW_PERCENTILE)
    lat_max_orig = np.percentile(lats, HIGH_PERCENTILE)

    width = lon_max_orig - lon_min_orig
    height = lat_max_orig - lat_min_orig
    if width <= 0 or height <= 0:
        raise ValueError("根据分位数计算得到的矩形边界无效")

    center_lon_new = (lon_min_orig + lon_max_orig) / 2.0 + SHIFT_LON
    center_lat_new = (lat_min_orig + lat_max_orig) / 2.0 + SHIFT_LAT

    lon_min_new = center_lon_new - width / 2.0
    lon_max_new = center_lon_new + width / 2.0
    lat_min_new = center_lat_new - height / 2.0
    lat_max_new = center_lat_new + height / 2.0

    print(f"原始矩形大小: 经度宽度 {width:.6f}, 纬度高度 {height:.6f}")
    print(
        "移动后矩形: "
        f"经度 [{lon_min_new:.6f}, {lon_max_new:.6f}], "
        f"纬度 [{lat_min_new:.6f}, {lat_max_new:.6f}]"
    )
    return lon_min_new, lon_max_new, lat_min_new, lat_max_new


def get_minmax_bbox(rows, dataset_label="dataset"):
    lats = np.array([row[2] for row in rows], dtype=float)
    lons = np.array([row[3] for row in rows], dtype=float)

    lon_min = float(np.min(lons))
    lon_max = float(np.max(lons))
    lat_min = float(np.min(lats))
    lat_max = float(np.max(lats))

    width = lon_max - lon_min
    height = lat_max - lat_min
    if width <= 0 or height <= 0:
        raise ValueError(f"{dataset_label} 数据集的经纬度边界无效")

    print(
        f"{dataset_label} 原始边界: "
        f"经度 [{lon_min:.6f}, {lon_max:.6f}], 纬度 [{lat_min:.6f}, {lat_max:.6f}]"
    )
    print(
        f"{dataset_label} 网格尺寸: "
        f"经度宽度 {width / GRID_X_NUM:.6f}, 纬度高度 {height / GRID_Y_NUM:.6f}"
    )
    return lon_min, lon_max, lat_min, lat_max


def get_dataset_bbox(rows):
    dataset_key, _ = resolve_dataset_config()
    if dataset_key == "rome":
        return get_minmax_bbox(rows, dataset_label="Rome")
    if dataset_key == "chicago":
        return get_minmax_bbox(rows, dataset_label="Chicago")
    return get_shifted_bbox(rows)


def assign_region_ids(rows, lon_min, lon_max, lat_min, lat_max):
    step_lon = (lon_max - lon_min) / GRID_X_NUM
    step_lat = (lat_max - lat_min) / GRID_Y_NUM
    if step_lon <= 0 or step_lat <= 0:
        raise ValueError("网格步长无效，请检查边界或网格参数")

    region_rows = []
    all_points = []
    grid_counts = np.zeros((GRID_Y_NUM, GRID_X_NUM), dtype=int)

    for orig_id, ts, lat, lon in rows:
        if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
            continue

        gx = int((lon - lon_min) // step_lon)
        gy = int((lat - lat_min) // step_lat)
        gx = min(max(gx, 0), GRID_X_NUM - 1)
        gy = min(max(gy, 0), GRID_Y_NUM - 1)

        region_id = gy * GRID_X_NUM + gx
        region_rows.append((orig_id, ts, region_id))
        all_points.append((lon, lat))
        grid_counts[gy, gx] += 1

    inside_ratio = (len(region_rows) / len(rows) * 100.0) if rows else 0.0
    print(f"矩形内点数: {len(region_rows)} (占比 {inside_ratio:.1f}%)")
    return region_rows, all_points, grid_counts


def build_trajectory_segments(region_rows):
    groups = defaultdict(list)
    for orig_id, ts, rid in region_rows:
        groups[orig_id].append((ts, rid))

    segments = []
    for orig_id, points in groups.items():
        points.sort(key=lambda item: item[0])
        for index in range(len(points) - 1):
            current_ts, current_rid = points[index]
            next_ts, _ = points[index + 1]

            start = current_ts if index == 0 else current_ts + 1
            end = next_ts
            if start <= end:
                segments.append((orig_id, current_rid, start, end))

    print(f"原始轨迹段数量: {len(segments)}")
    return segments


def build_chicago_vehicle_segments(rows, lon_min, lon_max, lat_min, lat_max):
    step_lon = (lon_max - lon_min) / GRID_X_NUM
    step_lat = (lat_max - lat_min) / GRID_Y_NUM
    if step_lon <= 0 or step_lat <= 0:
        raise ValueError("Chicago 网格步长无效，请检查边界或网格参数")

    groups = defaultdict(list)
    for orig_id, ts, lat, lon in rows:
        groups[orig_id].append((ts, lat, lon))

    segments = []
    for orig_id, points in groups.items():
        points.sort(key=lambda item: item[0])
        start_time, lat_start, lon_start = points[0]

        lon_clamped = min(max(lon_start, lon_min), lon_max)
        lat_clamped = min(max(lat_start, lat_min), lat_max)
        gx = int((lon_clamped - lon_min) // step_lon)
        gy = int((lat_clamped - lat_min) // step_lat)
        gx = min(max(gx, 0), GRID_X_NUM - 1)
        gy = min(max(gy, 0), GRID_Y_NUM - 1)
        region_id = gy * GRID_X_NUM + gx

        duration = random.randint(
            CHICAGO_MIN_DURATION_HOURS * SECONDS_PER_HOUR,
            CHICAGO_MAX_DURATION_HOURS * SECONDS_PER_HOUR,
        )
        end_time = min(start_time + duration, MAX_DAY_SEC)
        segments.append((orig_id, region_id, start_time, end_time))

    print(
        f"Chicago 为 {len(segments)} 辆车生成原始段"
        f"（每辆车一个段，持续 {CHICAGO_MIN_DURATION_HOURS}-{CHICAGO_MAX_DURATION_HOURS} 小时）"
    )
    return segments


def merge_segments(segments):
    groups = defaultdict(list)
    for orig_id, rid, start, end in segments:
        groups[orig_id].append((rid, start, end))

    merged = []
    for orig_id, segs in groups.items():
        segs.sort(key=lambda item: item[1])
        cur_rid, cur_start, cur_end = segs[0]

        for rid, start, end in segs[1:]:
            if rid == cur_rid:
                cur_end = max(cur_end, end)
            else:
                merged.append((orig_id, cur_rid, cur_start, cur_end))
                cur_rid, cur_start, cur_end = rid, start, end

        merged.append((orig_id, cur_rid, cur_start, cur_end))

    print(f"合并同区域连续段后数量: {len(merged)}")
    return merged


def split_by_slot(merged_segments):
    result = []
    for orig_id, rid, start, end in merged_segments:
        cur = start
        while cur <= end:
            next_boundary = ((cur // SLOT_SEC) + 1) * SLOT_SEC
            seg_end = min(end, next_boundary)
            if cur <= seg_end:
                result.append((orig_id, rid, cur, seg_end))
            cur = seg_end + 1

    print(f"{SLOT_SEC} 秒切片后轨迹段数量: {len(result)}")
    return result


def sample_base_quality(init_category):
    if init_category == "trusted":
        return round(random.uniform(TRUSTED_QUALITY_MIN, TRUSTED_QUALITY_MAX), 3)
    elif init_category == "malicious":
        return round(random.uniform(MALICIOUS_QUALITY_MIN, MALICIOUS_QUALITY_MAX), 3)
    else:
        return round(random.uniform(UNKNOWN_QUALITY_MIN, UNKNOWN_QUALITY_MAX), 3)


def sample_init_category():
    r = random.random()
    if r < TRUSTED_RATIO:
        return "trusted"
    elif r < TRUSTED_RATIO + MALICIOUS_RATIO:
        return "malicious"
    else:
        return "unknown"


def final_renumber_and_attributes(segments):
    present_orig_ids = sorted(
        {orig_id for orig_id, _, _, _ in segments},
        key=safe_int_key,
    )
    new_id_map = {orig_id: index + 1 for index, orig_id in enumerate(present_orig_ids)}

    vehicle_ids = list(new_id_map.values())
    random.shuffle(vehicle_ids)
    total_workers = len(vehicle_ids)
    trusted_target = int(round(total_workers * TRUSTED_RATIO))
    malicious_target = int(round(total_workers * MALICIOUS_RATIO))
    trusted_target = min(trusted_target, total_workers)
    malicious_target = min(malicious_target, max(0, total_workers - trusted_target))

    trusted_set = set(vehicle_ids[:trusted_target])
    malicious_set = set(vehicle_ids[trusted_target:trusted_target + malicious_target])

    attributes = {}
    for vehicle_id in new_id_map.values():
        cost = round(random.uniform(COST_MIN, COST_MAX), 1)
        if vehicle_id in trusted_set:
            init_category = "trusted"
        elif vehicle_id in malicious_set:
            init_category = "malicious"
        else:
            init_category = "unknown"
        base_quality = sample_base_quality(init_category)
        attributes[vehicle_id] = (cost, init_category, base_quality)

    final_segments = []
    for orig_id, rid, start, end in segments:
        vehicle_id = new_id_map[orig_id]
        cost, init_category, base_quality = attributes[vehicle_id]
        final_segments.append(
            (vehicle_id, rid, start, end, cost, init_category, base_quality)
        )

    print(f"实际有轨迹段的车辆数: {len(present_orig_ids)}")
    return final_segments


def summarize_vehicle_attributes(segments):
    seen = {}
    for vehicle_id, _, _, _, _, init_category, base_quality in segments:
        if vehicle_id not in seen:
            seen[vehicle_id] = (init_category, float(base_quality))

    trusted_qualities = [
        quality for category, quality in seen.values() if category == "trusted"
    ]
    unknown_qualities = [
        quality for category, quality in seen.values() if category == "unknown"
    ]
    malicious_qualities = [
        quality for category, quality in seen.values() if category == "malicious"
    ]
    all_qualities = [quality for _, quality in seen.values()]

    total_workers = len(seen)
    trusted_count = len(trusted_qualities)
    unknown_count = len(unknown_qualities)
    malicious_count = len(malicious_qualities)

    def safe_mean(values):
        return round(float(np.mean(values)), 4) if values else 0.0

    return {
        "total_workers": total_workers,
        "trusted_count": trusted_count,
        "unknown_count": unknown_count,
        "malicious_count": malicious_count,
        "trusted_ratio": round((trusted_count / total_workers), 4) if total_workers > 0 else 0.0,
        "malicious_ratio": round((malicious_count / total_workers), 4) if total_workers > 0 else 0.0,
        "avg_base_quality_all": safe_mean(all_qualities),
        "avg_base_quality_trusted": safe_mean(trusted_qualities),
        "avg_base_quality_unknown": safe_mean(unknown_qualities),
        "avg_base_quality_malicious": safe_mean(malicious_qualities),
    }


def save_json(obj, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"已保存 {filepath}")


def save_csv(segments, filepath):
    segments_sorted = sorted(segments, key=lambda item: (item[0], item[2], item[3], item[1]))
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "vehicle_id",
                "region_id",
                "start_time",
                "end_time",
                "cost",
                "init_category",
                "base_quality",
            ]
        )
        writer.writerows(segments_sorted)

    print(f"已保存 {filepath}，共 {len(segments_sorted)} 个段")


def plot_grid(lon_min, lon_max, lat_min, lat_max, all_points, grid_counts):
    dataset_key, _ = resolve_dataset_config()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    if all_points:
        lons, lats = zip(*all_points)
        if dataset_key == "rome":
            ax1.scatter(
                lons,
                lats,
                s=5,
                alpha=0.9,
                c="navy",
                edgecolors="cyan",
                linewidth=0.2,
            )
            ax1.set_xlabel("Longitude")
            ax1.set_ylabel("Latitude")
            ax1.set_title("GPS Points")
        elif dataset_key == "chicago":
            ax1.scatter(lons, lats, s=POINT_SIZE, alpha=POINT_ALPHA, c="blue")

            ax1.plot(
                [lon_min, lon_max, lon_max, lon_min, lon_min],
                [lat_min, lat_min, lat_max, lat_max, lat_min],
                "k-",
                linewidth=2,
            )

            x_edges = np.linspace(lon_min, lon_max, GRID_X_NUM + 1)
            y_edges = np.linspace(lat_min, lat_max, GRID_Y_NUM + 1)
            for x in x_edges:
                ax1.axvline(x=x, linestyle="--", color="gray", linewidth=0.8, alpha=0.7)
            for y in y_edges:
                ax1.axhline(y=y, linestyle="--", color="gray", linewidth=0.8, alpha=0.7)

            ax1.set_xlabel("Longitude")
            ax1.set_ylabel("Latitude")
            ax1.set_title(
                f"Chicago Points with {GRID_X_NUM}x{GRID_Y_NUM} grid\n"
                f"{len(all_points)} points (first {CHICAGO_MAX_VEHICLES} vehicles)"
            )
            ax1.set_xticks(x_edges)
            ax1.set_yticks(y_edges)
            ax1.set_xticklabels([f"{tick:.4f}" for tick in x_edges], rotation=45, fontsize=8)
            ax1.set_yticklabels([f"{tick:.4f}" for tick in y_edges], fontsize=8)
        else:
            ax1.scatter(lons, lats, s=POINT_SIZE, alpha=POINT_ALPHA, c="blue")

            ax1.plot(
                [lon_min, lon_max, lon_max, lon_min, lon_min],
                [lat_min, lat_min, lat_max, lat_max, lat_min],
                "k-",
                linewidth=2,
            )

            x_edges = np.linspace(lon_min, lon_max, GRID_X_NUM + 1)
            y_edges = np.linspace(lat_min, lat_max, GRID_Y_NUM + 1)
            for x in x_edges:
                ax1.axvline(x=x, linestyle="--", color="gray", linewidth=0.8, alpha=0.7)
            for y in y_edges:
                ax1.axhline(y=y, linestyle="--", color="gray", linewidth=0.8, alpha=0.7)

            ax1.set_xlabel("Longitude")
            ax1.set_ylabel("Latitude")
            ax1.set_title(
                f"Shifted dense region (d_lon={SHIFT_LON}, d_lat={SHIFT_LAT})\n"
                f"{GRID_X_NUM}x{GRID_Y_NUM} grid"
            )
            ax1.set_xticks(x_edges)
            ax1.set_yticks(y_edges)
            ax1.set_xticklabels([f"{tick:.4f}" for tick in x_edges], rotation=45, fontsize=8)
            ax1.set_yticklabels([f"{tick:.4f}" for tick in y_edges], fontsize=8)

    im = ax2.imshow(
        grid_counts,
        origin="lower",
        extent=[lon_min, lon_max, lat_min, lat_max],
        cmap="hot",
        interpolation="nearest",
    )
    ax2.set_xlabel("Longitude")
    ax2.set_ylabel("Latitude")
    ax2.set_title("Point Density per Grid")
    plt.colorbar(im, ax=ax2, label="Point count")

    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"已保存图片 {OUTPUT_PLOT}")


def main():
    global OUTPUT_SEG, OUTPUT_PLOT, SUMMARY_FILE, ALL_RUNS_SUMMARY_FILE
    global TRUSTED_RATIO, MALICIOUS_RATIO, RANDOM_SEED, NUM_EXPERIMENT_RUNS

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-seg", default=OUTPUT_SEG)
    parser.add_argument("--output-plot", default=OUTPUT_PLOT)
    parser.add_argument("--summary-file", default=SUMMARY_FILE)
    parser.add_argument("--all-runs-summary-file", default=ALL_RUNS_SUMMARY_FILE)
    parser.add_argument("--trusted-ratio", type=float, default=TRUSTED_RATIO)
    parser.add_argument("--malicious-ratio", type=float, default=MALICIOUS_RATIO)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--runs", type=int, default=NUM_EXPERIMENT_RUNS)
    args = parser.parse_args()

    OUTPUT_SEG = args.output_seg
    OUTPUT_PLOT = args.output_plot
    SUMMARY_FILE = args.summary_file
    ALL_RUNS_SUMMARY_FILE = args.all_runs_summary_file
    TRUSTED_RATIO = args.trusted_ratio
    MALICIOUS_RATIO = args.malicious_ratio
    RANDOM_SEED = args.seed
    NUM_EXPERIMENT_RUNS = args.runs

    seeds = [RANDOM_SEED + i * SEED_STEP for i in range(NUM_EXPERIMENT_RUNS)]
    print(f"开始重复实验，共 {NUM_EXPERIMENT_RUNS} 次，随机种子: {seeds}")

    dataset_key, _ = resolve_dataset_config()
    rows = read_input_data()
    if not rows:
        print("输入数据为空，程序结束")
        return

    lon_min, lon_max, lat_min, lat_max = get_dataset_bbox(rows)
    region_rows, all_points, grid_counts = assign_region_ids(
        rows, lon_min, lon_max, lat_min, lat_max
    )
    if not region_rows:
        print("矩形内无点，程序结束")
        return

    if dataset_key == "chicago":
        set_random_seed(seeds[0])
        segments = build_chicago_vehicle_segments(rows, lon_min, lon_max, lat_min, lat_max)
    else:
        segments = build_trajectory_segments(region_rows)
    if not segments:
        print("没有生成有效轨迹段，程序结束")
        return

    if dataset_key == "chicago":
        slot_segments = split_by_slot(segments)
    else:
        merged_segments = merge_segments(segments)
        slot_segments = split_by_slot(merged_segments)

    all_summaries = []
    all_runs_summary = []
    representative_segments = None
    for run_idx, seed in enumerate(seeds, start=1):
        print(f"\n===== Run {run_idx}/{NUM_EXPERIMENT_RUNS} | seed={seed} =====")
        set_random_seed(seed)
        final_segments = final_renumber_and_attributes(slot_segments)
        summary = summarize_vehicle_attributes(final_segments)
        all_summaries.append(summary)
        all_runs_summary.append(
            {
                "run_index": run_idx,
                "seed": seed,
                **summary,
            }
        )
        if representative_segments is None:
            representative_segments = final_segments

        print(
            "本次工人统计: "
            f"workers={summary['total_workers']} | "
            f"trusted={summary['trusted_count']} | "
            f"unknown={summary['unknown_count']} | "
            f"malicious={summary['malicious_count']} | "
            f"trusted_ratio={summary['trusted_ratio']:.4f} | "
            f"malicious_ratio={summary['malicious_ratio']:.4f} | "
            f"avg_base_quality={summary['avg_base_quality_all']:.4f}"
        )

    avg_summary = average_dict_records(all_summaries)
    avg_summary["num_experiment_runs"] = NUM_EXPERIMENT_RUNS
    avg_summary["experiment_seeds"] = seeds
    avg_summary["downstream_output_seed"] = seeds[0]

    save_csv(representative_segments, OUTPUT_SEG)
    plot_grid(lon_min, lon_max, lat_min, lat_max, all_points, grid_counts)
    save_json(all_runs_summary, ALL_RUNS_SUMMARY_FILE)
    save_json(avg_summary, SUMMARY_FILE)
    print(
        "平均初始工人统计: "
        f"workers={avg_summary['total_workers']} | "
        f"trusted={avg_summary['trusted_count']} | "
        f"unknown={avg_summary['unknown_count']} | "
        f"malicious={avg_summary['malicious_count']} | "
        f"trusted_ratio={avg_summary['trusted_ratio']:.4f} | "
        f"malicious_ratio={avg_summary['malicious_ratio']:.4f} | "
        f"avg_base_quality={avg_summary['avg_base_quality_all']:.4f} | "
        f"trusted_avg_quality={avg_summary['avg_base_quality_trusted']:.4f} | "
        f"unknown_avg_quality={avg_summary['avg_base_quality_unknown']:.4f} | "
        f"malicious_avg_quality={avg_summary['avg_base_quality_malicious']:.4f}"
    )
    print("全部完成")


if __name__ == "__main__":
    main()
