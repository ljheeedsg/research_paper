import csv
import json
import random
from collections import defaultdict

import numpy as np


# ==================== Configuration ====================
VEHICLE_FILE = "experiment2_vehicle.csv"
TASK_FILE = "experiment2_tasks.csv"
OUTPUT_JSON = "experiment2_worker_options.json"
SUMMARY_FILE = "experiment2_worker_options_summary.json"
ALL_RUNS_SUMMARY_FILE = "experiment2_worker_options_summary_all_runs.json"

SLOT_SEC = 600
RANDOM_SEED = 3
NUM_EXPERIMENT_RUNS = 10
SEED_STEP = 1

# q_ij 噪声
SIGMA_QUALITY = 0.03
DATA_SCALE = 0.20

# malicious 偏移范围
MALICIOUS_BIAS_MIN = 0.35
MALICIOUS_BIAS_MAX = 0.70

# true_value 范围
TRUE_VALUE_MIN = 0.0
TRUE_VALUE_MAX = 1.0
# =======================================================


random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


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


def load_vehicle_segments():
    """
    读取第一步输出的 experiment2_vehicle.csv
    按工人聚合轨迹段。
    """
    workers = defaultdict(lambda: {
        "cost": None,
        "init_category": None,
        "base_quality": None,
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

            workers[vehicle_id]["cost"] = cost
            workers[vehicle_id]["init_category"] = init_category
            workers[vehicle_id]["base_quality"] = base_quality
            workers[vehicle_id]["segments"].append({
                "region_id": region_id,
                "start_time": start_time,
                "end_time": end_time,
                "slot_id": start_time // SLOT_SEC
            })

    for worker in workers.values():
        worker["segments"].sort(key=lambda x: (x["start_time"], x["end_time"], x["region_id"]))

    print(f"加载工人数: {len(workers)}")
    return workers


def load_tasks():
    """
    读取第二步输出的 experiment2_tasks.csv
    并为每个任务生成 true_value。
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
                    "weight": float(row["weight"]),
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
    判断工人轨迹段与任务时间窗口是否有交集。
    """
    return not (seg_end < task_start or seg_start > task_end)


def generate_quality(base_quality):
    """
    根据工人基础质量生成某个任务上的实际质量 q_ij。
    """
    q_ij = base_quality + np.random.normal(0, SIGMA_QUALITY)
    q_ij = max(0.0, min(1.0, q_ij))
    return round(float(q_ij), 4)


def generate_task_data(true_value, quality, init_category):
    """
    生成工人对任务的上报数据 x_ij。

    trusted / unknown:
        围绕 true_value 波动，quality 越高噪声越小
    malicious:
        故意偏离 true_value
    """
    if init_category == "malicious":
        direction = random.choice([-1, 1])
        bias = random.uniform(MALICIOUS_BIAS_MIN, MALICIOUS_BIAS_MAX)
        value = true_value + direction * bias
        value = np.clip(value, TRUE_VALUE_MIN, TRUE_VALUE_MAX)
        return round(float(value), 4)

    sigma = max(0.0001, DATA_SCALE * (1.0 - quality))
    value = true_value + np.random.normal(0, sigma)
    value = np.clip(value, TRUE_VALUE_MIN, TRUE_VALUE_MAX)
    return round(float(value), 4)


def build_worker_options(workers, tasks_by_region):
    """
    为每个工人生成可选任务集合。
    规则：
    - 区域相同
    - 时间有交集
    - 同一任务对同一工人只保留一次
    """
    output = {}

    for vehicle_id, worker in workers.items():
        cost = worker["cost"]
        init_category = worker["init_category"]
        base_quality = worker["base_quality"]
        segments = worker["segments"]

        available_slots = set()
        tasks_map = {}

        for seg in segments:
            region_id = seg["region_id"]
            seg_start = seg["start_time"]
            seg_end = seg["end_time"]
            slot_id = seg["slot_id"]

            available_slots.add(slot_id)

            for task in tasks_by_region.get(region_id, []):
                if not has_time_overlap(seg_start, seg_end, task["start_time"], task["end_time"]):
                    continue

                task_id = task["task_id"]
                if task_id in tasks_map:
                    continue

                quality = generate_quality(base_quality)
                task_data = generate_task_data(task["true_value"], quality, init_category)

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
            "bid_price": cost,
            "init_category": init_category,
            "base_quality": base_quality,
            "available_slots": sorted(available_slots),
            "task_option_count": len(tasks_map),
            "tasks": sorted(
                tasks_map.values(),
                key=lambda x: (x["slot_id"], x["region_id"], x["task_id"])
            )
        }

    return output


def summarize_worker_options(worker_options):
    qualities_all = []
    qualities_trusted = []
    qualities_unknown = []
    qualities_malicious = []
    option_qualities = []
    option_abs_errors = []
    option_abs_errors_trusted = []
    option_abs_errors_unknown = []
    option_abs_errors_malicious = []
    total_task_options = 0

    for worker in worker_options.values():
        base_quality = float(worker["base_quality"])
        init_category = worker["init_category"]

        qualities_all.append(base_quality)
        worker_tasks = worker.get("tasks", [])
        total_task_options += len(worker_tasks)

        for task in worker_tasks:
            option_quality = float(task["quality"])
            abs_error = abs(float(task["task_data"]) - float(task["true_value"]))
            option_qualities.append(option_quality)
            option_abs_errors.append(abs_error)

            if init_category == "trusted":
                option_abs_errors_trusted.append(abs_error)
            elif init_category == "malicious":
                option_abs_errors_malicious.append(abs_error)
            else:
                option_abs_errors_unknown.append(abs_error)

        if init_category == "trusted":
            qualities_trusted.append(base_quality)
        elif init_category == "malicious":
            qualities_malicious.append(base_quality)
        else:
            qualities_unknown.append(base_quality)

    total_workers = len(worker_options)
    trusted_count = len(qualities_trusted)
    unknown_count = len(qualities_unknown)
    malicious_count = len(qualities_malicious)
    trusted_ratio = (trusted_count / total_workers) if total_workers > 0 else 0.0
    avg_task_options_per_worker = (
        total_task_options / total_workers
    ) if total_workers > 0 else 0.0

    def safe_mean(values):
        return round(float(np.mean(values)), 4) if values else 0.0

    summary = {
        "total_workers": total_workers,
        "trusted_count": trusted_count,
        "unknown_count": unknown_count,
        "malicious_count": malicious_count,
        "trusted_ratio": round(trusted_ratio, 4),
        "avg_base_quality_all": safe_mean(qualities_all),
        "avg_base_quality_trusted": safe_mean(qualities_trusted),
        "avg_base_quality_unknown": safe_mean(qualities_unknown),
        "avg_base_quality_malicious": safe_mean(qualities_malicious),
        "total_task_options": total_task_options,
        "avg_task_options_per_worker": round(avg_task_options_per_worker, 4),
        "avg_option_quality": safe_mean(option_qualities),
        "avg_abs_data_error": safe_mean(option_abs_errors),
        "avg_abs_data_error_trusted": safe_mean(option_abs_errors_trusted),
        "avg_abs_data_error_unknown": safe_mean(option_abs_errors_unknown),
        "avg_abs_data_error_malicious": safe_mean(option_abs_errors_malicious),
    }
    return summary


def save_worker_options(worker_options):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(worker_options, f, indent=2, ensure_ascii=False)
    print(f"已生成 {OUTPUT_JSON}")


def save_json(obj, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"已保存 {filepath}")


def main():
    seeds = [RANDOM_SEED + i * SEED_STEP for i in range(NUM_EXPERIMENT_RUNS)]
    print(f"开始重复实验，共 {NUM_EXPERIMENT_RUNS} 次，随机种子: {seeds}")

    workers = load_vehicle_segments()

    all_summaries = []
    all_runs_summary = []
    representative_worker_options = None
    for run_idx, seed in enumerate(seeds, start=1):
        print(f"\n===== Run {run_idx}/{NUM_EXPERIMENT_RUNS} | seed={seed} =====")
        set_random_seed(seed)
        _, tasks_by_region = load_tasks()
        worker_options = build_worker_options(workers, tasks_by_region)
        summary = summarize_worker_options(worker_options)
        all_summaries.append(summary)
        all_runs_summary.append(
            {
                "run_index": run_idx,
                "seed": seed,
                **summary,
            }
        )

        print(
            "本次工人可选项统计: "
            f"workers={summary['total_workers']} | "
            f"trusted={summary['trusted_count']} | "
            f"unknown={summary['unknown_count']} | "
            f"malicious={summary['malicious_count']} | "
            f"trusted_ratio={summary['trusted_ratio']:.4f} | "
            f"avg_base_quality={summary['avg_base_quality_all']:.4f} | "
            f"total_task_options={summary['total_task_options']}"
        )

        if representative_worker_options is None:
            representative_worker_options = worker_options

    avg_summary = average_dict_records(all_summaries)
    avg_summary["num_experiment_runs"] = NUM_EXPERIMENT_RUNS
    avg_summary["experiment_seeds"] = seeds
    avg_summary["downstream_output_seed"] = seeds[0]

    save_worker_options(representative_worker_options)
    save_json(all_runs_summary, ALL_RUNS_SUMMARY_FILE)
    save_json(avg_summary, SUMMARY_FILE)

    print(
        "平均工人可选项统计: "
        f"workers={avg_summary['total_workers']} | "
        f"trusted={avg_summary['trusted_count']} | "
        f"unknown={avg_summary['unknown_count']} | "
        f"malicious={avg_summary['malicious_count']} | "
        f"trusted_ratio={avg_summary['trusted_ratio']:.4f} | "
        f"avg_base_quality={avg_summary['avg_base_quality_all']:.4f} | "
        f"trusted_avg_quality={avg_summary['avg_base_quality_trusted']:.4f} | "
        f"unknown_avg_quality={avg_summary['avg_base_quality_unknown']:.4f} | "
        f"malicious_avg_quality={avg_summary['avg_base_quality_malicious']:.4f} | "
        f"total_task_options={avg_summary['total_task_options']} | "
        f"avg_task_options_per_worker={avg_summary['avg_task_options_per_worker']:.4f} | "
        f"avg_option_quality={avg_summary['avg_option_quality']:.4f} | "
        f"avg_abs_data_error={avg_summary['avg_abs_data_error']:.4f}"
    )
    print("全部完成")


if __name__ == "__main__":
    main()
