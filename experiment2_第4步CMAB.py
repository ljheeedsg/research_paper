import json
import math
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"
ROUND_RESULTS_FILE = "experiment2_cmab_round_results.json"
SUMMARY_FILE = "experiment2_cmab_summary.json"

PLOT_COVERAGE = "experiment2_cmab_coverage_rate.png"
PLOT_COMPLETION = "experiment2_cmab_completion_rate.png"
PLOT_AVG_QUALITY = "experiment2_cmab_avg_quality.png"
PLOT_CUM_COVERAGE = "experiment2_cmab_cumulative_coverage_rate.png"
PLOT_CUM_COMPLETION = "experiment2_cmab_cumulative_completion_rate.png"
PLOT_CUM_QUALITY = "experiment2_cmab_cumulative_avg_quality.png"

TOTAL_SLOTS = 86400 // 600
PER_ROUND_BUDGET = 1000
K = 7
RANDOM_SEED = 15

# 完成判定质量阈值（用于评价，不参与招募评分）
DELTA = 0.45
DEFAULT_INIT_UCB = 1.0

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
    从 worker_options 中汇总所有任务，按 slot 分组。
    """
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
    """
    第4步 baseline：
    平台不区分 trusted / unknown / malicious。
    所有工人作为普通候选工人参与论文版 CMAB 招募。
    """
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
            "init_category": worker["init_category"],   # 真实标签，仅用于离线统计
            "base_quality": float(worker["base_quality"]),
            "available_slots": set(worker.get("available_slots", [])),
            "task_map": task_map,
            "tasks_by_slot": tasks_by_slot,
            "n_obs": 0,
            "avg_quality": 0.0,
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
        if slot_id in worker["available_slots"]
    ]


def get_tasks_for_slot(tasks_by_slot, slot_id):
    return tasks_by_slot.get(slot_id, [])


def compute_ucb(worker, total_observations):
    """
    论文风格的工人级 UCB 质量估计：
        q_hat_i(t) = avg_quality_i + sqrt((K+1)*ln(T_learn)/n_i)

    若工人还未被观察，则使用统一乐观初值。
    """
    if worker["n_obs"] <= 0:
        return DEFAULT_INIT_UCB

    total_learned_counts = max(2, total_observations)
    explore = math.sqrt(
        (K + 1) * math.log(total_learned_counts) / worker["n_obs"]
    )
    return min(1.0, float(worker["avg_quality"]) + explore)


def compute_worker_marginal_gain(worker, slot_id, round_task_ids, current_best_quality, total_observations):
    """
    论文风格边际增益：

        Delta_i(t) = sum_j w_j * max(0, q_hat_i(t) - Q_j^cur(t))

    解释：
    - q_hat_i(t) 是平台当前对工人 i 的工人级质量估计
    - Q_j^cur(t) 是当前轮任务 j 已被已选工人带来的最好估计质量
    - 只要该工人对某任务能带来更高估计质量，就产生边际收益
    """
    bid_task_ids = [
        task_id
        for task_id in worker["tasks_by_slot"].get(slot_id, [])
        if task_id in round_task_ids
    ]
    if not bid_task_ids:
        return None

    q_hat = compute_ucb(worker, total_observations)
    marginal_gain = 0.0
    marginal_details = []

    for task_id in bid_task_ids:
        task = worker["task_map"][task_id]
        weight = float(task["weight"])
        prev_best = float(current_best_quality.get(task_id, 0.0))

        delta_quality = max(0.0, q_hat - prev_best)
        weighted_gain = weight * delta_quality

        if weighted_gain > 0:
            marginal_gain += weighted_gain
            marginal_details.append({
                "task_id": task_id,
                "weight": weight,
                "prev_best_quality": round(prev_best, 4),
                "estimated_quality": round(q_hat, 4),
                "delta_quality": round(delta_quality, 4),
                "weighted_gain": round(weighted_gain, 4),
            })

    cost = float(worker["bid_price"])
    score = (marginal_gain / cost) if (marginal_gain > 0 and cost > 0) else 0.0

    return {
        "worker_id": worker["worker_id"],
        "bid_price": round(cost, 4),
        "q_hat": round(q_hat, 4),
        "bid_task_ids": bid_task_ids,
        "marginal_task_count": len(marginal_details),
        "marginal_gain": round(marginal_gain, 4),
        "score": round(score, 6),
        "marginal_details": marginal_details,
    }


def greedy_select_workers(available_workers, slot_id, round_tasks, total_observations, budget):
    """
    论文风格贪心选择：
    每一步都选取“边际增益 / 报价”最大的工人。
    """
    round_task_ids = {task["task_id"] for task in round_tasks}
    remaining_workers = {worker["worker_id"]: worker for worker in available_workers}

    # 当前轮任务的“当前最好估计质量”
    current_best_quality = {task_id: 0.0 for task_id in round_task_ids}

    selected_ids = []
    selection_details = []
    total_cost = 0.0

    while remaining_workers and len(selected_ids) < K:
        remaining_budget = budget - total_cost
        candidates = []

        for worker in remaining_workers.values():
            if float(worker["bid_price"]) > remaining_budget:
                continue

            candidate = compute_worker_marginal_gain(
                worker=worker,
                slot_id=slot_id,
                round_task_ids=round_task_ids,
                current_best_quality=current_best_quality,
                total_observations=total_observations,
            )
            if candidate is None or candidate["marginal_gain"] <= 0:
                continue
            candidates.append(candidate)

        if not candidates:
            break

        candidates.sort(
            key=lambda item: (
                -item["score"],
                -item["marginal_gain"],
                -item["marginal_task_count"],
                item["bid_price"],
                item["worker_id"],
            )
        )
        best = candidates[0]

        selected_ids.append(best["worker_id"])
        total_cost += best["bid_price"]

        # 更新当前轮任务的最好估计质量状态
        for task_id in best["bid_task_ids"]:
            current_best_quality[task_id] = max(
                current_best_quality.get(task_id, 0.0),
                float(best["q_hat"]),
            )

        best["selection_order"] = len(selected_ids)
        best["remaining_budget_after_selection"] = round(budget - total_cost, 4)
        selection_details.append(best)
        remaining_workers.pop(best["worker_id"], None)

    return selected_ids, round(total_cost, 4), selection_details, current_best_quality


def evaluate_round(selected_worker_ids, workers, round_tasks, slot_id, delta):
    """
    实际执行阶段使用 Step 3 生成的 task-specific 质量 q_ij。

    指标口径：
    1. coverage_rate:
       至少有 1 个工人执行该任务

    2. completion_rate:
       工人数达到 required_workers，且平均质量 >= delta

    3. weighted_completion_quality:
       用 max q_ij 计算加权完成质量收益
    """
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

        # 完成判定：人数达到要求 + 平均质量达标
        completed = (num_workers >= required_workers) and (avg_quality >= delta)

        weighted_gain = weight * best_quality
        weighted_completion_quality += weighted_gain

        task_result = {
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
        }
        task_results.append(task_result)

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


def update_worker_statistics(selected_worker_ids, workers, slot_id):
    """
    用本轮被选工人的真实任务质量更新历史统计，
    供下一轮 UCB 学习使用。
    """
    total_new_observations = 0

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        task_ids = worker["tasks_by_slot"].get(slot_id, [])
        qualities = []

        for task_id in task_ids:
            if task_id in worker["task_map"]:
                qualities.append(float(worker["task_map"][task_id]["quality"]))

        if not qualities:
            continue

        old_n = worker["n_obs"]
        old_avg = worker["avg_quality"]

        new_obs = len(qualities)
        new_total_quality = old_n * old_avg + sum(qualities)
        new_n = old_n + new_obs
        new_avg = new_total_quality / new_n

        worker["n_obs"] = new_n
        worker["avg_quality"] = float(new_avg)
        total_new_observations += new_obs

    return total_new_observations


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


def compute_cumulative_summary(round_results):
    cumulative_state = {
        "num_tasks": 0,
        "num_covered": 0,
        "num_completed": 0,
        "task_weight_sum": 0.0,
        "weighted_completion_quality_sum": 0.0,
        "quality_sum": 0.0,
        "quality_count": 0,
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
    }


def summarize_results(round_results, initial_stats=None):
    valid_rounds = [r for r in round_results if r["num_tasks"] > 0]

    def safe_mean(key, data):
        if not data:
            return 0.0
        return round(float(np.mean([r[key] for r in data])), 4)

    cumulative_all = compute_cumulative_summary(valid_rounds)

    summary = {
        "selection_logic": "paper_style_cmab_marginal_gain_over_bid_price",
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
        "final_cumulative_coverage_rate_all_non_empty": cumulative_all["cumulative_coverage_rate"],
        "final_cumulative_completion_rate_all_non_empty": cumulative_all["cumulative_completion_rate"],
        "final_cumulative_avg_quality_all_non_empty": cumulative_all["cumulative_avg_quality"],
        "final_cumulative_normalized_completion_quality_all_non_empty": (
            cumulative_all["cumulative_normalized_completion_quality"]
        ),
    }
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
    total_observations = 0
    cumulative_state = {
        "num_tasks": 0,
        "num_covered": 0,
        "num_completed": 0,
        "task_weight_sum": 0.0,
        "weighted_completion_quality_sum": 0.0,
        "quality_sum": 0.0,
        "quality_count": 0,
    }

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)
        selected_worker_ids, cost_t, selection_details, est_quality_state = greedy_select_workers(
            available_workers=available_workers,
            slot_id=slot_id,
            round_tasks=round_tasks,
            total_observations=total_observations,
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

        round_result = {
            "round_id": round_id,
            "slot_id": slot_id,
            "selection_mode": "paper_style_cmab_marginal_gain_over_bid_price",
            "num_available_workers": len(available_workers),
            "num_selected_workers": len(selected_worker_ids),
            "selected_workers": selected_worker_ids,
            "selection_details": selection_details,
            "estimated_best_quality_state": {
                task_id: round(value, 4) for task_id, value in est_quality_state.items()
            },
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
            "total_observations_before_round": total_observations,
        }

        update_cumulative_metrics(round_result, cumulative_state)
        round_results.append(round_result)
        total_observations += update_worker_statistics(selected_worker_ids, workers, slot_id)

        print(
            f"[Round {round_id:03d}] "
            f"tasks={round_result['num_tasks']} | "
            f"selected={round_result['num_selected_workers']} | "
            f"coverage={round_result['coverage_rate']:.4f} | "
            f"completion={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"cum_coverage={round_result['cumulative_coverage_rate']:.4f} | "
            f"cum_completion={round_result['cumulative_completion_rate']:.4f} | "
            f"cum_quality={round_result['cumulative_avg_quality']:.4f} | "
            f"cost={round_result['cost']:.2f}"
        )

    summary = summarize_results(round_results, initial_stats)

    save_json(round_results, ROUND_RESULTS_FILE)
    save_json(summary, SUMMARY_FILE)

    plot_metric(round_results, "coverage_rate", "Coverage Rate", PLOT_COVERAGE)
    plot_metric(round_results, "completion_rate", "Completion Rate", PLOT_COMPLETION)
    plot_metric(round_results, "avg_quality", "Average Realized Quality", PLOT_AVG_QUALITY)
    plot_metric(round_results, "cumulative_coverage_rate", "Cumulative Coverage Rate", PLOT_CUM_COVERAGE)
    plot_metric(round_results, "cumulative_completion_rate", "Cumulative Completion Rate", PLOT_CUM_COMPLETION)
    plot_metric(round_results, "cumulative_avg_quality", "Cumulative Average Quality", PLOT_CUM_QUALITY)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
