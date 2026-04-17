import json
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"
ROUND_RESULTS_FILE = "experiment2_random_round_results.json"
SUMMARY_FILE = "experiment2_random_summary.json"

PLOT_COMPLETION = "experiment2_random_completion_rate.png"
PLOT_QUALITY = "experiment2_random_avg_quality.png"
PLOT_CUM_COMPLETION = "experiment2_random_cumulative_completion_rate.png"
PLOT_CUM_QUALITY = "experiment2_random_cumulative_avg_quality.png"
PLOT_REWARD = "experiment2_random_reward.png"
PLOT_EFFICIENCY = "experiment2_random_efficiency.png"

SLOT_SEC = 600
TOTAL_SLOTS = 86400 // SLOT_SEC

PER_ROUND_BUDGET = 50
DELTA = 0.6
RANDOM_SEED = 1

SKIP_EMPTY_ROUNDS = True
# =======================================================


random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def load_worker_options():
    with open(WORKER_OPTIONS_FILE, "r", encoding="utf-8") as f:
        worker_options = json.load(f)
    print(f"已加载工人可选项: {len(worker_options)} 个工人")
    return worker_options


def load_all_tasks_from_workers(worker_options):
    """
    从 worker_options 中收集所有任务，按 slot 分组。
    """
    task_dict = {}

    for _, worker in worker_options.items():
        for task in worker.get("tasks", []):
            task_id = task["task_id"]
            if task_id not in task_dict:
                task_dict[task_id] = {
                    "task_id": task_id,
                    "slot_id": task["slot_id"],
                    "region_id": task["region_id"],
                    "required_workers": task["required_workers"],
                    "weight": task["weight"],
                }

    tasks_by_slot = defaultdict(list)
    for task in task_dict.values():
        tasks_by_slot[task["slot_id"]].append(task)

    for slot_id in tasks_by_slot:
        tasks_by_slot[slot_id].sort(key=lambda x: x["task_id"])

    print(f"从 worker options 中收集到任务: {len(task_dict)} 个")
    return task_dict, tasks_by_slot


def build_worker_profiles(worker_options):
    workers = {}

    for _, worker in worker_options.items():
        worker_id = int(worker["worker_id"])
        tasks = worker.get("tasks", [])

        task_map = {task["task_id"]: task for task in tasks}
        tasks_by_slot = defaultdict(list)
        for task in tasks:
            tasks_by_slot[task["slot_id"]].append(task["task_id"])

        for slot_id in tasks_by_slot:
            tasks_by_slot[slot_id].sort()

        workers[worker_id] = {
            "worker_id": worker_id,
            "cost": float(worker["cost"]),
            "init_category": worker["init_category"],
            "base_quality": float(worker["base_quality"]),
            "available_slots": set(worker.get("available_slots", [])),
            "task_map": task_map,
            "tasks_by_slot": tasks_by_slot,
        }

    return workers


def get_available_workers(workers, slot_id):
    return [
        worker for worker in workers.values()
        if slot_id in worker["available_slots"]
    ]


def get_tasks_for_slot(tasks_by_slot, slot_id):
    return tasks_by_slot.get(slot_id, [])


def random_select_workers(available_workers, slot_id, budget):
    """
    随机招募：
    - 只在本轮有任务可做的工人里随机选
    - 直到预算耗尽
    """
    candidates = []
    for worker in available_workers:
        task_ids = worker["tasks_by_slot"].get(slot_id, [])
        if task_ids:
            candidates.append({
                "worker_id": worker["worker_id"],
                "cost": worker["cost"],
                "task_ids": task_ids,
            })

    random.shuffle(candidates)

    selected_ids = []
    total_cost = 0.0

    for item in candidates:
        if total_cost + item["cost"] > budget:
            continue
        selected_ids.append(item["worker_id"])
        total_cost += item["cost"]

    return selected_ids, round(total_cost, 4), candidates


def evaluate_round(selected_worker_ids, workers, round_tasks, slot_id, delta):
    """
    任务完成条件：
    1. 参与工人数 >= required_workers
    2. 平均质量 >= delta
    """
    task_execution = defaultdict(list)
    task_quality_values = defaultdict(list)

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        for task_id in worker["tasks_by_slot"].get(slot_id, []):
            if task_id in worker["task_map"]:
                q_ij = float(worker["task_map"][task_id]["quality"])
                task_execution[task_id].append(worker_id)
                task_quality_values[task_id].append(q_ij)

    completed_tasks = []
    executed_tasks = []
    failed_tasks = []
    task_results = []

    reward_t = 0.0

    for task in round_tasks:
        task_id = task["task_id"]
        required_workers = int(task["required_workers"])
        weight = float(task["weight"])

        worker_ids = task_execution.get(task_id, [])
        qualities = task_quality_values.get(task_id, [])

        num_workers = len(worker_ids)
        avg_quality = float(np.mean(qualities)) if qualities else 0.0
        executed = (num_workers > 0)

        completed = (num_workers >= required_workers) and (avg_quality >= delta)

        task_result = {
            "task_id": task_id,
            "slot_id": slot_id,
            "required_workers": required_workers,
            "weight": weight,
            "num_workers": num_workers,
            "avg_quality": round(avg_quality, 4),
            "executed_by": worker_ids,
            "executed": executed,
            "completed": completed,
        }
        task_results.append(task_result)

        if executed:
            executed_tasks.append(task_id)

        if completed:
            completed_tasks.append(task_id)
            reward_t += weight
        else:
            failed_tasks.append(task_id)

    num_tasks = len(round_tasks)
    num_executed = len(executed_tasks)
    num_completed = len(completed_tasks)
    completion_rate = (num_completed / num_tasks) if num_tasks > 0 else 0.0

    executed_qualities = [
        tr["avg_quality"] for tr in task_results if tr["executed"]
    ]
    avg_quality_t = float(np.mean(executed_qualities)) if executed_qualities else 0.0

    return {
        "num_tasks": num_tasks,
        "num_executed": num_executed,
        "num_completed": num_completed,
        "completion_rate": round(completion_rate, 4),
        "avg_quality": round(avg_quality_t, 4),
        "reward": round(reward_t, 4),
        "executed_tasks": executed_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "task_results": task_results,
    }


def update_cumulative_metrics(round_result, cumulative_state):
    executed_task_results = [
        tr for tr in round_result["task_results"] if tr["executed"]
    ]

    cumulative_state["num_tasks"] += round_result["num_tasks"]
    cumulative_state["num_completed"] += round_result["num_completed"]
    cumulative_state["quality_sum"] += sum(
        float(tr["avg_quality"]) for tr in executed_task_results
    )
    cumulative_state["quality_count"] += len(executed_task_results)

    cumulative_completion_rate = (
        cumulative_state["num_completed"] / cumulative_state["num_tasks"]
        if cumulative_state["num_tasks"] > 0 else 0.0
    )
    cumulative_avg_quality = (
        cumulative_state["quality_sum"] / cumulative_state["quality_count"]
        if cumulative_state["quality_count"] > 0 else 0.0
    )

    round_result["cumulative_num_tasks"] = cumulative_state["num_tasks"]
    round_result["cumulative_num_completed"] = cumulative_state["num_completed"]
    round_result["cumulative_completion_rate"] = round(cumulative_completion_rate, 4)
    round_result["cumulative_avg_quality"] = round(cumulative_avg_quality, 4)


def compute_cumulative_summary(round_results):
    cumulative_state = {
        "num_tasks": 0,
        "num_completed": 0,
        "quality_sum": 0.0,
        "quality_count": 0,
    }

    for round_result in round_results:
        executed_task_results = [
            tr for tr in round_result["task_results"] if tr["executed"]
        ]
        cumulative_state["num_tasks"] += round_result["num_tasks"]
        cumulative_state["num_completed"] += round_result["num_completed"]
        cumulative_state["quality_sum"] += sum(
            float(tr["avg_quality"]) for tr in executed_task_results
        )
        cumulative_state["quality_count"] += len(executed_task_results)

    cumulative_completion_rate = (
        cumulative_state["num_completed"] / cumulative_state["num_tasks"]
        if cumulative_state["num_tasks"] > 0 else 0.0
    )
    cumulative_avg_quality = (
        cumulative_state["quality_sum"] / cumulative_state["quality_count"]
        if cumulative_state["quality_count"] > 0 else 0.0
    )

    return {
        "cumulative_num_tasks": cumulative_state["num_tasks"],
        "cumulative_num_completed": cumulative_state["num_completed"],
        "cumulative_completion_rate": round(cumulative_completion_rate, 4),
        "cumulative_avg_quality": round(cumulative_avg_quality, 4),
    }


def summarize_results(round_results):
    valid_rounds = [r for r in round_results if r["num_tasks"] > 0]

    def safe_mean(key, data):
        if not data:
            return 0.0
        return round(float(np.mean([r[key] for r in data])), 4)

    cumulative_all = compute_cumulative_summary(valid_rounds)

    summary = {
        "total_rounds_recorded": len(round_results),
        "total_non_empty_rounds": len(valid_rounds),

        "avg_completion_rate": safe_mean("completion_rate", valid_rounds),
        "avg_avg_quality": safe_mean("avg_quality", valid_rounds),
        "avg_reward": safe_mean("reward", valid_rounds),
        "avg_cost": safe_mean("cost", valid_rounds),
        "avg_efficiency": safe_mean("efficiency", valid_rounds),

        "final_cumulative_completion_rate": cumulative_all["cumulative_completion_rate"],
        "final_cumulative_avg_quality": cumulative_all["cumulative_avg_quality"],
    }
    return summary


def save_json(obj, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"已保存 {filepath}")


def plot_metric(round_results, key, ylabel, filename):
    valid = [r for r in round_results if r["num_tasks"] > 0]
    if not valid:
        return

    x = [r["round_id"] for r in valid]
    y = [r[key] for r in valid]

    plt.figure(figsize=(10, 5))
    plt.plot(x, y, marker="o")
    plt.xlabel("Round")
    plt.ylabel(ylabel)
    plt.title(f"{ylabel} per Round")
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"已保存 {filename}")


def main():
    worker_options = load_worker_options()
    _, tasks_by_slot = load_all_tasks_from_workers(worker_options)
    workers = build_worker_profiles(worker_options)

    round_results = []
    cumulative_state = {
        "num_tasks": 0,
        "num_completed": 0,
        "quality_sum": 0.0,
        "quality_count": 0,
    }

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)

        selected_worker_ids, cost_t, selection_details = random_select_workers(
            available_workers, slot_id, PER_ROUND_BUDGET
        )

        eval_result = evaluate_round(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            slot_id=slot_id,
            delta=DELTA,
        )

        reward_t = eval_result["reward"]
        efficiency_t = (reward_t / cost_t) if cost_t > 0 else 0.0

        round_result = {
            "round_id": round_id,
            "slot_id": slot_id,

            "num_available_workers": len(available_workers),
            "num_selected_workers": len(selected_worker_ids),
            "selected_workers": selected_worker_ids,

            "num_tasks": eval_result["num_tasks"],
            "num_executed": eval_result["num_executed"],
            "num_completed": eval_result["num_completed"],
            "completion_rate": eval_result["completion_rate"],
            "avg_quality": eval_result["avg_quality"],
            "reward": round(reward_t, 4),
            "cost": round(cost_t, 4),
            "efficiency": round(efficiency_t, 4),

            "executed_tasks": eval_result["executed_tasks"],
            "completed_tasks": eval_result["completed_tasks"],
            "failed_tasks": eval_result["failed_tasks"],
            "task_results": eval_result["task_results"],
        }

        update_cumulative_metrics(round_result, cumulative_state)
        round_results.append(round_result)

        print(
            f"[Round {round_id:03d}] "
            f"tasks={round_result['num_tasks']} | "
            f"executed={round_result['num_executed']} | "
            f"completed={round_result['num_completed']} | "
            f"completion_rate={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"cum_completion={round_result['cumulative_completion_rate']:.4f} | "
            f"cum_quality={round_result['cumulative_avg_quality']:.4f} | "
            f"reward={round_result['reward']:.2f} | "
            f"cost={round_result['cost']:.2f} | "
            f"eff={round_result['efficiency']:.4f}"
        )

    summary = summarize_results(round_results)

    save_json(round_results, ROUND_RESULTS_FILE)
    save_json(summary, SUMMARY_FILE)

    plot_metric(round_results, "completion_rate", "Completion Rate", PLOT_COMPLETION)
    plot_metric(round_results, "avg_quality", "Average Quality", PLOT_QUALITY)
    plot_metric(round_results, "cumulative_completion_rate", "Cumulative Completion Rate", PLOT_CUM_COMPLETION)
    plot_metric(round_results, "cumulative_avg_quality", "Cumulative Average Quality", PLOT_CUM_QUALITY)
    plot_metric(round_results, "reward", "Reward", PLOT_REWARD)
    plot_metric(round_results, "efficiency", "Efficiency", PLOT_EFFICIENCY)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
