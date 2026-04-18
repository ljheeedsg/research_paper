import json
import math
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"

ROUND_RESULTS_FILE = "experiment2_cmab_trust_pgrd_round_results.json"
SUMMARY_FILE = "experiment2_cmab_trust_pgrd_summary.json"

PLOT_COVERAGE = "experiment2_cmab_trust_pgrd_coverage_rate.png"
PLOT_COMPLETION = "experiment2_cmab_trust_pgrd_completion_rate.png"
PLOT_AVG_QUALITY = "experiment2_cmab_trust_pgrd_avg_quality.png"
PLOT_CUM_COVERAGE = "experiment2_cmab_trust_pgrd_cumulative_coverage_rate.png"
PLOT_CUM_COMPLETION = "experiment2_cmab_trust_pgrd_cumulative_completion_rate.png"
PLOT_CUM_QUALITY = "experiment2_cmab_trust_pgrd_cumulative_avg_quality.png"
PLOT_TRUSTED = "experiment2_cmab_trust_pgrd_trusted_count.png"
PLOT_UNKNOWN = "experiment2_cmab_trust_pgrd_unknown_count.png"
PLOT_MALICIOUS = "experiment2_cmab_trust_pgrd_malicious_count.png"
PLOT_VALIDATION = "experiment2_cmab_trust_pgrd_validation_count.png"
PLOT_MEMBER = "experiment2_cmab_trust_pgrd_member_count.png"

TOTAL_SLOTS = 86400 // 600
PER_ROUND_BUDGET = 1000
K = 7
RANDOM_SEED = 3

# 完成判定质量阈值
DELTA = 0.45
DEFAULT_INIT_UCB = 1.0

# ========== Step 5: validation ==========
VALIDATION_TOP_M = 5

TRUST_INIT_TRUSTED = 1.0
TRUST_INIT_UNKNOWN = 0.5

ETA = 0.10
THETA_HIGH = 0.8
THETA_LOW = 0.20

ERROR_GOOD = 0.15
ERROR_BAD = 0.35

# ========== Step 6: PGRD ==========
# 会员任务占比：从每轮任务中选一部分作为会员任务
MEMBER_TASK_RATIO = 0.5

# 会员任务和普通任务的收益系数
MEMBER_REWARD_MULTIPLIER = 1.25
NORMAL_REWARD_MULTIPLIER = 1.00

# 会员费
MEMBERSHIP_FEE = 2.0

# 参照依赖损失系数
LAMBDA_REF = 2.0

# 概率敏感系数（logit）
XI = 4.0

# 概率阈值
PSI_THRESHOLD = 0.55

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
    平台初始只知道 trusted；
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

            # membership state
            "is_member": False,
            "last_membership_prob": 0.0,
            "last_member_utility": 0.0,
            "last_normal_utility": 0.0,

            # CMAB stats
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


# ==================== CMAB ====================
def compute_ucb(worker, total_observations):
    if worker["n_obs"] <= 0:
        return DEFAULT_INIT_UCB

    total_learned_counts = max(2, total_observations)
    explore = math.sqrt((K + 1) * math.log(total_learned_counts) / worker["n_obs"])
    return min(1.0, float(worker["avg_quality"]) + explore)


def split_member_and_normal_tasks(round_tasks, member_task_ratio):
    """
    按权重从高到低，取前一部分作为会员任务。
    """
    if not round_tasks:
        return set(), set()

    sorted_tasks = sorted(round_tasks, key=lambda x: (-float(x["weight"]), x["task_id"]))
    member_count = max(1, int(round(len(sorted_tasks) * member_task_ratio)))
    member_count = min(member_count, len(sorted_tasks))

    member_task_ids = {task["task_id"] for task in sorted_tasks[:member_count]}
    normal_task_ids = {task["task_id"] for task in sorted_tasks[member_count:]}
    return member_task_ids, normal_task_ids


# ==================== PGRD membership ====================
def sigmoid(x):
    x = max(-20.0, min(20.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def update_membership_by_pgrd(available_workers, slot_id, member_task_ids, normal_task_ids):
    """
    只有 trusted 才允许成为会员。
    会员选择依据：会员任务预期收益 vs 普通任务预期收益。
    """
    membership_records = []

    for worker in available_workers:
        worker["last_membership_prob"] = 0.0
        worker["last_member_utility"] = 0.0
        worker["last_normal_utility"] = 0.0

        # 非 trusted 一律不能是会员
        if worker["category"] != "trusted":
            worker["is_member"] = False
            continue

        bid_task_ids = set(worker["tasks_by_slot"].get(slot_id, []))
        member_bid_tasks = list(bid_task_ids & member_task_ids)
        normal_bid_tasks = list(bid_task_ids & normal_task_ids)

        member_weights = [float(worker["task_map"][tid]["weight"]) for tid in member_bid_tasks]
        normal_weights = [float(worker["task_map"][tid]["weight"]) for tid in normal_bid_tasks]

        total_bid_tasks = max(1, len(member_bid_tasks) + len(normal_bid_tasks))
        unit_cost = float(worker["bid_price"]) / total_bid_tasks

        # 参照依赖：会员任务的收益更高，普通任务作为对照
        member_reward_sum = MEMBER_REWARD_MULTIPLIER * sum(member_weights)
        normal_reward_sum = NORMAL_REWARD_MULTIPLIER * sum(normal_weights)

        # 参照损失：放弃会员任务相对普通任务的差异感知
        ref_loss = -LAMBDA_REF * abs(member_reward_sum - normal_reward_sum)

        member_cost_sum = unit_cost * max(1, len(member_bid_tasks))
        normal_cost_sum = unit_cost * max(1, len(normal_bid_tasks))

        R_member = member_reward_sum + ref_loss - member_cost_sum - MEMBERSHIP_FEE
        R_normal = normal_reward_sum - normal_cost_sum

        psi = sigmoid(XI * (R_member - R_normal))
        is_member = (len(member_bid_tasks) > 0) and (psi >= PSI_THRESHOLD)

        worker["is_member"] = is_member
        worker["last_membership_prob"] = psi
        worker["last_member_utility"] = R_member
        worker["last_normal_utility"] = R_normal

        membership_records.append({
            "worker_id": worker["worker_id"],
            "member_candidate": True,
            "member_bid_task_count": len(member_bid_tasks),
            "normal_bid_task_count": len(normal_bid_tasks),
            "member_reward_sum": round(member_reward_sum, 4),
            "normal_reward_sum": round(normal_reward_sum, 4),
            "member_utility": round(R_member, 4),
            "normal_utility": round(R_normal, 4),
            "membership_probability": round(psi, 4),
            "is_member": is_member,
        })

    return membership_records


def compute_worker_marginal_gain(
    worker,
    slot_id,
    round_task_ids,
    current_best_quality,
    total_observations,
    member_task_ids,
    normal_task_ids,
):
    """
    论文风格边际增益：
        Delta_i(t) = sum_j w_j * max(0, q_hat_i(t) - Q_j^cur(t))

    约束：
    - member task 只能由 is_member=True 的 trusted 工人做
    - normal task 由所有非 malicious 工人做
    """
    raw_bid_task_ids = [
        task_id
        for task_id in worker["tasks_by_slot"].get(slot_id, [])
        if task_id in round_task_ids
    ]
    if not raw_bid_task_ids:
        return None

    allowed_bid_task_ids = []
    for task_id in raw_bid_task_ids:
        if task_id in member_task_ids:
            if worker["is_member"] and worker["category"] == "trusted":
                allowed_bid_task_ids.append(task_id)
        elif task_id in normal_task_ids:
            allowed_bid_task_ids.append(task_id)

    if not allowed_bid_task_ids:
        return None

    q_hat = compute_ucb(worker, total_observations)
    marginal_gain = 0.0
    marginal_details = []

    for task_id in allowed_bid_task_ids:
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
                "task_type": "member" if task_id in member_task_ids else "normal",
            })

    cost = float(worker["bid_price"])
    score = (marginal_gain / cost) if (marginal_gain > 0 and cost > 0) else 0.0

    return {
        "worker_id": worker["worker_id"],
        "bid_price": round(cost, 4),
        "q_hat": round(q_hat, 4),
        "bid_task_ids": allowed_bid_task_ids,
        "marginal_task_count": len(marginal_details),
        "marginal_gain": round(marginal_gain, 4),
        "score": round(score, 6),
        "marginal_details": marginal_details,
        "trust": round(float(worker["trust"]), 4),
        "category": worker["category"],
        "is_member": bool(worker["is_member"]),
        "membership_probability": round(float(worker["last_membership_prob"]), 4),
    }


def greedy_select_workers(
    available_workers,
    slot_id,
    round_tasks,
    total_observations,
    budget,
    member_task_ids,
    normal_task_ids,
):
    """
    基于论文风格 CMAB 招募，但排除 malicious；
    并对会员任务施加会员访问约束。
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
                member_task_ids=member_task_ids,
                normal_task_ids=normal_task_ids,
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


def evaluate_round(selected_worker_ids, workers, round_tasks, slot_id, delta, member_task_ids, normal_task_ids):
    """
    实际执行评价：
    - member task 只能由 member trusted 执行
    - normal task 由非 malicious 执行
    """
    task_quality_values = defaultdict(list)
    task_execution = defaultdict(list)

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]

        for task_id in worker["tasks_by_slot"].get(slot_id, []):
            if task_id not in worker["task_map"]:
                continue

            # 会员任务约束
            if task_id in member_task_ids:
                if not (worker["is_member"] and worker["category"] == "trusted"):
                    continue
            elif task_id in normal_task_ids:
                if worker["category"] == "malicious":
                    continue

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
            "task_type": "member" if task_id in member_task_ids else "normal",
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


# ==================== validation ====================
def generate_validation_tasks_by_grid(available_workers, workers, task_grid_map, round_tasks, slot_id, top_m):
    available_ids = {w["worker_id"] for w in available_workers}
    round_task_ids = {task["task_id"] for task in round_tasks}

    grid_uc = defaultdict(int)
    grid_uu = defaultdict(int)
    grid_tasks = defaultdict(set)

    for worker_id in available_ids:
        worker = workers[worker_id]

        for task_id in worker["tasks_by_slot"].get(slot_id, []):
            if task_id not in round_task_ids:
                continue

            gid = task_grid_map.get(task_id)
            if gid is None:
                continue

            grid_tasks[gid].add(task_id)

            if worker["category"] == "trusted":
                grid_uc[gid] += 1
            elif worker["category"] == "unknown":
                grid_uu[gid] += 1

    candidate_grids = []
    for gid in grid_tasks:
        uc_cnt = grid_uc.get(gid, 0)
        uu_cnt = grid_uu.get(gid, 0)

        if uc_cnt > 0 and uu_cnt > 0:
            candidate_grids.append({
                "grid_id": gid,
                "trusted_count": uc_cnt,
                "unknown_count": uu_cnt,
                "task_ids": sorted(list(grid_tasks[gid])),
            })

    candidate_grids.sort(
        key=lambda x: (-x["unknown_count"], -x["trusted_count"], x["grid_id"])
    )

    selected_grids = candidate_grids[:top_m]

    validation_tasks = []
    for item in selected_grids:
        chosen_task = item["task_ids"][0]
        validation_tasks.append({
            "task_id": chosen_task,
            "grid_id": item["grid_id"],
            "trusted_count": item["trusted_count"],
            "unknown_count": item["unknown_count"],
        })

    return validation_tasks, candidate_grids


def update_trust_by_validation(validation_tasks, available_workers, workers, slot_id):
    trust_update_records = []
    available_ids = {w["worker_id"] for w in available_workers}

    for item in validation_tasks:
        task_id = item["task_id"]

        trusted_workers = []
        unknown_workers = []

        for worker_id in available_ids:
            worker = workers[worker_id]
            if task_id not in worker["tasks_by_slot"].get(slot_id, []):
                continue

            if worker["category"] == "trusted":
                trusted_workers.append(worker_id)
            elif worker["category"] == "unknown":
                unknown_workers.append(worker_id)

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
                "true_init_category": worker["init_category"],
            })

    return trust_update_records


def update_worker_statistics(selected_worker_ids, workers, slot_id):
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
        "selection_logic": "paper_style_cmab_plus_validation_plus_pgrd",
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
        "avg_validation_count_all_non_empty": safe_mean("num_validation_tasks", valid_rounds),
        "avg_trusted_count_all_non_empty": safe_mean("trusted_count", valid_rounds),
        "avg_unknown_count_all_non_empty": safe_mean("unknown_count", valid_rounds),
        "avg_malicious_count_all_non_empty": safe_mean("malicious_count", valid_rounds),
        "avg_member_count_all_non_empty": safe_mean("member_count", valid_rounds),
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
    }

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)

        # Step A: 划分会员任务 / 普通任务
        member_task_ids, normal_task_ids = split_member_and_normal_tasks(
            round_tasks=round_tasks,
            member_task_ratio=MEMBER_TASK_RATIO,
        )

        # Step B: trusted 工人根据 PGRD 决定是否成为会员
        membership_records = update_membership_by_pgrd(
            available_workers=available_workers,
            slot_id=slot_id,
            member_task_ids=member_task_ids,
            normal_task_ids=normal_task_ids,
        )

        # Step C: 论文风格 CMAB + 会员任务访问约束
        selected_worker_ids, cost_t, selection_details, est_quality_state = greedy_select_workers(
            available_workers=available_workers,
            slot_id=slot_id,
            round_tasks=round_tasks,
            total_observations=total_observations,
            budget=PER_ROUND_BUDGET,
            member_task_ids=member_task_ids,
            normal_task_ids=normal_task_ids,
        )

        # Step D: 本轮业务任务评价
        eval_result = evaluate_round(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            slot_id=slot_id,
            delta=DELTA,
            member_task_ids=member_task_ids,
            normal_task_ids=normal_task_ids,
        )

        # Step E: 验证任务
        validation_tasks, validation_candidates = generate_validation_tasks_by_grid(
            available_workers=available_workers,
            workers=workers,
            task_grid_map=task_grid_map,
            round_tasks=round_tasks,
            slot_id=slot_id,
            top_m=VALIDATION_TOP_M,
        )

        # Step F: 验证并更新 trust
        trust_update_records = update_trust_by_validation(
            validation_tasks=validation_tasks,
            available_workers=available_workers,
            workers=workers,
            slot_id=slot_id,
        )

        # Step G: 集合统计
        Uc, Uu, Um = rebuild_sets(workers)

        # Step H: 更新 CMAB 学习统计
        total_observations_before_round = total_observations
        total_observations += update_worker_statistics(selected_worker_ids, workers, slot_id)

        reward_t = eval_result["weighted_completion_quality"]
        efficiency_t = (reward_t / cost_t) if cost_t > 0 else 0.0

        member_count = sum(1 for w in workers.values() if w["is_member"])
        avg_member_prob = (
            float(np.mean([w["last_membership_prob"] for w in workers.values() if w["category"] == "trusted"]))
            if any(w["category"] == "trusted" for w in workers.values()) else 0.0
        )

        round_result = {
            "round_id": round_id,
            "slot_id": slot_id,
            "selection_mode": "paper_style_cmab_plus_validation_plus_pgrd",

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

            "member_task_count": len(member_task_ids),
            "normal_task_count": len(normal_task_ids),
            "member_task_ids": sorted(member_task_ids),
            "normal_task_ids": sorted(normal_task_ids),

            "membership_records": membership_records,
            "member_count": member_count,
            "avg_member_probability": round(avg_member_prob, 4),

            "num_validation_tasks": len(validation_tasks),
            "validation_tasks": validation_tasks,
            "validation_candidates": validation_candidates,
            "trust_updates": trust_update_records,

            "trusted_count": len(Uc),
            "unknown_count": len(Uu),
            "malicious_count": len(Um),

            "covered_tasks": eval_result["covered_tasks"],
            "completed_tasks": eval_result["completed_tasks"],
            "uncompleted_tasks": eval_result["uncompleted_tasks"],
            "task_results": eval_result["task_results"],
            "total_observations_before_round": total_observations_before_round,
        }

        update_cumulative_metrics(round_result, cumulative_state)
        round_results.append(round_result)

        print(
            f"[Round {round_id:03d}] "
            f"tasks={round_result['num_tasks']} | "
            f"member_tasks={round_result['member_task_count']} | "
            f"members={round_result['member_count']} | "
            f"selected={round_result['num_selected_workers']} | "
            f"validation={round_result['num_validation_tasks']} | "
            f"coverage={round_result['coverage_rate']:.4f} | "
            f"completion={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"trusted={round_result['trusted_count']} | "
            f"unknown={round_result['unknown_count']} | "
            f"malicious={round_result['malicious_count']} | "
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
    plot_metric(round_results, "trusted_count", "Trusted Count", PLOT_TRUSTED)
    plot_metric(round_results, "unknown_count", "Unknown Count", PLOT_UNKNOWN)
    plot_metric(round_results, "malicious_count", "Malicious Count", PLOT_MALICIOUS)
    plot_metric(round_results, "num_validation_tasks", "Validation Task Count", PLOT_VALIDATION)
    plot_metric(round_results, "member_count", "Member Count", PLOT_MEMBER)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
