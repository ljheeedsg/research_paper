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

PLOT_COMPLETION = "experiment2_cmab_trust_pgrd_completion_rate.png"
PLOT_QUALITY = "experiment2_cmab_trust_pgrd_avg_quality.png"
PLOT_CUM_COMPLETION = "experiment2_cmab_trust_pgrd_cumulative_completion_rate.png"
PLOT_CUM_QUALITY = "experiment2_cmab_trust_pgrd_cumulative_avg_quality.png"
PLOT_REWARD = "experiment2_cmab_trust_pgrd_reward.png"
PLOT_EFFICIENCY = "experiment2_cmab_trust_pgrd_efficiency.png"
PLOT_TRUST = "experiment2_cmab_trust_pgrd_avg_trust.png"
PLOT_MEMBER = "experiment2_cmab_trust_pgrd_member_count.png"
PLOT_FEE = "experiment2_cmab_trust_pgrd_fee_income.png"

TOTAL_SLOTS = 86400 // 600

PER_ROUND_BUDGET = 1000
DELTA = 0.6
ALPHA = 1.0

# Trust parameters
VALIDATION_TOP_M = 3
TRUST_INIT_TRUSTED = 1.0
TRUST_INIT_UNKNOWN = 0.5
ETA = 0.6
THETA_HIGH = 0.8
THETA_LOW = 0.2

# -------------------- PGRD parameters --------------------
RANDOM_SEED = 42

# 任务分类
MEMBER_RATIO = 0.6          # 前30%任务作为会员任务
MEMBER_MULTIPLIER = 1.5     # 会员任务收益倍率
NORMAL_MULTIPLIER = 1.0     # 普通任务收益倍率
MEMBER_COST_RATIO = 0.5     # 会员任务工人执行成本比例
NORMAL_COST_RATIO = 0.8     # 普通任务工人执行成本比例
QUALITY_TASK_WEIGHT = 0.4   # 质量敏感度中任务权重占比
QUALITY_TASK_REQ = 0.6      # 质量敏感度中所需工人数占比

# PGRD行为参数
PGRD_ALPHA = 0.6            # 历史收益权重
PGRD_BETA = 0.4             # 当前平均收益权重
PGRD_ZETA = 1.2             # softmax敏感度
PGRD_LAMBDA = 1.8           # 损失厌恶系数
PGRD_SIGMA = 0.85           # 损失曲率
PGRD_FEE = 1.0           # 会费
PGRD_PSI_TH = 0.4          # 成为会员的概率阈值
MEMBER_VALIDITY = 10       # 会员有效轮数
SCORE_TRUST_WEIGHT = 0.35  # 招募评分中 trust 权重
MEMBER_SCORE_BONUS = 0.15  # 会员任务的质量敏感加成

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


def build_task_catalog(task_dict):
    """
    基于“质量敏感度”划分 member / normal 任务。
    这里只新增任务类型与“用于PGRD的任务收益”，不改业务 reward 定义。
    """
    tasks = list(task_dict.values())

    max_weight = max((float(t["weight"]) for t in tasks), default=1.0)
    max_required = max((int(t["required_workers"]) for t in tasks), default=1)

    for task in tasks:
        weight_score = float(task["weight"]) / max_weight if max_weight > 0 else 0.0
        required_score = int(task["required_workers"]) / max_required if max_required > 0 else 0.0
        quality_priority = (
            QUALITY_TASK_WEIGHT * weight_score +
            QUALITY_TASK_REQ * required_score
        )
        task["quality_priority"] = round(float(quality_priority), 4)

    tasks.sort(key=lambda x: (-x["quality_priority"], -x["weight"], -x["required_workers"], x["task_id"]))

    member_num = max(1, int(len(tasks) * MEMBER_RATIO)) if tasks else 0
    member_task_ids = set(t["task_id"] for t in tasks[:member_num])

    task_catalog = {}
    for task in tasks:
        task_id = task["task_id"]
        base_reward = float(task["weight"])

        if task_id in member_task_ids:
            task_type = "member"
            task_reward = base_reward * MEMBER_MULTIPLIER
            worker_cost = task_reward * MEMBER_COST_RATIO
        else:
            task_type = "normal"
            task_reward = base_reward * NORMAL_MULTIPLIER
            worker_cost = task_reward * NORMAL_COST_RATIO

        task_catalog[task_id] = {
            "task_id": task_id,
            "slot_id": task["slot_id"],
            "region_id": task["region_id"],
            "required_workers": task["required_workers"],
            "weight": task["weight"],
            "quality_priority": task["quality_priority"],
            "type": task_type,
            "task_reward": round(task_reward, 4),   # PGRD / 历史收益更新用
            "worker_cost": round(worker_cost, 4),   # PGRD 成本估计
        }

    member_count = sum(1 for t in task_catalog.values() if t["type"] == "member")
    normal_count = sum(1 for t in task_catalog.values() if t["type"] == "normal")
    print(f"任务分类完成: member={member_count}, normal={normal_count}")
    return task_catalog


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

            # PGRD state
            "is_member": False,
            "member_until": -1,
            "hist_reward_m": 0.0,   # 上一轮会员任务平均收益
            "hist_reward_n": 0.0,   # 上一轮普通任务平均收益
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


def compute_ucb(avg_quality, n_obs, total_observations, alpha=ALPHA):
    """
    与你当前B3保持一致：
    UCB 探索项使用累计学习总次数，而不是轮次 t。
    """
    return avg_quality + math.sqrt(alpha * math.log(max(2, total_observations)) / (n_obs + 1))


# ==================== PGRD ====================
def get_worker_current_slot_tasks(worker, slot_id):
    task_ids = worker["tasks_by_slot"].get(slot_id, [])
    return [worker["task_map"][tid] for tid in task_ids if tid in worker["task_map"]]


def pgrd_decision_for_worker(worker, slot_id, task_catalog, R_m, R_n):
    """
    采用 experiment3_B4 中更稳定的 PGRD 逻辑：
    - 会员资格具有持续期
    - trusted 工人按阈值决定是否成为会员
    - unknown / malicious 不可成为会员
    """
    current_tasks = get_worker_current_slot_tasks(worker, slot_id)

    member_tasks = []
    normal_tasks = []

    for t in current_tasks:
        tid = t["task_id"]
        if task_catalog[tid]["type"] == "member":
            member_tasks.append(tid)
        else:
            normal_tasks.append(tid)

    # 默认输出
    result = {
        "is_member": False,
        "bid_tasks": normal_tasks.copy(),
        "member_tasks": member_tasks,
        "normal_tasks": normal_tasks,
        "b_m": 0.0,
        "b_n": 0.0,
        "loss": 0.0,
        "U_member": 0.0,
        "U_normal": 0.0,
        "psi": 0.0,
        "fee_paid": 0.0,
        "member_until": worker.get("member_until", -1),
    }

    if worker["category"] == "malicious":
        result["bid_tasks"] = []
        return result

    if worker["is_member"] and worker["member_until"] >= slot_id:
        result["is_member"] = True
        result["bid_tasks"] = member_tasks + normal_tasks
        result["member_until"] = worker["member_until"]
        return result

    # 非 trusted 不能成为会员
    if worker["category"] != "trusted":
        return result

    # 没有会员任务可选，则没有成为会员的意义
    if len(member_tasks) == 0:
        return result

    # 预期收益（上一轮历史 + 当前全局平均）
    b_m = PGRD_ALPHA * worker["hist_reward_m"] + PGRD_BETA * R_m
    b_n = PGRD_ALPHA * worker["hist_reward_n"] + PGRD_BETA * R_n

    # 参照损失采用全局会员/普通收益差，避免被局部噪声抹平。
    delta = PGRD_BETA * (R_m - R_n)
    loss = PGRD_LAMBDA * (delta ** PGRD_SIGMA) if delta > 0 else 0.0

    cost_m = float(np.mean([task_catalog[tid]["worker_cost"] for tid in member_tasks])) if member_tasks else 0.0
    cost_n = float(np.mean([task_catalog[tid]["worker_cost"] for tid in normal_tasks])) if normal_tasks else 0.0

    U_member = b_m + loss - cost_m - PGRD_FEE
    U_normal = b_n - cost_n

    # softmax 概率
    x_m = max(-50.0, min(50.0, PGRD_ZETA * U_member))
    x_n = max(-50.0, min(50.0, PGRD_ZETA * U_normal))
    exp_m = math.exp(x_m)
    exp_n = math.exp(x_n)
    psi = exp_m / (exp_m + exp_n) if (exp_m + exp_n) > 0 else 0.0

    choose_member = (psi >= PGRD_PSI_TH)

    if choose_member:
        bid_tasks = member_tasks + normal_tasks
        fee_paid = PGRD_FEE
        worker["is_member"] = True
        worker["member_until"] = slot_id + MEMBER_VALIDITY
    else:
        bid_tasks = normal_tasks.copy()
        fee_paid = 0.0
        worker["is_member"] = False
        worker["member_until"] = -1

    result.update({
        "is_member": choose_member,
        "bid_tasks": bid_tasks,
        "b_m": round(b_m, 4),
        "b_n": round(b_n, 4),
        "loss": round(loss, 4),
        "U_member": round(U_member, 4),
        "U_normal": round(U_normal, 4),
        "psi": round(psi, 4),
        "fee_paid": round(fee_paid, 4),
        "member_until": worker["member_until"],
    })
    return result


def build_bid_tasks_map(available_workers, slot_id, task_catalog, R_m, R_n):
    """
    对当前轮所有可用工人做PGRD决策，生成:
    - bid_tasks_map
    - pgrd_records
    - fee_income
    - member_count
    """
    bid_tasks_map = {}
    pgrd_records = []
    fee_income = 0.0
    member_count = 0

    for worker in available_workers:
        decision = pgrd_decision_for_worker(worker, slot_id, task_catalog, R_m, R_n)

        worker["is_member"] = decision["is_member"]
        bid_tasks_map[worker["worker_id"]] = decision["bid_tasks"]

        fee_income += decision["fee_paid"]
        if decision["is_member"]:
            member_count += 1

        pgrd_records.append({
            "worker_id": worker["worker_id"],
            "category": worker["category"],
            "is_member": decision["is_member"],
            "member_task_count": len(decision["member_tasks"]),
            "normal_task_count": len(decision["normal_tasks"]),
            "bid_task_count": len(decision["bid_tasks"]),
            "b_m": decision["b_m"],
            "b_n": decision["b_n"],
            "loss": decision["loss"],
            "U_member": decision["U_member"],
            "U_normal": decision["U_normal"],
            "psi": decision["psi"],
            "fee_paid": decision["fee_paid"],
            "member_until": decision["member_until"],
        })

    return bid_tasks_map, pgrd_records, round(fee_income, 4), member_count


# ==================== Selection ====================
def compute_worker_score(worker, bid_tasks_map, total_observations):
    """
    质量优先版评分：
    score = gain / cost
    gain = sum(weight * quality_signal * task_bonus)

    其中 quality_signal 同时考虑 UCB 质量与 trust，
    让 PGRD 在招募阶段真正影响质量而不只是影响可见任务集合。
    """
    candidate_task_ids = bid_tasks_map.get(worker["worker_id"], [])
    if not candidate_task_ids:
        return 0.0, []

    q_hat = compute_ucb(worker["avg_quality"], worker["n_obs"], total_observations, ALPHA)
    quality_signal = (
        (1.0 - SCORE_TRUST_WEIGHT) * q_hat +
        SCORE_TRUST_WEIGHT * worker["trust"]
    )

    gain = 0.0
    selected_tasks = []
    for task_id in candidate_task_ids:
        task = worker["task_map"][task_id]
        task_bonus = 1.0
        if worker["is_member"]:
            task_bonus += MEMBER_SCORE_BONUS * float(task.get("quality_priority", 0.0))
        gain += float(task["weight"]) * quality_signal * task_bonus
        selected_tasks.append(task_id)

    cost = worker["cost"]
    if cost <= 0:
        return 0.0, selected_tasks

    score = gain / cost
    return score, selected_tasks


def initialization_select_workers(available_workers, bid_tasks_map, budget):
    """
    初始化轮：
    只从 trusted + unknown 中选，malicious 初始不存在。
    为避免免费全选，仍受预算限制。
    """
    candidates = []
    for worker in available_workers:
        if worker["category"] == "malicious":
            continue
        task_ids = bid_tasks_map.get(worker["worker_id"], [])
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


def greedy_select_workers(available_workers, bid_tasks_map, total_observations, budget):
    """
    正常轮：
    候选 = trusted ∪ unknown，排除 malicious
    """
    worker_scores = []

    for worker in available_workers:
        if worker["category"] == "malicious":
            continue

        score, selected_tasks = compute_worker_score(worker, bid_tasks_map, total_observations)
        worker_scores.append({
            "worker_id": worker["worker_id"],
            "score": score,
            "cost": worker["cost"],
            "task_ids": selected_tasks,
            "category": worker["category"],
            "trust": round(worker["trust"], 4),
            "is_member": worker["is_member"],
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


# ==================== Evaluation ====================
def evaluate_business_tasks(selected_worker_ids, workers, round_tasks, bid_tasks_map, slot_id, delta):
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
        for task_id in bid_tasks_map.get(worker_id, []):
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
        "task_execution": task_execution,
    }


# ==================== Validation / Trust ====================
def select_validation_tasks(selected_worker_ids, workers, round_tasks, bid_tasks_map, slot_id, top_m):
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
            if task_id not in bid_tasks_map.get(worker_id, []):
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


# ==================== Statistics Update ====================
def update_worker_quality_statistics(selected_worker_ids, workers, bid_tasks_map):
    """
    按本轮实际执行任务的 quality 更新 CMAB 统计量，
    并返回本轮新增的学习次数。
    """
    total_new_observations = 0

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        task_ids = bid_tasks_map.get(worker_id, [])
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


def update_pgrd_rewards(selected_worker_ids, workers, bid_tasks_map, task_catalog, task_results, prev_R_m, prev_R_n):
    """
    更新：
    1. 每个工人的上一轮会员/普通任务收益
    2. 全局 R_m, R_n（下一轮PGRD用）

    这里让全局均值显式依赖会员身份，否则 PGRD 决策不会真正反馈到下一轮。
    """
    completed_task_ids = {tr["task_id"] for tr in task_results if tr["completed"]}

    member_rewards_global = []
    normal_rewards_global = []

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        task_ids = bid_tasks_map.get(worker_id, [])

        member_rewards_local = []
        normal_rewards_local = []

        for tid in task_ids:
            if tid not in completed_task_ids:
                continue
            reward = task_catalog[tid]["task_reward"]
            if task_catalog[tid]["type"] == "member":
                member_rewards_local.append(reward)
            else:
                normal_rewards_local.append(reward)

        if member_rewards_local:
            worker["hist_reward_m"] = float(np.mean(member_rewards_local))
        else:
            worker["hist_reward_m"] = 0.0

        if normal_rewards_local:
            worker["hist_reward_n"] = float(np.mean(normal_rewards_local))
        else:
            worker["hist_reward_n"] = 0.0

        if worker["is_member"] and worker["member_until"] >= 0:
            if worker["hist_reward_m"] > 0:
                member_rewards_global.append(worker["hist_reward_m"])
        else:
            if worker["hist_reward_n"] > 0:
                normal_rewards_global.append(worker["hist_reward_n"])

    if member_rewards_global:
        R_m = float(np.mean(member_rewards_global))
    else:
        R_m = prev_R_m

    if normal_rewards_global:
        R_n = float(np.mean(normal_rewards_global))
    else:
        R_n = prev_R_n

    return round(R_m, 4), round(R_n, 4)


# ==================== Output ====================
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
    valid_non_init_rounds = [r for r in valid_rounds if not r["is_initialization"]]

    def safe_mean(key, data):
        if not data:
            return 0.0
        return round(float(np.mean([r[key] for r in data])), 4)

    cumulative_all = compute_cumulative_summary(valid_rounds)
    cumulative_non_init = compute_cumulative_summary(valid_non_init_rounds)

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
        "avg_member_count_all_non_empty": safe_mean("member_count", valid_rounds),
        "avg_fee_income_all_non_empty": safe_mean("fee_income", valid_rounds),

        "avg_completion_rate_non_init": safe_mean("completion_rate", valid_non_init_rounds),
        "avg_avg_quality_non_init": safe_mean("avg_quality", valid_non_init_rounds),
        "avg_reward_non_init": safe_mean("reward", valid_non_init_rounds),
        "avg_cost_non_init": safe_mean("cost", valid_non_init_rounds),
        "avg_efficiency_non_init": safe_mean("efficiency", valid_non_init_rounds),
        "avg_avg_trust_non_init": safe_mean("avg_trust", valid_non_init_rounds),
        "avg_member_count_non_init": safe_mean("member_count", valid_non_init_rounds),
        "avg_fee_income_non_init": safe_mean("fee_income", valid_non_init_rounds),

        "final_cumulative_completion_rate_all_non_empty": cumulative_all["cumulative_completion_rate"],
        "final_cumulative_avg_quality_all_non_empty": cumulative_all["cumulative_avg_quality"],
        "final_cumulative_completion_rate_non_init": cumulative_non_init["cumulative_completion_rate"],
        "final_cumulative_avg_quality_non_init": cumulative_non_init["cumulative_avg_quality"],
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


# ==================== Main ====================
def main():
    worker_options = load_worker_options()
    task_dict, tasks_by_slot = load_all_tasks_from_workers(worker_options)
    task_catalog = build_task_catalog(task_dict)
    workers = build_worker_profiles(worker_options)

    round_results = []
    total_observations = 0
    cumulative_state = {
        "num_tasks": 0,
        "num_completed": 0,
        "quality_sum": 0.0,
        "quality_count": 0,
    }

    # PGRD 全局平均收益，初始用任务分类的平均收益
    member_rewards_init = [t["task_reward"] for t in task_catalog.values() if t["type"] == "member"]
    normal_rewards_init = [t["task_reward"] for t in task_catalog.values() if t["type"] == "normal"]
    R_m = float(np.mean(member_rewards_init)) if member_rewards_init else 0.0
    R_n = float(np.mean(normal_rewards_init)) if normal_rewards_init else 0.0

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)
        is_initialization = (len(round_results) == 0)

        # ---------- PGRD ----------
        bid_tasks_map, pgrd_records, fee_income_t, member_count_t = build_bid_tasks_map(
            available_workers=available_workers,
            slot_id=slot_id,
            task_catalog=task_catalog,
            R_m=R_m,
            R_n=R_n,
        )

        # ---------- Selection ----------
        if is_initialization:
            selected_worker_ids, cost_t, selection_details = initialization_select_workers(
                available_workers, bid_tasks_map, PER_ROUND_BUDGET
            )
        else:
            selected_worker_ids, cost_t, selection_details = greedy_select_workers(
                available_workers, bid_tasks_map, total_observations, PER_ROUND_BUDGET
            )

        # ---------- Business tasks ----------
        business_eval = evaluate_business_tasks(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            bid_tasks_map=bid_tasks_map,
            slot_id=slot_id,
            delta=DELTA,
        )

        # ---------- Validation ----------
        validation_tasks, validation_candidates = select_validation_tasks(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            bid_tasks_map=bid_tasks_map,
            slot_id=slot_id,
            top_m=VALIDATION_TOP_M,
        )

        # ---------- Trust update ----------
        trust_update_records = update_trust_by_validation(
            validation_tasks=validation_tasks,
            workers=workers,
            slot_id=slot_id,
        )

        # ---------- Rebuild U sets ----------
        Uc, Uu, Um = rebuild_sets(workers)

        # ---------- Update CMAB stats ----------
        total_observations_before_round = total_observations
        total_observations += update_worker_quality_statistics(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            bid_tasks_map=bid_tasks_map,
        )

        # ---------- Update PGRD rewards ----------
        R_m, R_n = update_pgrd_rewards(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            bid_tasks_map=bid_tasks_map,
            task_catalog=task_catalog,
            task_results=business_eval["task_results"],
            prev_R_m=R_m,
            prev_R_n=R_n,
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
            "num_executed": business_eval["num_executed"],
            "num_completed": business_eval["num_completed"],
            "completion_rate": business_eval["completion_rate"],
            "avg_quality": business_eval["avg_quality"],
            "reward": round(reward_t, 4),
            "cost": round(cost_t, 4),
            "efficiency": round(efficiency_t, 4),

            "avg_trust": round(avg_trust_t, 4),
            "num_validation_tasks": len(validation_tasks),
            "total_observations_before_round": total_observations_before_round,

            "trusted_count": len(Uc),
            "unknown_count": len(Uu),
            "malicious_count": len(Um),

            "member_count": member_count_t,
            "fee_income": round(fee_income_t, 4),
            "R_m": round(R_m, 4),
            "R_n": round(R_n, 4),

            "executed_tasks": business_eval["executed_tasks"],
            "completed_tasks": business_eval["completed_tasks"],
            "failed_tasks": business_eval["failed_tasks"],
            "task_results": business_eval["task_results"],

            "validation_tasks": validation_tasks,
            "trust_updates": trust_update_records,
            "pgrd_records": pgrd_records,
        }

        update_cumulative_metrics(round_result, cumulative_state)
        round_results.append(round_result)

        print(
            f"[Round {round_id:03d}] "
            f"init={is_initialization} | "
            f"tasks={round_result['num_tasks']} | "
            f"executed={round_result['num_executed']} | "
            f"completed={round_result['num_completed']} | "
            f"completion_rate={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"cum_completion={round_result['cumulative_completion_rate']:.4f} | "
            f"cum_quality={round_result['cumulative_avg_quality']:.4f} | "
            f"reward={round_result['reward']:.2f} | "
            f"cost={round_result['cost']:.2f} | "
            f"eff={round_result['efficiency']:.4f} | "
            f"avg_trust={round_result['avg_trust']:.4f} | "
            f"member={round_result['member_count']} | "
            f"fee={round_result['fee_income']:.2f} | "
            f"Uc={round_result['trusted_count']} | "
            f"Uu={round_result['unknown_count']} | "
            f"Um={round_result['malicious_count']}"
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
    plot_metric(round_results, "avg_trust", "Average Trust", PLOT_TRUST)
    plot_metric(round_results, "member_count", "Member Count", PLOT_MEMBER)
    plot_metric(round_results, "fee_income", "Fee Income", PLOT_FEE)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
