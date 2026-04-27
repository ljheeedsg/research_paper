import csv
import json
import random
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Circle


# ==================== Configuration ====================
VEHICLE_FILE = "experiment2_vehicle.csv"
TASK_CSV = "experiment2_tasks.csv"
TASK_JSON = "experiment2_task_segments.json"
PLOT_FILE = "experiment2_tasks_distribution.png"
SUMMARY_FILE = "experiment2_tasks_summary.json"
ALL_RUNS_SUMMARY_FILE = "experiment2_tasks_summary_all_runs.json"

TOTAL_TASKS = 2000
SLOT_SEC = 600
SLOTS_PER_DAY = 86400 // SLOT_SEC

MAX_REQUIRED_WORKERS = 1
TASK_WEIGHT_MIN = 1.0
TASK_WEIGHT_MAX = 3.0
RANDOM_SEED = 3
NUM_EXPERIMENT_RUNS = 10
SEED_STEP = 1

GRID_X_NUM = 10
GRID_Y_NUM = 10
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


def get_slot_index(t_seconds: int) -> int:
    """把秒转换为 slot 索引"""
    return t_seconds // SLOT_SEC


def load_vehicle_capacity():
    """
    读取车辆轨迹文件，统计每个 (region, slot) 的不同车辆数量。
    capacity[region][slot] = {vehicle_id,...}
    """
    capacity = defaultdict(lambda: defaultdict(set))
    region_density = defaultdict(int)

    with open(VEHICLE_FILE, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required_cols = {"vehicle_id", "region_id", "start_time"}
        if not required_cols.issubset(reader.fieldnames or []):
            raise ValueError(
                f"输入文件缺少必要字段，至少需要: {sorted(required_cols)}，"
                f"实际表头: {reader.fieldnames}"
            )

        for row in reader:
            try:
                vehicle_id = int(row["vehicle_id"])
                region_id = int(row["region_id"])
                start_time = int(row["start_time"])
            except (TypeError, ValueError, KeyError):
                continue

            slot_id = get_slot_index(start_time)
            if slot_id < 0 or slot_id >= SLOTS_PER_DAY:
                continue

            capacity[region_id][slot_id].add(vehicle_id)
            region_density[region_id] += 1

    # 转成整数容量
    capacity_count = {}
    total_capacity = 0
    for region_id, slot_dict in capacity.items():
        capacity_count[region_id] = {}
        for slot_id, workers in slot_dict.items():
            cnt = len(workers)
            if cnt > 0:
                capacity_count[region_id][slot_id] = cnt
                total_capacity += cnt

    return capacity_count, region_density, total_capacity


def build_candidate_slots(capacity_count):
    """
    构造候选任务位置:
    candidate_slots = [(region_id, slot_id, capacity), ...]
    """
    candidate_slots = []
    for region_id, slot_dict in capacity_count.items():
        for slot_id, cap in slot_dict.items():
            if cap > 0:
                candidate_slots.append((region_id, slot_id, cap))
    return candidate_slots


def generate_tasks(candidate_slots):
    """
    按容量加权采样生成任务。
    规则：
    1. 只在 capacity > 0 的 (region, slot) 生成任务
    2. 某个位置的任务数不超过该位置容量
    3. required_workers ∈ [1, min(MAX_REQUIRED_WORKERS, capacity)]
    4. weight 为任务价值权重，与 required_workers 解耦
    """
    if not candidate_slots:
        return [], defaultdict(list)

    weights = [cap for (_, _, cap) in candidate_slots]
    generated_count = defaultdict(int)   # (region, slot) -> task count
    seq_counter = defaultdict(int)       # region -> sequence id

    tasks = []
    tasks_by_region = defaultdict(list)

    max_attempts = TOTAL_TASKS * 20
    attempts = 0

    while len(tasks) < TOTAL_TASKS and attempts < max_attempts:
        attempts += 1

        region_id, slot_id, cap = random.choices(candidate_slots, weights=weights, k=1)[0]

        # 同一位置任务数不能超过容量
        if generated_count[(region_id, slot_id)] >= cap:
            continue

        max_req = min(MAX_REQUIRED_WORKERS, cap)
        if max_req < 1:
            continue

        required_workers = random.randint(1, max_req)
        base_weight = random.uniform(TASK_WEIGHT_MIN, TASK_WEIGHT_MAX)
        weight_bonus = 0.2 * (required_workers - 1)
        weight = round(min(TASK_WEIGHT_MAX, base_weight + weight_bonus), 2)
        true_value = round(random.uniform(0.0, 1.0), 4)

        start_time = slot_id * SLOT_SEC
        end_time = (slot_id + 1) * SLOT_SEC - 1

        seq = seq_counter[region_id]
        task_id = f"t{region_id:02d}_{seq:03d}"

        task_record = {
            "task_id": task_id,
            "region_id": region_id,
            "slot_id": slot_id,
            "start_time": start_time,
            "end_time": end_time,
            "required_workers": required_workers,
            "weight": weight,
            "candidate_capacity": cap,
            "true_value": true_value,
        }

        tasks.append(task_record)
        tasks_by_region[region_id].append(task_record)

        seq_counter[region_id] += 1
        generated_count[(region_id, slot_id)] += 1

    return tasks, tasks_by_region


def summarize_tasks(tasks, tasks_by_region, candidate_slots, total_capacity):
    task_counts = [len(task_list) for task_list in tasks_by_region.values()]
    weights = [task["weight"] for task in tasks]
    required_workers = [task["required_workers"] for task in tasks]

    def safe_mean(values):
        return round(float(np.mean(values)), 4) if values else 0.0

    return {
        "total_tasks": len(tasks),
        "target_tasks": TOTAL_TASKS,
        "candidate_slot_count": len(candidate_slots),
        "total_capacity": total_capacity,
        "regions_with_tasks": len(tasks_by_region),
        "avg_tasks_per_active_region": safe_mean(task_counts),
        "max_tasks_in_region": max(task_counts) if task_counts else 0,
        "avg_required_workers": safe_mean(required_workers),
        "max_required_workers": max(required_workers) if required_workers else 0,
        "avg_task_weight": safe_mean(weights),
    }


def save_tasks_csv(tasks):
    with open(TASK_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "task_id",
            "region_id",
            "slot_id",
            "start_time",
            "end_time",
            "required_workers",
            "weight",
            "candidate_capacity",
            "true_value",
        ])
        for task in tasks:
            writer.writerow([
                task["task_id"],
                task["region_id"],
                task["slot_id"],
                task["start_time"],
                task["end_time"],
                task["required_workers"],
                task["weight"],
                task["candidate_capacity"],
                task["true_value"],
            ])
    print(f"已生成 {TASK_CSV}")


def save_tasks_json(tasks_by_region):
    result = {}
    for region_id, task_list in tasks_by_region.items():
        result[f"region_{region_id}"] = task_list

    with open(TASK_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"已生成 {TASK_JSON}")


def plot_task_distribution(region_density, tasks_by_region):
    """
    背景热力图：工人轨迹段密度
    圆点大小：该区域任务数量
    """
    density_matrix = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for region_id, dens in region_density.items():
        ix = region_id % GRID_X_NUM
        iy = region_id // GRID_X_NUM
        if 0 <= ix < GRID_X_NUM and 0 <= iy < GRID_Y_NUM:
            density_matrix[iy, ix] = dens

    task_count_matrix = np.zeros((GRID_Y_NUM, GRID_X_NUM))
    for region_id, task_list in tasks_by_region.items():
        ix = region_id % GRID_X_NUM
        iy = region_id // GRID_X_NUM
        if 0 <= ix < GRID_X_NUM and 0 <= iy < GRID_Y_NUM:
            task_count_matrix[iy, ix] = len(task_list)

    fig, ax = plt.subplots(figsize=(12, 9), dpi=120)

    im = ax.imshow(
        density_matrix,
        cmap="YlOrRd",
        interpolation="nearest",
        origin="lower",
    )
    cbar = plt.colorbar(im, ax=ax, label="Worker Activity (segments)")
    cbar.ax.tick_params(labelsize=10)

    max_task = max(1, task_count_matrix.max())
    for iy in range(GRID_Y_NUM):
        for ix in range(GRID_X_NUM):
            task_num = task_count_matrix[iy, ix]
            if task_num > 0:
                radius = 0.38 * (task_num / max_task)
                circle = Circle(
                    (ix, iy),
                    radius,
                    color="#4A00E0",
                    alpha=0.9,
                    ec="white",
                    linewidth=1.2,
                    zorder=3,
                )
                ax.add_patch(circle)

                num_str = str(int(task_num))
                # 数字描边阴影
                for dx, dy in [(0.02, 0), (-0.02, 0), (0, 0.02), (0, -0.02)]:
                    ax.text(
                        ix + dx,
                        iy + dy,
                        num_str,
                        ha="center",
                        va="center",
                        fontsize=11,
                        color="black",
                        fontweight="bold",
                        alpha=0.9,
                        zorder=3.5,
                    )
                ax.text(
                    ix,
                    iy,
                    num_str,
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="white",
                    fontweight="bold",
                    zorder=4,
                )

    ax.set_xticks(range(GRID_X_NUM))
    ax.set_yticks(range(GRID_Y_NUM))
    ax.set_xlabel("Grid X (longitude direction)", fontsize=11)
    ax.set_ylabel("Grid Y (latitude direction)", fontsize=11)
    ax.set_title("Generated Tasks based on Worker Capacity", fontsize=13, fontweight="bold")
    ax.legend(
        handles=[Patch(facecolor="#4A00E0", alpha=0.9, edgecolor="white", label="Task count")],
        loc="upper right",
    )

    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"已保存分布图至 {PLOT_FILE}")


def save_json(obj, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"已保存 {filepath}")


def main():
    seeds = [RANDOM_SEED + i * SEED_STEP for i in range(NUM_EXPERIMENT_RUNS)]
    print(f"开始重复实验，共 {NUM_EXPERIMENT_RUNS} 次，随机种子: {seeds}")

    capacity_count, region_density, total_capacity = load_vehicle_capacity()

    if total_capacity == 0:
        print("错误：没有找到任何工人轨迹，无法生成任务。")
        return

    candidate_slots = build_candidate_slots(capacity_count)
    if not candidate_slots:
        print("错误：没有任何可用的 (region, slot) 候选位置。")
        return

    all_summaries = []
    all_runs_summary = []
    representative_tasks = None
    representative_tasks_by_region = None
    for run_idx, seed in enumerate(seeds, start=1):
        print(f"\n===== Run {run_idx}/{NUM_EXPERIMENT_RUNS} | seed={seed} =====")
        set_random_seed(seed)
        tasks, tasks_by_region = generate_tasks(candidate_slots)
        summary = summarize_tasks(tasks, tasks_by_region, candidate_slots, total_capacity)
        all_summaries.append(summary)
        all_runs_summary.append(
            {
                "run_index": run_idx,
                "seed": seed,
                **summary,
            }
        )

        actual_tasks = len(tasks)
        print(f"实际生成任务数: {actual_tasks} / 目标 {TOTAL_TASKS}")
        if actual_tasks < TOTAL_TASKS:
            print("警告：当前时空容量不足，未能达到目标任务数。")

        if representative_tasks is None:
            representative_tasks = tasks
            representative_tasks_by_region = tasks_by_region

    avg_summary = average_dict_records(all_summaries)
    avg_summary["num_experiment_runs"] = NUM_EXPERIMENT_RUNS
    avg_summary["experiment_seeds"] = seeds
    avg_summary["downstream_output_seed"] = seeds[0]

    save_tasks_csv(representative_tasks)
    save_tasks_json(representative_tasks_by_region)
    plot_task_distribution(region_density, representative_tasks_by_region)
    save_json(all_runs_summary, ALL_RUNS_SUMMARY_FILE)
    save_json(avg_summary, SUMMARY_FILE)

    print("平均任务统计:")
    for k, v in avg_summary.items():
        print(f"  {k}: {v}")

    print("全部完成")


if __name__ == "__main__":
    main()
