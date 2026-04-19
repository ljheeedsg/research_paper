from pathlib import Path

import json
import math
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"

ROUND_RESULTS_FILE = "experiment2_random_longrun_round_results.json"
SUMMARY_FILE = "experiment2_random_longrun_summary.json"

PLOT_COVERAGE = "experiment2_random_longrun_coverage_rate.png"
PLOT_COMPLETION = "experiment2_random_longrun_completion_rate.png"
PLOT_AVG_QUALITY = "experiment2_random_longrun_avg_quality.png"

PLOT_CUM_COVERAGE = "experiment2_random_longrun_cumulative_coverage_rate.png"
PLOT_CUM_COMPLETION = "experiment2_random_longrun_cumulative_completion_rate.png"
PLOT_CUM_QUALITY = "experiment2_random_longrun_cumulative_avg_quality.png"

PLOT_PLATFORM_UTILITY = "experiment2_random_longrun_platform_utility.png"
PLOT_CUM_PLATFORM_UTILITY = "experiment2_random_longrun_cumulative_platform_utility.png"
PLOT_ACTIVE_WORKERS = "experiment2_random_longrun_active_workers.png"
PLOT_LEFT_WORKERS = "experiment2_random_longrun_left_workers.png"
PLOT_LEAVE_PROB = "experiment2_random_longrun_avg_leave_probability.png"

TOTAL_SLOTS = 86400 // 600
PER_ROUND_BUDGET = 1000
K = 7
RANDOM_SEED = 13

# 与 CMAB 长期运行版保持一致
DELTA = 0.45

# ===== Platform Utility =====
RHO = 10.0

# ===== Worker Cost =====
WORKER_COST_RATIO = 0.6

# ===== Leave Model =====
BETA0 = -2.5
BETA1 = 0.02
BETA2 = 0.3

SKIP_EMPTY_ROUNDS = True
# =======================================================


random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def sigmoid(x: float) -> float:
    x = max(-20.0, min(20.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def load_worker_options():
    with open(WORKER_OPTIONS_FILE, "r", encoding="utf-8") as f:
        worker_options = json.load(f)
    print(f"已加载工人可选项: {len(worker_options)} 个工人")
    return worker_options


def load_all_tasks_from_workers(worker_options):
    task_dict = {}

    for _, worker in worker_options.items():
        for task in worker.get("tasks", []):
            task_id = task["task_id"]
            if task_id not in task_dict:
                task_dict[task_id] = {
                    "task_id": task_id,
                    "slot_id": int(task["slot_id"]),
                    "region_id": int(task["region_id"]),
                    "required_workers": int(task["required_workers"]),
                    "weight": float(task["weight"]),
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
            tasks_by_slot[int(task["slot_id"])].append(task["task_id"])

        for slot_id in tasks_by_slot:
            tasks_by_slot[slot_id].sort()

        bid_price = float(worker.get("bid_price", worker["cost"]))

        workers[worker_id] = {
            "worker_id": worker_id,
            "cost": bid_price,
            "bid_price": bid_price,
            "init_category": worker["init_category"],
            "base_quality": float(worker["base_quality"]),
            "available_slots": set(worker.get("available_slots", [])),
            "task_map": task_map,
            "tasks_by_slot": tasks_by_slot,

            "is_active": True,
            "cumulative_reward": 0.0,
            "cumulative_cost": 0.0,
            "recent_reward": 0.0,
            "leave_probability": 0.0,
            "selected_rounds": 0,
            "active_rounds": 0,
            "left_round_id": None,
        }

    return workers


def summarize_initial_workers(workers):
    base_qualities = [float(worker["base_quality"]) for worker in workers.values()]
    trusted_qualities = [
        float(worker["base_quality"])
        for worker in workers.values()
        if worker["init_category"] == "trusted"
    ]
    unknown_qualities = [
        float(worker["base_quality"])
        for worker in workers.values()
        if worker["init_category"] == "unknown"
    ]
    malicious_qualities = [
        float(worker["base_quality"])
        for worker in workers.values()
        if worker["init_category"] == "malicious"
    ]

    total_workers = len(workers)

    def safe_mean(values):
        return round(float(np.mean(values)), 4) if values else 0.0

    return {
        "initial_total_workers": total_workers,
        "initial_true_trusted_count": len(trusted_qualities),
        "initial_true_unknown_count": len(unknown_qualities),
        "initial_true_malicious_count": len(malicious_qualities),
        "initial_true_trusted_ratio": round((len(trusted_qualities) / total_workers), 4) if total_workers > 0 else 0.0,
        "initial_avg_base_quality": safe_mean(base_qualities),
        "initial_true_trusted_avg_base_quality": safe_mean(trusted_qualities),
        "initial_true_unknown_avg_base_quality": safe_mean(unknown_qualities),
        "initial_true_malicious_avg_base_quality": safe_mean(malicious_qualities),
    }


def get_available_workers(workers, slot_id):
    return [
        worker for worker in workers.values()
        if slot_id in worker["available_slots"] and worker["is_active"]
    ]


def get_tasks_for_slot(tasks_by_slot, slot_id):
    return tasks_by_slot.get(slot_id, [])


def update_active_rounds(available_workers):
    for worker in available_workers:
        worker["active_rounds"] += 1


def random_select_workers(available_workers, slot_id, budget):
    remaining_candidates = []
    for worker in available_workers:
        bid_task_ids = worker["tasks_by_slot"].get(slot_id, [])
        if not bid_task_ids:
            continue
        remaining_candidates.append({
            "worker_id": worker["worker_id"],
            "bid_price": float(worker["bid_price"]),
            "bid_task_ids": bid_task_ids,
        })

    selected_ids = []
    selection_details = []
    total_cost = 0.0

    while remaining_candidates and len(selected_ids) < K:
        remaining_budget = budget - total_cost
        feasible = [
            item for item in remaining_candidates
            if float(item["bid_price"]) <= remaining_budget
        ]
        if not feasible:
            break

        chosen = random.choice(feasible)
        selected_ids.append(chosen["worker_id"])
        total_cost += float(chosen["bid_price"])

        chosen["selection_order"] = len(selected_ids)
        chosen["remaining_budget_after_selection"] = round(budget - total_cost, 4)
        selection_details.append(chosen)
        remaining_candidates = [
            item for item in remaining_candidates
            if item["worker_id"] != chosen["worker_id"]
        ]

    return selected_ids, round(total_cost, 4), selection_details


def evaluate_round(selected_worker_ids, workers, round_tasks, slot_id, delta):
    task_quality_values = defaultdict(list)
    task_execution = defaultdict(list)

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        for task_id in worker["tasks_by_slot"].get(slot_id, []):
            if task_id in worker["task_map"]:
                q_ij = float(worker["task_map"][task_id]["quality"])
                task_quality_values[task_id].append(q_ij)
                task_execution[task_id].append(worker_id)

    covered_tasks = []
    completed_tasks = []
    uncompleted_tasks = []
    task_results = []

    weighted_completion_quality = 0.0
    total_weight = 0.0

    for task in round_tasks:
        task_id = task["task_id"]
        required_workers = int(task["required_workers"])
        weight = float(task["weight"])
        total_weight += weight

        qualities = task_quality_values.get(task_id, [])
        worker_ids = task_execution.get(task_id, [])

        num_workers = len(worker_ids)
        covered = num_workers > 0
        best_quality = max(qualities) if qualities else 0.0
        avg_quality = float(np.mean(qualities)) if qualities else 0.0
        completed = (num_workers >= required_workers) and (avg_quality >= delta)

        weighted_gain = weight * best_quality
        weighted_completion_quality += weighted_gain
        platform_value = RHO * weight * best_quality

        task_results.append({
            "task_id": task_id,
            "slot_id": slot_id,
            "required_workers": required_workers,
            "weight": weight,
            "covered": covered,
            "completed": completed,
            "num_workers": num_workers,
            "executed_by": worker_ids,
            "best_quality": round(best_quality, 4),
            "avg_quality": round(avg_quality, 4),
            "weighted_gain": round(weighted_gain, 4),
            "platform_value": round(platform_value, 4),
        })

        if covered:
            covered_tasks.append(task_id)
        if completed:
            completed_tasks.append(task_id)
        else:
            uncompleted_tasks.append(task_id)

    num_tasks = len(round_tasks)
    num_covered = len(covered_tasks)
    num_completed = len(completed_tasks)
    coverage_rate = (num_covered / num_tasks) if num_tasks > 0 else 0.0
    completion_rate = (num_completed / num_tasks) if num_tasks > 0 else 0.0
    normalized_completion_quality = (
        weighted_completion_quality / total_weight
        if total_weight > 0 else 0.0
    )

    covered_qualities = [tr["best_quality"] for tr in task_results if tr["covered"]]
    avg_quality_t = float(np.mean(covered_qualities)) if covered_qualities else 0.0

    return {
        "num_tasks": num_tasks,
        "num_covered": num_covered,
        "num_completed": num_completed,
        "coverage_rate": round(coverage_rate, 4),
        "completion_rate": round(completion_rate, 4),
        "avg_quality": round(avg_quality_t, 4),
        "weighted_completion_quality": round(weighted_completion_quality, 4),
        "normalized_completion_quality": round(normalized_completion_quality, 4),
        "total_task_weight": round(total_weight, 4),
        "covered_tasks": covered_tasks,
        "completed_tasks": completed_tasks,
        "uncompleted_tasks": uncompleted_tasks,
        "task_results": task_results,
    }


def compute_platform_utility(eval_result, selected_worker_ids, workers):
    platform_task_value = sum(
        float(task_result["platform_value"])
        for task_result in eval_result["task_results"]
    )
    platform_payment = sum(
        float(workers[worker_id]["bid_price"])
        for worker_id in selected_worker_ids
    )
    platform_utility = platform_task_value - platform_payment

    return {
        "platform_task_value": round(platform_task_value, 4),
        "platform_payment": round(platform_payment, 4),
        "platform_utility": round(platform_utility, 4),
    }


def update_worker_reward_cost(selected_worker_ids, workers):
    selected_set = set(selected_worker_ids)

    for worker_id, worker in workers.items():
        if worker_id in selected_set:
            reward_t = float(worker["bid_price"])
            cost_t = WORKER_COST_RATIO * reward_t

            worker["recent_reward"] = reward_t
            worker["cumulative_reward"] += reward_t
            worker["cumulative_cost"] += cost_t
            worker["selected_rounds"] += 1
        else:
            worker["recent_reward"] = 0.0


def update_worker_leave_state(workers, round_id):
    left_worker_ids = []
    leave_probabilities = []

    for worker in workers.values():
        if not worker["is_active"]:
            continue

        avg_reward = worker["cumulative_reward"] / max(1, worker["selected_rounds"])
        leave_probability = sigmoid(
            BETA0
            + BETA1 * float(worker["cumulative_cost"])
            - BETA2 * float(avg_reward)
        )

        worker["leave_probability"] = float(leave_probability)
        leave_probabilities.append(float(leave_probability))

        if random.random() < leave_probability:
            worker["is_active"] = False
            worker["left_round_id"] = round_id
            left_worker_ids.append(worker["worker_id"])

    avg_leave_probability = float(np.mean(leave_probabilities)) if leave_probabilities else 0.0

    return {
        "left_worker_ids": left_worker_ids,
        "num_left_workers_this_round": len(left_worker_ids),
        "avg_leave_probability": round(avg_leave_probability, 4),
    }


def update_cumulative_metrics(round_result, cumulative_state):
    covered_task_results = [
        tr for tr in round_result["task_results"] if tr["covered"]
    ]

    cumulative_state["num_tasks"] += round_result["num_tasks"]
    cumulative_state["num_covered"] += round_result["num_covered"]
    cumulative_state["num_completed"] += round_result["num_completed"]
    cumulative_state["task_weight_sum"] += round_result["total_task_weight"]
    cumulative_state["weighted_completion_quality_sum"] += round_result["weighted_completion_quality"]
    cumulative_state["quality_sum"] += sum(
        float(tr["best_quality"]) for tr in covered_task_results
    )
    cumulative_state["quality_count"] += len(covered_task_results)

    cumulative_state["platform_task_value_sum"] += round_result["platform_task_value"]
    cumulative_state["platform_payment_sum"] += round_result["platform_payment"]
    cumulative_state["platform_utility_sum"] += round_result["platform_utility"]

    cumulative_coverage_rate = (
        cumulative_state["num_covered"] / cumulative_state["num_tasks"]
        if cumulative_state["num_tasks"] > 0 else 0.0
    )
    cumulative_completion_rate = (
        cumulative_state["num_completed"] / cumulative_state["num_tasks"]
        if cumulative_state["num_tasks"] > 0 else 0.0
    )
    cumulative_normalized_completion_quality = (
        cumulative_state["weighted_completion_quality_sum"] / cumulative_state["task_weight_sum"]
        if cumulative_state["task_weight_sum"] > 0 else 0.0
    )
    cumulative_avg_quality = (
        cumulative_state["quality_sum"] / cumulative_state["quality_count"]
        if cumulative_state["quality_count"] > 0 else 0.0
    )

    round_result["cumulative_num_tasks"] = cumulative_state["num_tasks"]
    round_result["cumulative_num_covered"] = cumulative_state["num_covered"]
    round_result["cumulative_num_completed"] = cumulative_state["num_completed"]
    round_result["cumulative_coverage_rate"] = round(cumulative_coverage_rate, 4)
    round_result["cumulative_completion_rate"] = round(cumulative_completion_rate, 4)
    round_result["cumulative_normalized_completion_quality"] = round(
        cumulative_normalized_completion_quality, 4
    )
    round_result["cumulative_avg_quality"] = round(cumulative_avg_quality, 4)
    round_result["cumulative_platform_task_value"] = round(cumulative_state["platform_task_value_sum"], 4)
    round_result["cumulative_platform_payment"] = round(cumulative_state["platform_payment_sum"], 4)
    round_result["cumulative_platform_utility"] = round(cumulative_state["platform_utility_sum"], 4)


def compute_cumulative_summary(round_results):
    cumulative_state = {
        "num_tasks": 0,
        "num_covered": 0,
        "num_completed": 0,
        "task_weight_sum": 0.0,
        "weighted_completion_quality_sum": 0.0,
        "quality_sum": 0.0,
        "quality_count": 0,
        "platform_task_value_sum": 0.0,
        "platform_payment_sum": 0.0,
        "platform_utility_sum": 0.0,
    }

    for round_result in round_results:
        covered_task_results = [
            tr for tr in round_result["task_results"] if tr["covered"]
        ]
        cumulative_state["num_tasks"] += round_result["num_tasks"]
        cumulative_state["num_covered"] += round_result["num_covered"]
        cumulative_state["num_completed"] += round_result["num_completed"]
        cumulative_state["task_weight_sum"] += round_result["total_task_weight"]
        cumulative_state["weighted_completion_quality_sum"] += round_result["weighted_completion_quality"]
        cumulative_state["quality_sum"] += sum(
            float(tr["best_quality"]) for tr in covered_task_results
        )
        cumulative_state["quality_count"] += len(covered_task_results)
        cumulative_state["platform_task_value_sum"] += round_result["platform_task_value"]
        cumulative_state["platform_payment_sum"] += round_result["platform_payment"]
        cumulative_state["platform_utility_sum"] += round_result["platform_utility"]

    cumulative_coverage_rate = (
        cumulative_state["num_covered"] / cumulative_state["num_tasks"]
        if cumulative_state["num_tasks"] > 0 else 0.0
    )
    cumulative_completion_rate = (
        cumulative_state["num_completed"] / cumulative_state["num_tasks"]
        if cumulative_state["num_tasks"] > 0 else 0.0
    )
    cumulative_normalized_completion_quality = (
        cumulative_state["weighted_completion_quality_sum"] / cumulative_state["task_weight_sum"]
        if cumulative_state["task_weight_sum"] > 0 else 0.0
    )
    cumulative_avg_quality = (
        cumulative_state["quality_sum"] / cumulative_state["quality_count"]
        if cumulative_state["quality_count"] > 0 else 0.0
    )

    return {
        "cumulative_num_tasks": cumulative_state["num_tasks"],
        "cumulative_num_covered": cumulative_state["num_covered"],
        "cumulative_num_completed": cumulative_state["num_completed"],
        "cumulative_coverage_rate": round(cumulative_coverage_rate, 4),
        "cumulative_completion_rate": round(cumulative_completion_rate, 4),
        "cumulative_normalized_completion_quality": round(cumulative_normalized_completion_quality, 4),
        "cumulative_avg_quality": round(cumulative_avg_quality, 4),
        "cumulative_platform_task_value": round(cumulative_state["platform_task_value_sum"], 4),
        "cumulative_platform_payment": round(cumulative_state["platform_payment_sum"], 4),
        "cumulative_platform_utility": round(cumulative_state["platform_utility_sum"], 4),
    }


def summarize_worker_longrun_stats(workers):
    active_workers = [w for w in workers.values() if w["is_active"]]
    left_workers = [w for w in workers.values() if not w["is_active"]]

    def safe_mean(values):
        return round(float(np.mean(values)), 4) if values else 0.0

    return {
        "final_num_active_workers": len(active_workers),
        "final_num_left_workers": len(left_workers),
        "final_avg_cumulative_reward": safe_mean([w["cumulative_reward"] for w in workers.values()]),
        "final_avg_cumulative_cost": safe_mean([w["cumulative_cost"] for w in workers.values()]),
        "final_avg_selected_rounds": safe_mean([w["selected_rounds"] for w in workers.values()]),
        "final_avg_active_rounds": safe_mean([w["active_rounds"] for w in workers.values()]),
        "final_avg_leave_probability_active_workers": safe_mean([w["leave_probability"] for w in active_workers]),
    }


def summarize_results(round_results, workers, initial_stats=None):
    valid_rounds = [r for r in round_results if r["num_tasks"] > 0]

    def safe_mean(key, data):
        if not data:
            return 0.0
        return round(float(np.mean([r[key] for r in data])), 4)

    cumulative_all = compute_cumulative_summary(valid_rounds)
    worker_stats = summarize_worker_longrun_stats(workers)

    summary = {
        "selection_logic": "random_recruitment_longrun_under_budget_and_k_cap",
        "max_selected_workers_per_round": K,
        "total_rounds_recorded": len(round_results),
        "total_non_empty_rounds": len(valid_rounds),

        "avg_num_selected_workers_all_non_empty": safe_mean("num_selected_workers", valid_rounds),
        "avg_coverage_rate_all_non_empty": safe_mean("coverage_rate", valid_rounds),
        "avg_completion_rate_all_non_empty": safe_mean("completion_rate", valid_rounds),
        "avg_avg_quality_all_non_empty": safe_mean("avg_quality", valid_rounds),
        "avg_normalized_completion_quality_all_non_empty": safe_mean(
            "normalized_completion_quality", valid_rounds
        ),
        "avg_reward_all_non_empty": safe_mean("reward", valid_rounds),
        "avg_cost_all_non_empty": safe_mean("cost", valid_rounds),
        "avg_efficiency_all_non_empty": safe_mean("efficiency", valid_rounds),

        "avg_platform_task_value_all_non_empty": safe_mean("platform_task_value", valid_rounds),
        "avg_platform_payment_all_non_empty": safe_mean("platform_payment", valid_rounds),
        "avg_platform_utility_all_non_empty": safe_mean("platform_utility", valid_rounds),
        "avg_num_active_workers_all_non_empty": safe_mean("num_active_workers", valid_rounds),
        "avg_num_left_workers_this_round_all_non_empty": safe_mean("num_left_workers_this_round", valid_rounds),
        "avg_leave_probability_all_non_empty": safe_mean("avg_leave_probability", valid_rounds),

        "final_cumulative_coverage_rate_all_non_empty": cumulative_all["cumulative_coverage_rate"],
        "final_cumulative_completion_rate_all_non_empty": cumulative_all["cumulative_completion_rate"],
        "final_cumulative_avg_quality_all_non_empty": cumulative_all["cumulative_avg_quality"],
        "final_cumulative_normalized_completion_quality_all_non_empty": (
            cumulative_all["cumulative_normalized_completion_quality"]
        ),
        "final_cumulative_platform_task_value": cumulative_all["cumulative_platform_task_value"],
        "final_cumulative_platform_payment": cumulative_all["cumulative_platform_payment"],
        "final_cumulative_platform_utility": cumulative_all["cumulative_platform_utility"],
    }

    summary.update(worker_stats)

    if initial_stats:
        summary.update(initial_stats)
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
    initial_stats = summarize_initial_workers(workers)

    print(
        "输入工人统计: "
        f"workers={initial_stats['initial_total_workers']} | "
        f"true_trusted={initial_stats['initial_true_trusted_count']} | "
        f"true_unknown={initial_stats['initial_true_unknown_count']} | "
        f"true_malicious={initial_stats['initial_true_malicious_count']} | "
        f"true_trusted_ratio={initial_stats['initial_true_trusted_ratio']:.4f} | "
        f"avg_base_quality={initial_stats['initial_avg_base_quality']:.4f}"
    )

    round_results = []
    cumulative_state = {
        "num_tasks": 0,
        "num_covered": 0,
        "num_completed": 0,
        "task_weight_sum": 0.0,
        "weighted_completion_quality_sum": 0.0,
        "quality_sum": 0.0,
        "quality_count": 0,
        "platform_task_value_sum": 0.0,
        "platform_payment_sum": 0.0,
        "platform_utility_sum": 0.0,
    }

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)
        update_active_rounds(available_workers)

        selected_worker_ids, cost_t, selection_details = random_select_workers(
            available_workers=available_workers,
            slot_id=slot_id,
            budget=PER_ROUND_BUDGET,
        )

        eval_result = evaluate_round(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            slot_id=slot_id,
            delta=DELTA,
        )

        reward_t = eval_result["weighted_completion_quality"]
        efficiency_t = (reward_t / cost_t) if cost_t > 0 else 0.0

        update_worker_reward_cost(selected_worker_ids, workers)
        platform_result = compute_platform_utility(eval_result, selected_worker_ids, workers)
        leave_result = update_worker_leave_state(workers, round_id)

        current_active_workers = sum(1 for worker in workers.values() if worker["is_active"])
        cumulative_left_workers = sum(1 for worker in workers.values() if not worker["is_active"])

        round_result = {
            "round_id": round_id,
            "slot_id": slot_id,
            "selection_mode": "random_recruitment_longrun_under_budget_and_k_cap",
            "num_available_workers": len(available_workers),
            "num_selected_workers": len(selected_worker_ids),
            "selected_workers": selected_worker_ids,
            "selection_details": selection_details,

            "num_tasks": eval_result["num_tasks"],
            "num_covered": eval_result["num_covered"],
            "num_completed": eval_result["num_completed"],
            "coverage_rate": eval_result["coverage_rate"],
            "completion_rate": eval_result["completion_rate"],
            "avg_quality": eval_result["avg_quality"],
            "weighted_completion_quality": eval_result["weighted_completion_quality"],
            "normalized_completion_quality": eval_result["normalized_completion_quality"],
            "total_task_weight": eval_result["total_task_weight"],
            "reward": round(reward_t, 4),
            "cost": round(cost_t, 4),
            "efficiency": round(efficiency_t, 4),
            "covered_tasks": eval_result["covered_tasks"],
            "completed_tasks": eval_result["completed_tasks"],
            "uncompleted_tasks": eval_result["uncompleted_tasks"],
            "task_results": eval_result["task_results"],

            "platform_task_value": platform_result["platform_task_value"],
            "platform_payment": platform_result["platform_payment"],
            "platform_utility": platform_result["platform_utility"],

            "num_active_workers": current_active_workers,
            "num_left_workers_this_round": leave_result["num_left_workers_this_round"],
            "left_worker_ids_this_round": leave_result["left_worker_ids"],
            "cumulative_left_workers": cumulative_left_workers,
            "avg_leave_probability": leave_result["avg_leave_probability"],
        }

        update_cumulative_metrics(round_result, cumulative_state)
        round_results.append(round_result)

        print(
            f"[Round {round_id:03d}] "
            f"tasks={round_result['num_tasks']} | "
            f"selected={round_result['num_selected_workers']} | "
            f"coverage={round_result['coverage_rate']:.4f} | "
            f"completion={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"platform_utility={round_result['platform_utility']:.2f} | "
            f"active_workers={round_result['num_active_workers']} | "
            f"left_this_round={round_result['num_left_workers_this_round']} | "
            f"cum_utility={round_result['cumulative_platform_utility']:.2f}"
        )

    summary = summarize_results(round_results, workers, initial_stats)

    save_json(round_results, ROUND_RESULTS_FILE)
    save_json(summary, SUMMARY_FILE)

    plot_metric(round_results, "coverage_rate", "Coverage Rate", PLOT_COVERAGE)
    plot_metric(round_results, "completion_rate", "Completion Rate", PLOT_COMPLETION)
    plot_metric(round_results, "avg_quality", "Average Realized Quality", PLOT_AVG_QUALITY)

    plot_metric(round_results, "cumulative_coverage_rate", "Cumulative Coverage Rate", PLOT_CUM_COVERAGE)
    plot_metric(round_results, "cumulative_completion_rate", "Cumulative Completion Rate", PLOT_CUM_COMPLETION)
    plot_metric(round_results, "cumulative_avg_quality", "Cumulative Average Quality", PLOT_CUM_QUALITY)

    plot_metric(round_results, "platform_utility", "Platform Utility", PLOT_PLATFORM_UTILITY)
    plot_metric(round_results, "cumulative_platform_utility", "Cumulative Platform Utility", PLOT_CUM_PLATFORM_UTILITY)
    plot_metric(round_results, "num_active_workers", "Active Workers", PLOT_ACTIVE_WORKERS)
    plot_metric(round_results, "cumulative_left_workers", "Cumulative Left Workers", PLOT_LEFT_WORKERS)
    plot_metric(round_results, "avg_leave_probability", "Average Leave Probability", PLOT_LEAVE_PROB)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

