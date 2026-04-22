import json
import math
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"

ROUND_RESULTS_FILE = "experiment2_cmab_trust_round_results.json"
SUMMARY_FILE = "experiment2_cmab_trust_summary.json"

PLOT_COVERAGE = "experiment2_cmab_trust_coverage_rate.png"
PLOT_COMPLETION = "experiment2_cmab_trust_completion_rate.png"
PLOT_AVG_QUALITY = "experiment2_cmab_trust_avg_quality.png"
PLOT_CUM_COVERAGE = "experiment2_cmab_trust_cumulative_coverage_rate.png"
PLOT_CUM_COMPLETION = "experiment2_cmab_trust_cumulative_completion_rate.png"
PLOT_CUM_QUALITY = "experiment2_cmab_trust_cumulative_avg_quality.png"
PLOT_TRUSTED = "experiment2_cmab_trust_trusted_count.png"
PLOT_UNKNOWN = "experiment2_cmab_trust_unknown_count.png"
PLOT_MALICIOUS = "experiment2_cmab_trust_malicious_count.png"
PLOT_VALIDATION = "experiment2_cmab_trust_validation_count.png"
PLOT_PLATFORM_UTILITY = "experiment2_cmab_trust_platform_utility.png"
PLOT_CUM_PLATFORM_UTILITY = "experiment2_cmab_trust_cumulative_platform_utility.png"
PLOT_ACTIVE_WORKERS = "experiment2_cmab_trust_active_workers.png"
PLOT_LEFT_WORKERS = "experiment2_cmab_trust_left_workers.png"
PLOT_LEAVE_PROB = "experiment2_cmab_trust_avg_leave_probability.png"

TOTAL_SLOTS = 86400 // 600
PER_ROUND_BUDGET = 1000
K = 20
RANDOM_SEED = 3
NUM_EXPERIMENT_RUNS = 10
SEED_STEP = 1

# 完成判定质量阈值（只用于评价）
DELTA = 0.45
DEFAULT_INIT_UCB = 1.0

# ===== Platform Utility =====
# 将“任务权重 × 完成质量”货币化
RHO = 10.0

# ===== Worker Cost =====
# 工人真实执行成本 = WORKER_COST_RATIO × 工人报酬
WORKER_COST_RATIO = 0.6

# ===== Leave Model =====
# 退出概率：
# sigmoid(BETA0 + BETA1 * cumulative_cost - BETA2 * avg_reward_per_selected_round)
BETA0 = -2.5
BETA1 = 0.02
BETA2 = 0.3

# 验证任务参数
VALIDATION_TOP_M = 7

# 平台初始认知：只知道 trusted，其余都先当 unknown
TRUST_INIT_TRUSTED = 1.0
TRUST_INIT_UNKNOWN = 0.5

# trust 更新参数
ETA = 6
THETA_HIGH = 0.8
THETA_LOW = 0.20
TRUST_EPS = 1e-9

# 分段误差阈值
ERROR_GOOD = 0.15
ERROR_BAD = 0.35

SKIP_EMPTY_ROUNDS = True
# =======================================================


random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)


def set_random_seed(seed):
    random.seed(seed)
    np.random.seed(seed)


def is_numeric_value(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def average_numeric_values(values):
    if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return int(round(float(np.mean(values))))
    return round(float(np.mean(values)), 4)


def average_dict_records(records):
    averaged = {}
    for key, first_value in records[0].items():
        values = [record.get(key) for record in records]
        if all(is_numeric_value(value) for value in values):
            averaged[key] = average_numeric_values(values)
        else:
            averaged[key] = first_value
    return averaged


def aggregate_round_results(all_round_results):
    if not all_round_results:
        return []

    expected_len = len(all_round_results[0])
    for run_results in all_round_results:
        if len(run_results) != expected_len:
            raise ValueError("不同随机种子的轮次结果长度不一致，无法直接取平均。")

    aggregated = []
    for idx in range(expected_len):
        records = [run_results[idx] for run_results in all_round_results]
        aggregated.append(average_dict_records(records))
    return aggregated


def sigmoid(x: float) -> float:
    x = max(-20.0, min(20.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def load_worker_options():
    with open(WORKER_OPTIONS_FILE, "r", encoding="utf-8") as f:
        worker_options = json.load(f)
    print(f"已加载工人可选项: {len(worker_options)} 个工人")
    return worker_options


def load_all_tasks_from_workers(worker_options):
    """
    从 worker_options 中汇总所有任务，按 slot 分组；
    同时建立 task_id -> region_id 映射（这里将 region 当作 grid）。
    """
    task_dict = {}
    task_grid_map = {}

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
                task_grid_map[task_id] = int(task["region_id"])

    tasks_by_slot = defaultdict(list)
    for task in task_dict.values():
        tasks_by_slot[task["slot_id"]].append(task)

    for slot_id in tasks_by_slot:
        tasks_by_slot[slot_id].sort(key=lambda x: x["task_id"])

    print(f"从 worker options 中收集到任务: {len(task_dict)} 个")
    return task_dict, tasks_by_slot, task_grid_map


def build_worker_profiles(worker_options):
    """
    第5步：
    平台初始只知道 trusted。
    真实 unknown / malicious 初始都视为 unknown。
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

        bid_price = float(worker.get("bid_price", worker["cost"]))

        workers[worker_id] = {
            "worker_id": worker_id,
            "cost": bid_price,
            "bid_price": bid_price,
            "init_category": init_category,   # 真实标签，仅分析用
            "base_quality": float(worker["base_quality"]),
            "available_slots": set(worker.get("available_slots", [])),
            "task_map": task_map,
            "tasks_by_slot": tasks_by_slot,

            # trust state
            "trust": trust,
            "category": category,

            # CMAB stats
            "n_obs": 0,
            "avg_quality": 0.0,

            # ===== long-run worker state =====
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
        if slot_id in worker["available_slots"] and worker["is_active"]
    ]


def get_tasks_for_slot(tasks_by_slot, slot_id):
    return tasks_by_slot.get(slot_id, [])


def compute_ucb(worker, total_observations):
    """
    论文风格工人级 UCB 估计。
    """
    if worker["n_obs"] <= 0:
        return DEFAULT_INIT_UCB

    total_learned_counts = max(2, total_observations)
    explore = math.sqrt((K + 1) * math.log(total_learned_counts) / worker["n_obs"])
    return min(1.0, float(worker["avg_quality"]) + explore)


def compute_worker_marginal_gain(worker, slot_id, round_task_ids, current_best_quality, total_observations):
    """
    论文风格边际增益：
        Delta_i(t) = sum_j w_j * max(0, q_hat_i(t) - Q_j^cur(t))
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
        "trust": round(float(worker["trust"]), 4),
        "category": worker["category"],
    }


def greedy_select_workers(available_workers, slot_id, round_tasks, total_observations, budget):
    """
    第5步的招募仍沿用论文风格 CMAB，
    但排除已经被识别为 malicious 的工人。
    """
    round_task_ids = {task["task_id"] for task in round_tasks}
    remaining_workers = {
        worker["worker_id"]: worker
        for worker in available_workers
        if worker["category"] != "malicious"
    }

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
    实际执行评价：
    1. coverage_rate: 至少有1个工人执行
    2. completion_rate: 人数达到 required_workers 且平均质量 >= delta
    3. weighted_completion_quality: weight * best_quality
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

        completed = (num_workers >= required_workers) and (avg_quality >= delta)

        weighted_gain = weight * best_quality
        weighted_completion_quality += weighted_gain

        platform_value = RHO * weight * best_quality

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
            "platform_value": round(platform_value, 4),
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


def compute_platform_utility(eval_result, selected_worker_ids, workers):
    """
    平台单轮收益：
        task_value_t = sum_j (RHO * weight_j * best_quality_j)
        payment_t = sum_i bid_i
        utility_t = task_value_t - payment_t
    """
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


def generate_validation_tasks_by_grid(worker_ids_for_validation, workers, task_grid_map, round_tasks, slot_id, top_m):
    """
    只在指定的验证参与者集合中生成验证任务。
    对本文件的 strict version 来说，worker_ids_for_validation 就是本轮被招募工人。

    1. 先按 task 聚合 trusted / unknown 的精确重叠
    2. 只有同一个 task 同时存在被招募 trusted 和 unknown，才可作为验证任务
    3. 选择 unknown 更多、trusted 更多的 top-M task
    """
    validation_worker_ids = set(worker_ids_for_validation)
    round_task_ids = {task["task_id"] for task in round_tasks}

    task_uc = defaultdict(int)
    task_uu = defaultdict(int)

    for worker_id in validation_worker_ids:
        worker = workers[worker_id]

        for task_id in worker["tasks_by_slot"].get(slot_id, []):
            if task_id not in round_task_ids:
                continue

            gid = task_grid_map.get(task_id)
            if gid is None:
                continue

            if worker["category"] == "trusted":
                task_uc[task_id] += 1
            elif worker["category"] == "unknown":
                task_uu[task_id] += 1

    candidate_tasks = []
    for task_id in round_task_ids:
        uc_cnt = task_uc.get(task_id, 0)
        uu_cnt = task_uu.get(task_id, 0)

        # 必须在同一个 task 上同时有被招募 trusted 和 unknown
        if uc_cnt > 0 and uu_cnt > 0:
            candidate_tasks.append({
                "task_id": task_id,
                "grid_id": task_grid_map.get(task_id),
                "trusted_count": uc_cnt,
                "unknown_count": uu_cnt,
            })

    candidate_tasks.sort(
        key=lambda x: (-x["unknown_count"], -x["trusted_count"], x["grid_id"], x["task_id"])
    )

    validation_tasks = candidate_tasks[:top_m]

    return validation_tasks, candidate_tasks


def update_trust_by_validation(validation_tasks, selected_worker_ids, workers, slot_id):
    """
    修改版（Strict Version）：
    只有本轮被招募 selected_worker_ids 的工人，
    才能参与验证任务并上传数据。
    """

    trust_update_records = []

    # ===============================
    # 修改1：参与验证的人从 available_workers
    # 改成 selected_worker_ids
    # ===============================
    selected_ids = set(selected_worker_ids)

    for item in validation_tasks:
        task_id = item["task_id"]

        trusted_workers = []
        unknown_workers = []

        # ===============================
        # 修改2：只遍历 selected_ids
        # 原来是 available_ids
        # ===============================
        for worker_id in selected_ids:
            worker = workers[worker_id]

            if task_id not in worker["tasks_by_slot"].get(slot_id, []):
                continue

            if worker["category"] == "trusted":
                trusted_workers.append(worker_id)

            elif worker["category"] == "unknown":
                unknown_workers.append(worker_id)

        # 没有trusted参考值，则跳过
        if not trusted_workers:
            continue

        # ===============================
        # trusted 提供参考值
        # ===============================
        trusted_data = []

        for worker_id in trusted_workers:
            worker = workers[worker_id]

            if task_id in worker["task_map"]:
                trusted_data.append(
                    float(worker["task_map"][task_id]["task_data"])
                )

        if not trusted_data:
            continue

        base_v = float(np.median(trusted_data))

        # ===============================
        # 更新 unknown trust
        # ===============================
        for worker_id in unknown_workers:
            worker = workers[worker_id]

            if task_id not in worker["task_map"]:
                continue

            data_i = float(worker["task_map"][task_id]["task_data"])

            if abs(base_v) < 1e-12:
                error = abs(data_i - base_v)
            else:
                error = abs(data_i - base_v) / abs(base_v)

            old_trust = float(worker["trust"])

            if error <= ERROR_GOOD:
                new_trust = old_trust + ETA

            elif error <= ERROR_BAD:
                new_trust = old_trust

            else:
                new_trust = old_trust - ETA

            new_trust = max(0.0, min(1.0, new_trust))
            worker["trust"] = new_trust

            old_category = worker["category"]

            if new_trust >= THETA_HIGH - TRUST_EPS:
                worker["category"] = "trusted"

            elif new_trust <= THETA_LOW + TRUST_EPS:
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
                "true_init_category": worker["init_category"],
            })

    return trust_update_records


def update_worker_statistics(selected_worker_ids, workers, slot_id):
    """
    用本轮被选工人的真实任务质量更新历史统计，供下一轮 UCB 使用。
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


def update_worker_reward_cost(selected_worker_ids, workers):
    """
    更新被选工人的：
    - cumulative_reward
    - cumulative_cost
    - recent_reward
    - selected_rounds
    """
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


def update_worker_leave_state(workers, round_id, selected_worker_ids):
    """
    只对本轮被选中的工人执行退出判定。
    这样更符合：参与任务 -> 产生收益/成本 -> 再决定是否离开。
    """
    left_worker_ids = []
    leave_probabilities = []
    selected_set = set(selected_worker_ids)

    for worker_id, worker in workers.items():
        if not worker["is_active"]:
            continue

        if worker_id not in selected_set:
            worker["leave_probability"] = 0.0
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


def update_active_rounds(available_workers):
    for worker in available_workers:
        worker["active_rounds"] += 1


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
        "selection_logic": "paper_style_cmab_plus_validation_longrun",
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
        "avg_validation_count_all_non_empty": safe_mean("num_validation_tasks", valid_rounds),
        "avg_trusted_count_all_non_empty": safe_mean("trusted_count", valid_rounds),
        "avg_unknown_count_all_non_empty": safe_mean("unknown_count", valid_rounds),
        "avg_malicious_count_all_non_empty": safe_mean("malicious_count", valid_rounds),
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


def run_single_experiment(seed):
    set_random_seed(seed)
    worker_options = load_worker_options()
    _, tasks_by_slot, task_grid_map = load_all_tasks_from_workers(worker_options)
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

        # Step A: 论文风格 CMAB 招募
        selected_worker_ids, cost_t, selection_details, est_quality_state = greedy_select_workers(
            available_workers=available_workers,
            slot_id=slot_id,
            round_tasks=round_tasks,
            total_observations=total_observations,
            budget=PER_ROUND_BUDGET,
        )

        # Step B: 本轮业务任务评价
        eval_result = evaluate_round(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            slot_id=slot_id,
            delta=DELTA,
        )

        # Step C: 生成验证任务（先 grid 后 task）
        validation_tasks, validation_candidates = generate_validation_tasks_by_grid(
            worker_ids_for_validation=selected_worker_ids,
            workers=workers,
            task_grid_map=task_grid_map,
            round_tasks=round_tasks,
            slot_id=slot_id,
            top_m=VALIDATION_TOP_M,
        )

        # Step D: 执行验证并更新 trust
        trust_update_records = update_trust_by_validation(
            validation_tasks=validation_tasks,
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            slot_id=slot_id,
        )

        # Step E: 更新集合统计
        reward_t = eval_result["weighted_completion_quality"]
        efficiency_t = (reward_t / cost_t) if cost_t > 0 else 0.0
        update_worker_reward_cost(selected_worker_ids, workers)
        platform_result = compute_platform_utility(eval_result, selected_worker_ids, workers)
        leave_result = update_worker_leave_state(
            workers=workers,
            round_id=round_id,
            selected_worker_ids=selected_worker_ids,
        )

        Uc, Uu, Um = rebuild_sets(workers)

        total_observations_before_round = total_observations
        total_observations += update_worker_statistics(selected_worker_ids, workers, slot_id)
        current_active_workers = sum(1 for worker in workers.values() if worker["is_active"])
        cumulative_left_workers = sum(1 for worker in workers.values() if not worker["is_active"])

        round_result = {
            "round_id": round_id,
            "slot_id": slot_id,
            "selection_mode": "paper_style_cmab_plus_validation_longrun",
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
            "platform_task_value": platform_result["platform_task_value"],
            "platform_payment": platform_result["platform_payment"],
            "platform_utility": platform_result["platform_utility"],

            "num_validation_tasks": len(validation_tasks),
            "validation_tasks": validation_tasks,
            "validation_candidates": validation_candidates,
            "trust_updates": trust_update_records,

            "trusted_count": len(Uc),
            "unknown_count": len(Uu),
            "malicious_count": len(Um),
            "num_active_workers": current_active_workers,
            "num_left_workers_this_round": leave_result["num_left_workers_this_round"],
            "left_worker_ids_this_round": leave_result["left_worker_ids"],
            "cumulative_left_workers": cumulative_left_workers,
            "avg_leave_probability": leave_result["avg_leave_probability"],

            "covered_tasks": eval_result["covered_tasks"],
            "completed_tasks": eval_result["completed_tasks"],
            "uncompleted_tasks": eval_result["uncompleted_tasks"],
            "task_results": eval_result["task_results"],
            "total_observations_before_round": total_observations_before_round,
            "total_observations_after_round": total_observations,
        }

        update_cumulative_metrics(round_result, cumulative_state)
        round_results.append(round_result)

        print(
            f"[Round {round_id:03d}] "
            f"tasks={round_result['num_tasks']} | "
            f"selected={round_result['num_selected_workers']} | "
            f"validation={round_result['num_validation_tasks']} | "
            f"coverage={round_result['coverage_rate']:.4f} | "
            f"completion={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"platform_utility={round_result['platform_utility']:.2f} | "
            f"trusted={round_result['trusted_count']} | "
            f"unknown={round_result['unknown_count']} | "
            f"malicious={round_result['malicious_count']} | "
            f"active_workers={round_result['num_active_workers']} | "
            f"left_this_round={round_result['num_left_workers_this_round']} | "
            f"cum_utility={round_result['cumulative_platform_utility']:.2f}"
        )

    summary = summarize_results(round_results, workers, initial_stats)
    return round_results, summary


def main():
    seeds = [RANDOM_SEED + i * SEED_STEP for i in range(NUM_EXPERIMENT_RUNS)]
    print(f"开始重复实验，共 {NUM_EXPERIMENT_RUNS} 次，随机种子: {seeds}")

    all_round_results = []
    all_summaries = []
    all_runs_payload = []

    for run_idx, seed in enumerate(seeds, start=1):
        print(f"\n===== Run {run_idx}/{NUM_EXPERIMENT_RUNS} | seed={seed} =====")
        round_results, summary = run_single_experiment(seed)
        all_round_results.append(round_results)
        all_summaries.append(summary)
        all_runs_payload.append(
            {
                "run_index": run_idx,
                "seed": seed,
                "summary": summary,
                "round_results": round_results,
            }
        )

    avg_round_results = aggregate_round_results(all_round_results)
    avg_summary = average_dict_records(all_summaries)
    avg_summary["num_experiment_runs"] = NUM_EXPERIMENT_RUNS
    avg_summary["experiment_seeds"] = seeds

    all_runs_file = ROUND_RESULTS_FILE.replace(".json", "_all_runs.json")
    save_json(all_runs_payload, all_runs_file)
    save_json(avg_round_results, ROUND_RESULTS_FILE)
    save_json(avg_summary, SUMMARY_FILE)

    plot_metric(avg_round_results, "coverage_rate", "Coverage Rate", PLOT_COVERAGE)
    plot_metric(avg_round_results, "completion_rate", "Completion Rate", PLOT_COMPLETION)
    plot_metric(avg_round_results, "avg_quality", "Average Realized Quality", PLOT_AVG_QUALITY)
    plot_metric(avg_round_results, "cumulative_coverage_rate", "Cumulative Coverage Rate", PLOT_CUM_COVERAGE)
    plot_metric(avg_round_results, "cumulative_completion_rate", "Cumulative Completion Rate", PLOT_CUM_COMPLETION)
    plot_metric(avg_round_results, "cumulative_avg_quality", "Cumulative Average Quality", PLOT_CUM_QUALITY)
    plot_metric(avg_round_results, "trusted_count", "Trusted Count", PLOT_TRUSTED)
    plot_metric(avg_round_results, "unknown_count", "Unknown Count", PLOT_UNKNOWN)
    plot_metric(avg_round_results, "malicious_count", "Malicious Count", PLOT_MALICIOUS)
    plot_metric(avg_round_results, "num_validation_tasks", "Validation Task Count", PLOT_VALIDATION)
    plot_metric(avg_round_results, "platform_utility", "Platform Utility", PLOT_PLATFORM_UTILITY)
    plot_metric(avg_round_results, "cumulative_platform_utility", "Cumulative Platform Utility", PLOT_CUM_PLATFORM_UTILITY)
    plot_metric(avg_round_results, "num_active_workers", "Active Workers", PLOT_ACTIVE_WORKERS)
    plot_metric(avg_round_results, "cumulative_left_workers", "Cumulative Left Workers", PLOT_LEFT_WORKERS)
    plot_metric(avg_round_results, "avg_leave_probability", "Average Leave Probability", PLOT_LEAVE_PROB)

    print("全部完成")
    print("Average Summary:")
    for k, v in avg_summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
