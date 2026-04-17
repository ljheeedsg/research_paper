import csv
import json
import random
from collections import defaultdict

import numpy as np


# ==================== Configuration ====================
VEHICLE_FILE = "experiment2_vehicle.csv"
TASK_FILE = "experiment2_tasks.csv"
OUTPUT_JSON = "experiment2_worker_options.json"

SLOT_SEC = 600
RANDOM_SEED = 1

# q_ij 噪声
SIGMA_QUALITY = 0.05

# 任务真实值范围
TRUE_VALUE_MIN = 0.0
TRUE_VALUE_MAX = 1.0

# 稳定性参数
TRUSTED_STABILITY = 0.3
UNKNOWN_STABILITY = 1.0
# =======================================================


random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def load_vehicle_segments():
    """
    读取车辆轨迹段，按 vehicle_id 聚合。
    """
    workers = defaultdict(lambda: {
        "cost": None,
        "init_category": None,
        "base_quality": None,
        "stability": None,
        "segments": []
    })

    with open(VEHICLE_FILE, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        required_cols = {
            "vehicle_id", "region_id", "start_time", "end_time",
            "cost", "init_category", "base_quality"
        }
        if not required_cols.issubset(reader.fieldnames or []):
            raise ValueError(
                f"车辆文件缺少必要字段，至少需要: {sorted(required_cols)}，"
                f"实际表头: {reader.fieldnames}"
            )

        for row in reader:
            try:
                vehicle_id = int(row["vehicle_id"])
                region_id = int(row["region_id"])
                start_time = int(row["start_time"])
                end_time = int(row["end_time"])
                cost = float(row["cost"])
                init_category = row["init_category"].strip()
                base_quality = float(row["base_quality"])
            except (TypeError, ValueError, KeyError, AttributeError):
                continue

            # 根据初始类别设置稳定性
            if init_category == "trusted":
                stability = TRUSTED_STABILITY
            else:
                stability = UNKNOWN_STABILITY

            workers[vehicle_id]["cost"] = cost
            workers[vehicle_id]["init_category"] = init_category
            workers[vehicle_id]["base_quality"] = base_quality
            workers[vehicle_id]["stability"] = stability
            workers[vehicle_id]["segments"].append({
                "region_id": region_id,
                "start_time": start_time,
                "end_time": end_time,
                "slot_id": start_time // SLOT_SEC
            })

    # 每个工人的段按时间排序
    for worker in workers.values():
        worker["segments"].sort(key=lambda x: (x["start_time"], x["end_time"], x["region_id"]))

    print(f"加载工人数: {len(workers)}")
    return workers


def load_tasks():
    """
    读取任务数据，并按 region_id 分组。
    同时给每个任务生成一个 true_value。
    """
    tasks = []
    tasks_by_region = defaultdict(list)

    with open(TASK_FILE, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        required_cols = {
            "task_id", "region_id", "slot_id", "start_time", "end_time",
            "required_workers", "weight"
        }
        if not required_cols.issubset(reader.fieldnames or []):
            raise ValueError(
                f"任务文件缺少必要字段，至少需要: {sorted(required_cols)}，"
                f"实际表头: {reader.fieldnames}"
            )

        for row in reader:
            try:
                task = {
                    "task_id": row["task_id"].strip(),
                    "region_id": int(row["region_id"]),
                    "slot_id": int(row["slot_id"]),
                    "start_time": int(row["start_time"]),
                    "end_time": int(row["end_time"]),
                    "required_workers": int(row["required_workers"]),
                    "weight": int(row["weight"]),
                    "true_value": round(random.uniform(TRUE_VALUE_MIN, TRUE_VALUE_MAX), 4),
                }
            except (TypeError, ValueError, KeyError, AttributeError):
                continue

            tasks.append(task)
            tasks_by_region[task["region_id"]].append(task)

    for region_id in tasks_by_region:
        tasks_by_region[region_id].sort(key=lambda x: (x["start_time"], x["end_time"], x["task_id"]))

    print(f"加载任务数: {len(tasks)}")
    return tasks, tasks_by_region


def has_time_overlap(seg_start, seg_end, task_start, task_end):
    """
    判断轨迹段与任务时间是否重叠。
    """
    return not (seg_end < task_start or seg_start > task_end)


def generate_quality(base_quality):
    """
    生成工人 i 执行任务 j 的质量 q_ij:
        q_ij = base_quality_i + epsilon
    """
    q_ij = base_quality + np.random.normal(0, SIGMA_QUALITY)
    q_ij = max(0.0, min(1.0, q_ij))
    return round(float(q_ij), 4)


def generate_task_data(true_value, base_quality, stability):
    """
    生成工人上报数据:
        x_ij = x_j_true + noise
        noise ~ N(0, sigma_i)
        sigma_i = (1 - base_quality_i) * stability_i

    含义：
    - base_quality 越高，误差越小
    - trusted 的 stability 更低，因此数据更稳定
    """
    sigma = max(0.0001, (1.0 - base_quality) * stability)
    value = true_value + np.random.normal(0, sigma)
    return round(float(value), 4)


def build_worker_options(workers, tasks_by_region):
    """
    为每个工人生成可执行任务集合。
    """
    output = {}

    for vehicle_id, worker in workers.items():
        cost = worker["cost"]
        init_category = worker["init_category"]
        base_quality = worker["base_quality"]
        stability = worker["stability"]
        segments = worker["segments"]

        available_slots = set()
        tasks_map = {}

        for seg in segments:
            region_id = seg["region_id"]
            seg_start = seg["start_time"]
            seg_end = seg["end_time"]
            slot_id = seg["slot_id"]

            available_slots.add(slot_id)

            # 只看同 region 的任务
            for task in tasks_by_region.get(region_id, []):
                if not has_time_overlap(seg_start, seg_end, task["start_time"], task["end_time"]):
                    continue

                task_id = task["task_id"]

                # 同一工人可能多个 segment 与同一任务重叠，只保留一次
                if task_id in tasks_map:
                    continue

                quality = generate_quality(base_quality)
                task_data = generate_task_data(task["true_value"], base_quality, stability)

                tasks_map[task_id] = {
                    "task_id": task_id,
                    "region_id": task["region_id"],
                    "slot_id": task["slot_id"],
                    "task_start_time": task["start_time"],
                    "task_end_time": task["end_time"],
                    "required_workers": task["required_workers"],
                    "weight": task["weight"],
                    "quality": quality,
                    "task_data": task_data,
                    "true_value": task["true_value"],
                }

        output[f"worker_{vehicle_id:03d}"] = {
            "worker_id": vehicle_id,
            "cost": cost,
            "init_category": init_category,
            "base_quality": base_quality,
            "stability": stability,
            "available_slots": sorted(available_slots),
            "tasks": sorted(
                tasks_map.values(),
                key=lambda x: (x["slot_id"], x["region_id"], x["task_id"])
            )
        }

    return output


def save_worker_options(worker_options):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(worker_options, f, indent=2, ensure_ascii=False)
    print(f"已生成 {OUTPUT_JSON}")


def main():
    workers = load_vehicle_segments()
    _, tasks_by_region = load_tasks()
    worker_options = build_worker_options(workers, tasks_by_region)
    save_worker_options(worker_options)
    print("全部完成")


if __name__ == "__main__":
    main()