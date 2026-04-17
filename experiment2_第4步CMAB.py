import json
import math
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"
TASK_FILE = "experiment2_tasks.csv"   # 这里只用来保证轮次任务集合完整
ROUND_RESULTS_FILE = "experiment2_cmab_round_results.json"
SUMMARY_FILE = "experiment2_cmab_summary.json"

PLOT_COMPLETION = "experiment2_cmab_completion_rate.png"
PLOT_QUALITY = "experiment2_cmab_avg_quality.png"
PLOT_REWARD = "experiment2_cmab_reward.png"
PLOT_EFFICIENCY = "experiment2_cmab_efficiency.png"

SLOT_SEC = 600
TOTAL_SLOTS = 86400 // SLOT_SEC

# 预算设置：建议先用“每轮预算”
PER_ROUND_BUDGET = 1000

# 质量阈值：任务完成必须满足平均质量 >= DELTA
DELTA = 0.6

# UCB 参数
ALPHA = 1.0

# 是否跳过无任务轮次
SKIP_EMPTY_ROUNDS = True
# =======================================================


def load_worker_options():
    with open(WORKER_OPTIONS_FILE, "r", encoding="utf-8") as f:
        worker_options = json.load(f)
    print(f"已加载工人可选项: {len(worker_options)} 个工人")
    return worker_options


def load_all_tasks_from_workers(worker_options):
    """
    从 worker_options 里收集所有任务。
    这样不依赖 csv 里的字段是否完全一致。
    """
    task_dict = {}

    for worker_key, worker in worker_options.items():
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
    """
    为 CMAB 构建工人画像。
    """
    workers = {}

    for worker_key, worker in worker_options.items():
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
            # CMAB 统计量
            "n_obs": 0,             # 被观测到的任务次数
            "avg_quality": 0.0,     # 历史平均质量
        }

    return workers


def get_available_workers(workers, slot_id):
    return [
        worker for worker in workers.values()
        if slot_id in worker["available_slots"]
    ]


def get_tasks_for_slot(tasks_by_slot, slot_id):
    return tasks_by_slot.get(slot_id, [])


def get_worker_observed_quality(worker, task_ids):
    """
    返回该工人在本轮实际执行任务上的质量列表。
    """
    qualities = []
    for task_id in task_ids:
        if task_id in worker["task_map"]:
            qualities.append(float(worker["task_map"][task_id]["quality"]))
    return qualities


def compute_ucb(avg_quality, n_obs, total_observations, alpha=ALPHA):
    """
    UCB:
    q_hat = avg_quality + sqrt(alpha * ln(N) / (n_obs + 1))

    其中 N 表示截至当前轮之前的累计学习总次数，而不是轮次 t。
    """
    return avg_quality + math.sqrt(alpha * math.log(max(2, total_observations)) / (n_obs + 1))


def compute_worker_score(worker, slot_id, total_observations):
    """
    score_i(t) = gain_i(t) / c_i
    gain_i(t) = sum_{j in S_i(t)} w_j * q_hat_i(t)
    """
    candidate_task_ids = worker["tasks_by_slot"].get(slot_id, [])
    if not candidate_task_ids:
        return 0.0, []

    q_hat = compute_ucb(worker["avg_quality"], worker["n_obs"], total_observations, ALPHA)

    gain = 0.0
    selected_tasks = []
    for task_id in candidate_task_ids:
        task = worker["task_map"][task_id]
        gain += float(task["weight"]) * q_hat
        selected_tasks.append(task_id)

    cost = worker["cost"]
    if cost <= 0:
        return 0.0, selected_tasks

    score = gain / cost
    return score, selected_tasks


def greedy_select_workers(available_workers, slot_id, total_observations, budget):
    """
    正常 CMAB 轮的贪心选择：
    按 score 从高到低排序，依次选工人直到预算耗尽。
    """
    worker_scores = []

    for worker in available_workers:
        score, selected_tasks = compute_worker_score(worker, slot_id, total_observations)
        worker_scores.append({
            "worker_id": worker["worker_id"],
            "score": score,
            "cost": worker["cost"],
            "task_ids": selected_tasks,
        })

    worker_scores.sort(key=lambda x: (-x["score"], x["cost"], x["worker_id"]))

    selected_ids = []
    total_cost = 0.0

    for item in worker_scores:
        cost = item["cost"]
        if total_cost + cost > budget:
            continue
        if not item["task_ids"]:
            continue

        selected_ids.append(item["worker_id"])
        total_cost += cost

    return selected_ids, round(total_cost, 4), worker_scores


def initialization_select_workers(available_workers, slot_id, budget):
    """
    初始化轮：
    选取所有可用且本轮有任务可做的工人，
    若预算不够，则按 cost 从小到大依次加入。
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

    candidates.sort(key=lambda x: (x["cost"], x["worker_id"]))

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
    评估本轮任务完成情况。
    完成条件：
        1. 参与工人数 >= required_workers
        2. 平均质量 >= delta
    """
    task_execution = defaultdict(list)
    task_quality_values = defaultdict(list)

    # 统计每个任务由哪些被选工人执行、质量是多少
    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        for task_id in worker["tasks_by_slot"].get(slot_id, []):
            if task_id in worker["task_map"]:
                q_ij = float(worker["task_map"][task_id]["quality"])
                task_execution[task_id].append(worker_id)
                task_quality_values[task_id].append(q_ij)

    completed_tasks = []
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

        completed = (num_workers >= required_workers) and (avg_quality >= delta)

        task_result = {
            "task_id": task_id,
            "slot_id": slot_id,
            "required_workers": required_workers,
            "weight": weight,
            "num_workers": num_workers,
            "avg_quality": round(avg_quality, 4),
            "executed_by": worker_ids,
            "completed": completed,
        }
        task_results.append(task_result)

        if completed:
            completed_tasks.append(task_id)
            reward_t += weight
        else:
            failed_tasks.append(task_id)

    num_tasks = len(round_tasks)
    num_completed = len(completed_tasks)
    completion_rate = (num_completed / num_tasks) if num_tasks > 0 else 0.0

    completed_qualities = [
        tr["avg_quality"] for tr in task_results if tr["completed"]
    ]
    avg_quality_t = float(np.mean(completed_qualities)) if completed_qualities else 0.0

    return {
        "num_tasks": num_tasks,
        "num_completed": num_completed,
        "completion_rate": round(completion_rate, 4),
        "avg_quality": round(avg_quality_t, 4),
        "reward": round(reward_t, 4),
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "task_results": task_results,
    }


def update_worker_statistics(selected_worker_ids, workers, slot_id):
    """
    根据本轮实际执行任务的质量，更新每个工人的 n_obs 和 avg_quality，
    并返回本轮新增的学习次数。
    """
    total_new_observations = 0

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        task_ids = worker["tasks_by_slot"].get(slot_id, [])
        qualities = get_worker_observed_quality(worker, task_ids)

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


def summarize_results(round_results):
    valid_rounds = [r for r in round_results if r["num_tasks"] > 0]
    valid_non_init_rounds = [
        r for r in valid_rounds if not r["is_initialization"]
    ]

    def safe_mean(key, data):
        if not data:
            return 0.0
        return round(float(np.mean([r[key] for r in data])), 4)

    summary = {
        "total_rounds_recorded": len(round_results),
        "total_non_empty_rounds": len(valid_rounds),
        "total_non_empty_non_init_rounds": len(valid_non_init_rounds),

        "avg_completion_rate_all_non_empty": safe_mean("completion_rate", valid_rounds),
        "avg_avg_quality_all_non_empty": safe_mean("avg_quality", valid_rounds),
        "avg_reward_all_non_empty": safe_mean("reward", valid_rounds),
        "avg_cost_all_non_empty": safe_mean("cost", valid_rounds),
        "avg_efficiency_all_non_empty": safe_mean("efficiency", valid_rounds),

        "avg_completion_rate_non_init": safe_mean("completion_rate", valid_non_init_rounds),
        "avg_avg_quality_non_init": safe_mean("avg_quality", valid_non_init_rounds),
        "avg_reward_non_init": safe_mean("reward", valid_non_init_rounds),
        "avg_cost_non_init": safe_mean("cost", valid_non_init_rounds),
        "avg_efficiency_non_init": safe_mean("efficiency", valid_non_init_rounds),
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
    for r in valid:
        if r["is_initialization"]:
            plt.axvline(r["round_id"], linestyle="--", alpha=0.5)
            break

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
    total_observations = 0

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)

        # 初始化轮：第一 个“有任务的轮次”
        is_initialization = (len(round_results) == 0)

        if is_initialization:
            selected_worker_ids, cost_t, selection_details = initialization_select_workers(
                available_workers, slot_id, PER_ROUND_BUDGET
            )
        else:
            selected_worker_ids, cost_t, selection_details = greedy_select_workers(
                available_workers, slot_id, total_observations, PER_ROUND_BUDGET
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
            "is_initialization": is_initialization,

            "num_available_workers": len(available_workers),
            "num_selected_workers": len(selected_worker_ids),
            "selected_workers": selected_worker_ids,

            "num_tasks": eval_result["num_tasks"],
            "num_completed": eval_result["num_completed"],
            "completion_rate": eval_result["completion_rate"],
            "avg_quality": eval_result["avg_quality"],
            "reward": round(reward_t, 4),
            "cost": round(cost_t, 4),
            "efficiency": round(efficiency_t, 4),

            "completed_tasks": eval_result["completed_tasks"],
            "failed_tasks": eval_result["failed_tasks"],
            "task_results": eval_result["task_results"],
            "total_observations_before_round": total_observations,
        }

        round_results.append(round_result)

        # 更新工人统计量
        total_observations += update_worker_statistics(selected_worker_ids, workers, slot_id)

        print(
            f"[Round {round_id:03d}] "
            f"init={is_initialization} | "
            f"tasks={round_result['num_tasks']} | "
            f"completed={round_result['num_completed']} | "
            f"completion_rate={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"reward={round_result['reward']:.2f} | "
            f"cost={round_result['cost']:.2f} | "
            f"eff={round_result['efficiency']:.4f}"
        )

    summary = summarize_results(round_results)

    save_json(round_results, ROUND_RESULTS_FILE)
    save_json(summary, SUMMARY_FILE)

    plot_metric(round_results, "completion_rate", "Completion Rate", PLOT_COMPLETION)
    plot_metric(round_results, "avg_quality", "Average Quality", PLOT_QUALITY)
    plot_metric(round_results, "reward", "Reward", PLOT_REWARD)
    plot_metric(round_results, "efficiency", "Efficiency", PLOT_EFFICIENCY)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
