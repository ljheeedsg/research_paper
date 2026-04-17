import json
import math
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"

ROUND_RESULTS_FILE = "experiment2_cmab_trust_round_results.json"
SUMMARY_FILE = "experiment2_cmab_trust_summary.json"

PLOT_COMPLETION = "experiment2_cmab_trust_completion_rate.png"
PLOT_QUALITY = "experiment2_cmab_trust_avg_quality.png"
PLOT_REWARD = "experiment2_cmab_trust_reward.png"
PLOT_EFFICIENCY = "experiment2_cmab_trust_efficiency.png"
PLOT_TRUST = "experiment2_cmab_trust_avg_trust.png"

TOTAL_SLOTS = 86400 // 600

PER_ROUND_BUDGET = 50.0
DELTA = 0.6
ALPHA = 1.0

# Trust parameters
VALIDATION_TOP_M = 7
TRUST_INIT_TRUSTED = 1.0
TRUST_INIT_UNKNOWN = 0.5
ETA = 0.6
THETA_HIGH = 0.8
THETA_LOW = 0.2

SKIP_EMPTY_ROUNDS = True
# =======================================================


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
    构建工人画像，并初始化 trust/category/UCB统计量。
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

        init_category = worker["init_category"]
        if init_category == "trusted":
            trust = TRUST_INIT_TRUSTED
            category = "trusted"
        else:
            trust = TRUST_INIT_UNKNOWN
            category = "unknown"

        workers[worker_id] = {
            "worker_id": worker_id,
            "cost": float(worker["cost"]),
            "init_category": init_category,
            "base_quality": float(worker["base_quality"]),
            "stability": float(worker.get("stability", 1.0)),
            "available_slots": set(worker.get("available_slots", [])),
            "task_map": task_map,
            "tasks_by_slot": tasks_by_slot,

            # trust state
            "trust": trust,
            "category": category,

            # CMAB stats
            "n_obs": 0,
            "avg_quality": 0.0,
        }

    return workers


def rebuild_sets(workers):
    Uc, Uu, Um = set(), set(), set()
    for worker_id, worker in workers.items():
        if worker["category"] == "trusted":
            Uc.add(worker_id)
        elif worker["category"] == "unknown":
            Uu.add(worker_id)
        else:
            Um.add(worker_id)
    return Uc, Uu, Um


def get_available_workers(workers, slot_id):
    return [
        worker for worker in workers.values()
        if slot_id in worker["available_slots"]
    ]


def get_tasks_for_slot(tasks_by_slot, slot_id):
    return tasks_by_slot.get(slot_id, [])


def compute_ucb(avg_quality, n_obs, round_id, alpha=ALPHA):
    return avg_quality + math.sqrt(alpha * math.log(max(2, round_id)) / (n_obs + 1))


def compute_worker_score(worker, slot_id, round_id):
    """
    score = gain / cost
    gain = sum(weight * q_hat)
    这里先不把 trust 乘进去，保持与 Step4 接近；
    trust 主要用于“允许/禁止招募”。
    """
    candidate_task_ids = worker["tasks_by_slot"].get(slot_id, [])
    if not candidate_task_ids:
        return 0.0, []

    q_hat = compute_ucb(worker["avg_quality"], worker["n_obs"], round_id, ALPHA)

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


def initialization_select_workers(available_workers, slot_id, budget):
    """
    初始化轮：
    只从 trusted + unknown 中选，malicious 初始不存在。
    为避免免费全选，仍受预算限制。
    """
    candidates = []
    for worker in available_workers:
        if worker["category"] == "malicious":
            continue
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


def greedy_select_workers(available_workers, slot_id, round_id, budget):
    """
    正常轮：
    候选 = trusted ∪ unknown，排除 malicious
    """
    worker_scores = []

    for worker in available_workers:
        if worker["category"] == "malicious":
            continue

        score, selected_tasks = compute_worker_score(worker, slot_id, round_id)
        worker_scores.append({
            "worker_id": worker["worker_id"],
            "score": score,
            "cost": worker["cost"],
            "task_ids": selected_tasks,
            "category": worker["category"],
            "trust": round(worker["trust"], 4),
        })

    worker_scores.sort(key=lambda x: (-x["score"], x["cost"], x["worker_id"]))

    selected_ids = []
    total_cost = 0.0

    for item in worker_scores:
        if not item["task_ids"]:
            continue
        if total_cost + item["cost"] > budget:
            continue
        selected_ids.append(item["worker_id"])
        total_cost += item["cost"]

    return selected_ids, round(total_cost, 4), worker_scores


def evaluate_business_tasks(selected_worker_ids, workers, round_tasks, slot_id, delta):
    """
    评估业务任务完成情况。
    完成条件：
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
        "task_execution": task_execution,
    }


def select_validation_tasks(selected_worker_ids, workers, round_tasks, slot_id, top_m):
    """
    从当前轮业务任务中选验证任务：
      条件：该任务被 selected trusted 和 selected unknown 同时覆盖
      排序：按 unknown 工人数降序
    """
    candidate_list = []

    for task in round_tasks:
        task_id = task["task_id"]
        trusted_workers = []
        unknown_workers = []

        for worker_id in selected_worker_ids:
            worker = workers[worker_id]
            if task_id not in worker["tasks_by_slot"].get(slot_id, []):
                continue

            if worker["category"] == "trusted":
                trusted_workers.append(worker_id)
            elif worker["category"] == "unknown":
                unknown_workers.append(worker_id)

        if len(trusted_workers) > 0 and len(unknown_workers) > 0:
            candidate_list.append({
                "task_id": task_id,
                "trusted_workers": trusted_workers,
                "unknown_workers": unknown_workers,
                "unknown_count": len(unknown_workers),
            })

    candidate_list.sort(
        key=lambda x: (-x["unknown_count"], x["task_id"])
    )

    return candidate_list[:top_m], candidate_list


def update_trust_by_validation(validation_tasks, workers, slot_id):
    """
    用 trusted 的 task_data 中位数作为基准，更新 unknown 的 trust。
    """
    trust_update_records = []

    for item in validation_tasks:
        task_id = item["task_id"]
        trusted_workers = item["trusted_workers"]
        unknown_workers = item["unknown_workers"]

        trusted_data = []
        for worker_id in trusted_workers:
            worker = workers[worker_id]
            if task_id in worker["task_map"]:
                trusted_data.append(float(worker["task_map"][task_id]["task_data"]))

        if not trusted_data:
            continue

        base_v = float(np.median(trusted_data))

        for worker_id in unknown_workers:
            worker = workers[worker_id]
            if task_id not in worker["task_map"]:
                continue

            data_i = float(worker["task_map"][task_id]["task_data"])

            if abs(base_v) < 1e-12:
                error = abs(data_i - base_v)
            else:
                error = abs(data_i - base_v) / abs(base_v)

            old_trust = worker["trust"]
            new_trust = old_trust + ETA * (1 - 2 * error)
            new_trust = max(0.0, min(1.0, new_trust))
            worker["trust"] = new_trust

            old_category = worker["category"]
            if new_trust >= THETA_HIGH:
                worker["category"] = "trusted"
            elif new_trust <= THETA_LOW:
                worker["category"] = "malicious"
            else:
                worker["category"] = "unknown"

            trust_update_records.append({
                "task_id": task_id,
                "worker_id": worker_id,
                "base_value": round(base_v, 4),
                "worker_data": round(data_i, 4),
                "error": round(float(error), 4),
                "old_trust": round(old_trust, 4),
                "new_trust": round(new_trust, 4),
                "old_category": old_category,
                "new_category": worker["category"],
            })

    return trust_update_records


def update_worker_quality_statistics(selected_worker_ids, workers, slot_id):
    """
    按本轮实际执行任务的 quality 更新 CMAB 统计量。
    """
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


def summarize_results(round_results):
    valid_rounds = [r for r in round_results if r["num_tasks"] > 0]
    valid_non_init_rounds = [r for r in valid_rounds if not r["is_initialization"]]

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
        "avg_avg_trust_all_non_empty": safe_mean("avg_trust", valid_rounds),

        "avg_completion_rate_non_init": safe_mean("completion_rate", valid_non_init_rounds),
        "avg_avg_quality_non_init": safe_mean("avg_quality", valid_non_init_rounds),
        "avg_reward_non_init": safe_mean("reward", valid_non_init_rounds),
        "avg_cost_non_init": safe_mean("cost", valid_non_init_rounds),
        "avg_efficiency_non_init": safe_mean("efficiency", valid_non_init_rounds),
        "avg_avg_trust_non_init": safe_mean("avg_trust", valid_non_init_rounds),
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

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)
        is_initialization = (len(round_results) == 0)

        if is_initialization:
            selected_worker_ids, cost_t, selection_details = initialization_select_workers(
                available_workers, slot_id, PER_ROUND_BUDGET
            )
        else:
            selected_worker_ids, cost_t, selection_details = greedy_select_workers(
                available_workers, slot_id, round_id, PER_ROUND_BUDGET
            )

        # 先评估业务任务
        business_eval = evaluate_business_tasks(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            slot_id=slot_id,
            delta=DELTA,
        )

        # 生成验证任务
        validation_tasks, validation_candidates = select_validation_tasks(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            slot_id=slot_id,
            top_m=VALIDATION_TOP_M,
        )

        # trust 更新
        trust_update_records = update_trust_by_validation(
            validation_tasks=validation_tasks,
            workers=workers,
            slot_id=slot_id,
        )

        # 更新 Uc / Uu / Um
        Uc, Uu, Um = rebuild_sets(workers)

        # 更新 CMAB 质量统计
        update_worker_quality_statistics(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            slot_id=slot_id,
        )

        reward_t = business_eval["reward"]
        efficiency_t = (reward_t / cost_t) if cost_t > 0 else 0.0

        if selected_worker_ids:
            avg_trust_t = float(np.mean([workers[w]["trust"] for w in selected_worker_ids]))
        else:
            avg_trust_t = 0.0

        round_result = {
            "round_id": round_id,
            "slot_id": slot_id,
            "is_initialization": is_initialization,

            "num_available_workers": len(available_workers),
            "num_selected_workers": len(selected_worker_ids),
            "selected_workers": selected_worker_ids,

            "num_tasks": business_eval["num_tasks"],
            "num_completed": business_eval["num_completed"],
            "completion_rate": business_eval["completion_rate"],
            "avg_quality": business_eval["avg_quality"],
            "reward": round(reward_t, 4),
            "cost": round(cost_t, 4),
            "efficiency": round(efficiency_t, 4),

            "avg_trust": round(avg_trust_t, 4),
            "num_validation_tasks": len(validation_tasks),

            "trusted_count": len(Uc),
            "unknown_count": len(Uu),
            "malicious_count": len(Um),

            "completed_tasks": business_eval["completed_tasks"],
            "failed_tasks": business_eval["failed_tasks"],
            "task_results": business_eval["task_results"],

            "validation_tasks": validation_tasks,
            "trust_updates": trust_update_records,
        }

        round_results.append(round_result)

        print(
            f"[Round {round_id:03d}] "
            f"init={is_initialization} | "
            f"tasks={round_result['num_tasks']} | "
            f"completed={round_result['num_completed']} | "
            f"completion_rate={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"reward={round_result['reward']:.2f} | "
            f"cost={round_result['cost']:.2f} | "
            f"eff={round_result['efficiency']:.4f} | "
            f"avg_trust={round_result['avg_trust']:.4f} | "
            f"Uc={round_result['trusted_count']} | "
            f"Uu={round_result['unknown_count']} | "
            f"Um={round_result['malicious_count']}"
        )

    summary = summarize_results(round_results)

    save_json(round_results, ROUND_RESULTS_FILE)
    save_json(summary, SUMMARY_FILE)

    plot_metric(round_results, "completion_rate", "Completion Rate", PLOT_COMPLETION)
    plot_metric(round_results, "avg_quality", "Average Quality", PLOT_QUALITY)
    plot_metric(round_results, "reward", "Reward", PLOT_REWARD)
    plot_metric(round_results, "efficiency", "Efficiency", PLOT_EFFICIENCY)
    plot_metric(round_results, "avg_trust", "Average Trust", PLOT_TRUST)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()