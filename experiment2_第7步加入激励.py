import json
import math
import random
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


# ==================== Configuration ====================
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"

ROUND_RESULTS_FILE = "experiment2_cmab_trust_pgrd_lgsc_round_results.json"
SUMMARY_FILE = "experiment2_cmab_trust_pgrd_lgsc_summary.json"

PLOT_COVERAGE = "experiment2_cmab_trust_pgrd_lgsc_coverage_rate.png"
PLOT_COMPLETION = "experiment2_cmab_trust_pgrd_lgsc_completion_rate.png"
PLOT_AVG_QUALITY = "experiment2_cmab_trust_pgrd_lgsc_avg_quality.png"
PLOT_CUM_COVERAGE = "experiment2_cmab_trust_pgrd_lgsc_cumulative_coverage_rate.png"
PLOT_CUM_COMPLETION = "experiment2_cmab_trust_pgrd_lgsc_cumulative_completion_rate.png"
PLOT_CUM_QUALITY = "experiment2_cmab_trust_pgrd_lgsc_cumulative_avg_quality.png"

PLOT_TRUSTED = "experiment2_cmab_trust_pgrd_lgsc_trusted_count.png"
PLOT_UNKNOWN = "experiment2_cmab_trust_pgrd_lgsc_unknown_count.png"
PLOT_MALICIOUS = "experiment2_cmab_trust_pgrd_lgsc_malicious_count.png"
PLOT_VALIDATION = "experiment2_cmab_trust_pgrd_lgsc_validation_count.png"
PLOT_TRUST = "experiment2_cmab_trust_pgrd_lgsc_avg_trust.png"

PLOT_PLATFORM_UTILITY = "experiment2_cmab_trust_pgrd_lgsc_platform_utility.png"
PLOT_CUM_PLATFORM_UTILITY = "experiment2_cmab_trust_pgrd_lgsc_cumulative_platform_utility.png"
PLOT_ACTIVE_WORKERS = "experiment2_cmab_trust_pgrd_lgsc_active_workers.png"
PLOT_LEFT_WORKERS = "experiment2_cmab_trust_pgrd_lgsc_left_workers.png"
PLOT_LEAVE_PROB = "experiment2_cmab_trust_pgrd_lgsc_avg_leave_probability.png"

PLOT_MEMBER_COUNT = "experiment2_cmab_trust_pgrd_lgsc_member_count.png"
PLOT_TRUSTED_MEMBER_COUNT = "experiment2_cmab_trust_pgrd_lgsc_trusted_member_count.png"
PLOT_MEMBERSHIP_FEE_INCOME = "experiment2_cmab_trust_pgrd_lgsc_membership_fee_income.png"
PLOT_BONUS_PAYMENT = "experiment2_cmab_trust_pgrd_lgsc_bonus_payment.png"
PLOT_AVG_SUNK_VALUE = "experiment2_cmab_trust_pgrd_lgsc_avg_sunk_value.png"
PLOT_AVG_SUNK_RATE = "experiment2_cmab_trust_pgrd_lgsc_avg_sunk_rate.png"

TOTAL_SLOTS = 86400 // 600
PER_ROUND_BUDGET = 1000
K = 7
RANDOM_SEED = 3

DELTA = 0.45
DEFAULT_INIT_UCB = 1.0

RHO = 10.0
WORKER_COST_RATIO = 0.6

BETA0 = -1
BETA1 = 0.1
BETA2 = 0.1
BETA3 = 1.0
BETA4 = 2.0

VALIDATION_TOP_M = 5
TRUST_INIT_TRUSTED = 1.0
TRUST_INIT_UNKNOWN = 0.5
ETA = 0.10
THETA_HIGH = 0.8
THETA_LOW = 0.20
ERROR_GOOD = 0.15
ERROR_BAD = 0.35

MEMBERSHIP_FEE = 2
MEMBER_TASK_RATIO = 0.5
MEMBER_REWARD_MULTIPLIER = 1.25
NORMAL_REWARD_MULTIPLIER = 1.0
PGRD_LAMBDA = 1.5
PGRD_XI = 4.0
MEMBERSHIP_THRESHOLD = 0.55

SUNK_THRESHOLD = 12
MEMBER_BONUS = 12
RHO_INIT = 1.0

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
            "init_category": init_category,
            "base_quality": float(worker["base_quality"]),
            "available_slots": set(worker.get("available_slots", [])),
            "task_map": task_map,
            "tasks_by_slot": tasks_by_slot,
            "trust": trust,
            "category": category,
            "n_obs": 0,
            "avg_quality": 0.0,
            "is_active": True,
            "cumulative_reward": 0.0,
            "cumulative_cost": 0.0,
            "recent_reward": 0.0,
            "leave_probability": 0.0,
            "selected_rounds": 0,
            "active_rounds": 0,
            "left_round_id": None,
            "is_member": False,
            "membership_probability": 0.0,
            "cumulative_membership_fee": 0.0,
            "member_rounds": 0,
            "sunk_value": 0.0,
            "sunk_rate": RHO_INIT,
            "bonus_count": 0,
            "period_cost_sum": 0.0,
            "cumulative_bonus": 0.0,
            "current_sunk_loss": 0.0,
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
    if worker["n_obs"] <= 0:
        return DEFAULT_INIT_UCB

    total_learned_counts = max(2, total_observations)
    explore = math.sqrt((K + 1) * math.log(total_learned_counts) / worker["n_obs"])
    return min(1.0, float(worker["avg_quality"]) + explore)


def compute_worker_marginal_gain(
    worker,
    slot_id,
    round_task_ids,
    current_best_quality,
    total_observations,
    bid_tasks_map=None,
):
    candidate_bid_tasks = (
        bid_tasks_map.get(worker["worker_id"], [])
        if bid_tasks_map is not None else worker["tasks_by_slot"].get(slot_id, [])
    )
    bid_task_ids = [task_id for task_id in candidate_bid_tasks if task_id in round_task_ids]
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


def greedy_select_workers(available_workers, slot_id, round_tasks, total_observations, budget, bid_tasks_map=None):
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
                bid_tasks_map=bid_tasks_map,
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


def evaluate_round(selected_worker_ids, workers, round_tasks, slot_id, delta, bid_tasks_map=None):
    task_quality_values = defaultdict(list)
    task_execution = defaultdict(list)

    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        executed_task_ids = (
            bid_tasks_map.get(worker_id, [])
            if bid_tasks_map is not None else worker["tasks_by_slot"].get(slot_id, [])
        )
        for task_id in executed_task_ids:
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


def compute_platform_utility(platform_task_value, platform_payment, membership_fee_income, bonus_payment):
    platform_utility = platform_task_value + membership_fee_income - platform_payment - bonus_payment
    return {
        "platform_task_value": round(platform_task_value, 4),
        "platform_payment": round(platform_payment, 4),
        "membership_fee_income": round(membership_fee_income, 4),
        "bonus_payment": round(bonus_payment, 4),
        "platform_utility": round(platform_utility, 4),
    }


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
                worker["is_member"] = False
            else:
                worker["category"] = "unknown"
                if worker["is_member"]:
                    worker["is_member"] = False

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


def update_worker_statistics(selected_worker_ids, workers, slot_id, bid_tasks_map=None):
    total_new_observations = 0
    for worker_id in selected_worker_ids:
        worker = workers[worker_id]
        task_ids = (
            bid_tasks_map.get(worker_id, [])
            if bid_tasks_map is not None else worker["tasks_by_slot"].get(slot_id, [])
        )
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


def split_member_and_normal_tasks(round_tasks):
    if not round_tasks:
        return set(), set()

    task_infos = []
    for task in round_tasks:
        task_id = task["task_id"]
        weight = float(task["weight"])
        member_score = MEMBER_REWARD_MULTIPLIER * weight
        task_infos.append((task_id, member_score))

    task_infos.sort(key=lambda x: (-x[1], x[0]))
    member_count = max(1, int(round(len(task_infos) * MEMBER_TASK_RATIO)))
    member_count = min(member_count, len(task_infos))

    member_task_ids = {tid for tid, _ in task_infos[:member_count]}
    normal_task_ids = {tid for tid, _ in task_infos[member_count:]}
    return member_task_ids, normal_task_ids


def update_membership_by_pgrd(available_workers, slot_id, member_task_ids, normal_task_ids):
    membership_records = []
    member_worker_ids = []
    membership_fee_income_t = 0.0
    bid_tasks_map = {}

    for worker in available_workers:
        worker["membership_probability"] = 0.0

        bid_task_ids = set(worker["tasks_by_slot"].get(slot_id, []))
        member_bid_tasks = sorted(list(bid_task_ids & member_task_ids))
        normal_bid_tasks = sorted(list(bid_task_ids & normal_task_ids))

        if worker["category"] == "malicious":
            worker["is_member"] = False
            bid_tasks_map[worker["worker_id"]] = []
            continue

        if worker["category"] != "trusted":
            worker["is_member"] = False
            bid_tasks_map[worker["worker_id"]] = normal_bid_tasks
            continue

        n_m = len(member_bid_tasks)
        n_n = len(normal_bid_tasks)

        if n_m == 0 and n_n == 0:
            worker["is_member"] = False
            bid_tasks_map[worker["worker_id"]] = []
            continue

        member_net_values = []
        for tid in member_bid_tasks:
            weight = float(worker["task_map"][tid]["weight"])
            p_m = MEMBER_REWARD_MULTIPLIER * weight
            c_m = WORKER_COST_RATIO * float(worker["bid_price"])
            member_net_values.append(p_m - c_m)

        normal_net_values = []
        for tid in normal_bid_tasks:
            weight = float(worker["task_map"][tid]["weight"])
            p_n = NORMAL_REWARD_MULTIPLIER * weight
            c_n = WORKER_COST_RATIO * float(worker["bid_price"])
            normal_net_values.append(p_n - c_n)

        avg_member_net = float(np.mean(member_net_values)) if member_net_values else 0.0
        avg_normal_net = float(np.mean(normal_net_values)) if normal_net_values else 0.0

        R_A = n_m * avg_member_net - MEMBERSHIP_FEE
        R_B = n_n * avg_normal_net
        ref_loss = max(0.0, R_A - R_B)
        diff = R_A - R_B + PGRD_LAMBDA * ref_loss
        psi = sigmoid(PGRD_XI * diff)

        is_member = psi >= MEMBERSHIP_THRESHOLD
        worker["membership_probability"] = float(psi)
        worker["is_member"] = bool(is_member)

        if is_member:
            member_worker_ids.append(worker["worker_id"])
            membership_fee_income_t += MEMBERSHIP_FEE
            worker["cumulative_membership_fee"] += MEMBERSHIP_FEE
            worker["member_rounds"] += 1
            bid_tasks_map[worker["worker_id"]] = sorted(member_bid_tasks + normal_bid_tasks)
        else:
            bid_tasks_map[worker["worker_id"]] = normal_bid_tasks

        membership_records.append({
            "worker_id": worker["worker_id"],
            "member_task_count": n_m,
            "normal_task_count": n_n,
            "R_A": round(R_A, 4),
            "R_B": round(R_B, 4),
            "reference_loss": round(ref_loss, 4),
            "membership_probability": round(psi, 4),
            "is_member": bool(is_member),
            "bid_task_ids": bid_tasks_map[worker["worker_id"]],
        })

    return {
        "membership_records": membership_records,
        "member_worker_ids": member_worker_ids,
        "member_count": len(member_worker_ids),
        "membership_fee_income": round(membership_fee_income_t, 4),
        "bid_tasks_map": bid_tasks_map,
    }


def update_lgsc_state(selected_worker_ids, workers, slot_id, bid_tasks_map=None):
    bonus_payment_t = 0.0
    bonus_trigger_count = 0
    lgsc_records = []

    selected_set = set(selected_worker_ids)

    for worker_id in selected_set:
        worker = workers[worker_id]
        if not worker["is_member"]:
            worker["current_sunk_loss"] = (MEMBER_BONUS / SUNK_THRESHOLD) * worker["sunk_value"]
            continue

        task_ids = (
            bid_tasks_map.get(worker_id, [])
            if bid_tasks_map is not None else worker["tasks_by_slot"].get(slot_id, [])
        )
        if not task_ids:
            worker["current_sunk_loss"] = (MEMBER_BONUS / SUNK_THRESHOLD) * worker["sunk_value"]
            continue

        round_cost_sum = 0.0
        for _ in task_ids:
            round_cost_sum += WORKER_COST_RATIO * float(worker["bid_price"])

        worker["sunk_value"] += worker["sunk_rate"] * round_cost_sum
        worker["period_cost_sum"] += round_cost_sum

        bonus_triggered = False
        bonus_paid = 0.0

        if worker["sunk_value"] >= SUNK_THRESHOLD:
            bonus_paid = MEMBER_BONUS
            worker["cumulative_bonus"] += bonus_paid
            worker["bonus_count"] += 1

            G_i = worker["bonus_count"]
            C_last = max(worker["period_cost_sum"], 1e-8)
            worker["sunk_rate"] = 1.0 + (MEMBER_BONUS * G_i) / (MEMBER_BONUS * G_i + C_last)

            worker["sunk_value"] = 0.0
            worker["period_cost_sum"] = 0.0
            bonus_payment_t += bonus_paid
            bonus_trigger_count += 1
            bonus_triggered = True

        worker["current_sunk_loss"] = (MEMBER_BONUS / SUNK_THRESHOLD) * worker["sunk_value"]

        lgsc_records.append({
            "worker_id": worker_id,
            "is_member": True,
            "round_cost_sum": round(round_cost_sum, 4),
            "sunk_value": round(worker["sunk_value"], 4),
            "sunk_rate": round(worker["sunk_rate"], 4),
            "current_sunk_loss": round(worker["current_sunk_loss"], 4),
            "bonus_triggered": bonus_triggered,
            "bonus_paid": round(bonus_paid, 4),
            "bonus_count": worker["bonus_count"],
            "cumulative_bonus": round(worker["cumulative_bonus"], 4),
        })

    return {
        "bonus_payment": round(bonus_payment_t, 4),
        "bonus_trigger_count": bonus_trigger_count,
        "lgsc_records": lgsc_records,
    }


def update_worker_leave_state(workers, round_id, selected_worker_ids):
    """
    Step6 修正版退出判定：
    保留原有验证任务逻辑不变；
    仅对本轮被选中的工人执行退出判定。
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
        member_flag = 1 if worker["is_member"] else 0
        sunk_progress = worker["sunk_value"] / max(SUNK_THRESHOLD, 1e-8)

        leave_probability = sigmoid(
            BETA0
            + BETA1 * float(worker["cumulative_cost"])
            - BETA2 * float(avg_reward)
            - BETA3 * member_flag
            - BETA4 * sunk_progress
        )

        worker["leave_probability"] = float(leave_probability)
        leave_probabilities.append(float(leave_probability))

        if random.random() < leave_probability:
            worker["is_active"] = False
            worker["left_round_id"] = round_id
            worker["is_member"] = False
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
    cumulative_state["num_tasks"] += round_result["num_tasks"]
    cumulative_state["num_covered"] += round_result["num_covered"]
    cumulative_state["num_completed"] += round_result["num_completed"]
    cumulative_state["task_weight_sum"] += round_result["total_task_weight"]
    cumulative_state["weighted_completion_quality_sum"] += round_result["weighted_completion_quality"]
    cumulative_state["quality_sum"] += round_result["covered_quality_sum"]
    cumulative_state["quality_count"] += round_result["num_covered"]
    cumulative_state["platform_task_value_sum"] += round_result["platform_task_value"]
    cumulative_state["platform_payment_sum"] += round_result["platform_payment"]
    cumulative_state["membership_fee_income_sum"] += round_result["membership_fee_income"]
    cumulative_state["bonus_payment_sum"] += round_result["bonus_payment"]
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
    round_result["cumulative_normalized_completion_quality"] = round(cumulative_normalized_completion_quality, 4)
    round_result["cumulative_avg_quality"] = round(cumulative_avg_quality, 4)
    round_result["cumulative_platform_task_value"] = round(cumulative_state["platform_task_value_sum"], 4)
    round_result["cumulative_platform_payment"] = round(cumulative_state["platform_payment_sum"], 4)
    round_result["cumulative_membership_fee_income"] = round(cumulative_state["membership_fee_income_sum"], 4)
    round_result["cumulative_bonus_payment"] = round(cumulative_state["bonus_payment_sum"], 4)
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
        "membership_fee_income_sum": 0.0,
        "bonus_payment_sum": 0.0,
        "platform_utility_sum": 0.0,
    }

    for round_result in round_results:
        cumulative_state["num_tasks"] += round_result["num_tasks"]
        cumulative_state["num_covered"] += round_result["num_covered"]
        cumulative_state["num_completed"] += round_result["num_completed"]
        cumulative_state["task_weight_sum"] += round_result["total_task_weight"]
        cumulative_state["weighted_completion_quality_sum"] += round_result["weighted_completion_quality"]
        cumulative_state["quality_sum"] += round_result["covered_quality_sum"]
        cumulative_state["quality_count"] += round_result["num_covered"]
        cumulative_state["platform_task_value_sum"] += round_result["platform_task_value"]
        cumulative_state["platform_payment_sum"] += round_result["platform_payment"]
        cumulative_state["membership_fee_income_sum"] += round_result["membership_fee_income"]
        cumulative_state["bonus_payment_sum"] += round_result["bonus_payment"]
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
        "cumulative_membership_fee_income": round(cumulative_state["membership_fee_income_sum"], 4),
        "cumulative_bonus_payment": round(cumulative_state["bonus_payment_sum"], 4),
        "cumulative_platform_utility": round(cumulative_state["platform_utility_sum"], 4),
    }


def summarize_worker_longrun_stats(workers):
    active_workers = [w for w in workers.values() if w["is_active"]]
    member_workers = [w for w in workers.values() if w["is_member"]]

    def safe_mean(values):
        return round(float(np.mean(values)), 4) if values else 0.0

    return {
        "final_num_active_workers": len(active_workers),
        "final_num_member_workers": len(member_workers),
        "final_avg_cumulative_reward": safe_mean([w["cumulative_reward"] for w in workers.values()]),
        "final_avg_cumulative_cost": safe_mean([w["cumulative_cost"] for w in workers.values()]),
        "final_avg_membership_fee_paid": safe_mean([w["cumulative_membership_fee"] for w in workers.values()]),
        "final_avg_cumulative_bonus": safe_mean([w["cumulative_bonus"] for w in workers.values()]),
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
        "selection_logic": "paper_style_cmab_plus_validation_plus_pgrd_plus_lgsc",
        "max_selected_workers_per_round": K,
        "total_rounds_recorded": len(round_results),
        "total_non_empty_rounds": len(valid_rounds),
        "avg_num_selected_workers_all_non_empty": safe_mean("num_selected_workers", valid_rounds),
        "avg_coverage_rate_all_non_empty": safe_mean("coverage_rate", valid_rounds),
        "avg_completion_rate_all_non_empty": safe_mean("completion_rate", valid_rounds),
        "avg_avg_quality_all_non_empty": safe_mean("avg_quality", valid_rounds),
        "avg_membership_fee_income_all_non_empty": safe_mean("membership_fee_income", valid_rounds),
        "avg_bonus_payment_all_non_empty": safe_mean("bonus_payment", valid_rounds),
        "avg_platform_utility_all_non_empty": safe_mean("platform_utility", valid_rounds),
        "avg_member_count_all_non_empty": safe_mean("member_count", valid_rounds),
        "avg_num_active_workers_all_non_empty": safe_mean("num_active_workers", valid_rounds),
        "avg_leave_probability_all_non_empty": safe_mean("avg_leave_probability", valid_rounds),
        "final_cumulative_coverage_rate_all_non_empty": cumulative_all["cumulative_coverage_rate"],
        "final_cumulative_completion_rate_all_non_empty": cumulative_all["cumulative_completion_rate"],
        "final_cumulative_avg_quality_all_non_empty": cumulative_all["cumulative_avg_quality"],
        "final_cumulative_membership_fee_income": cumulative_all["cumulative_membership_fee_income"],
        "final_cumulative_bonus_payment": cumulative_all["cumulative_bonus_payment"],
        "final_cumulative_platform_utility": cumulative_all["cumulative_platform_utility"],
    }

    summary.update(worker_stats)

    if initial_stats:
        summary.update({
            "initial_total_workers": initial_stats["initial_total_workers"],
            "initial_true_trusted_count": initial_stats["initial_true_trusted_count"],
            "initial_true_unknown_count": initial_stats["initial_true_unknown_count"],
            "initial_true_malicious_count": initial_stats["initial_true_malicious_count"],
            "initial_avg_base_quality": initial_stats["initial_avg_base_quality"],
        })
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
        "platform_task_value_sum": 0.0,
        "platform_payment_sum": 0.0,
        "membership_fee_income_sum": 0.0,
        "bonus_payment_sum": 0.0,
        "platform_utility_sum": 0.0,
    }

    for slot_id in range(TOTAL_SLOTS):
        round_id = slot_id + 1
        round_tasks = get_tasks_for_slot(tasks_by_slot, slot_id)

        if SKIP_EMPTY_ROUNDS and not round_tasks:
            continue

        available_workers = get_available_workers(workers, slot_id)
        update_active_rounds(available_workers)
        # Step A: 先用 PGRD 决定会员身份和可投标任务
        for worker in workers.values():
            worker["is_member"] = False
            worker["membership_probability"] = 0.0

        member_task_ids, normal_task_ids = split_member_and_normal_tasks(round_tasks)
        membership_result = update_membership_by_pgrd(
            available_workers=available_workers,
            slot_id=slot_id,
            member_task_ids=member_task_ids,
            normal_task_ids=normal_task_ids,
        )
        bid_tasks_map = membership_result["bid_tasks_map"]

        # Step B: 在 PGRD 输出的 bid_tasks_map 上执行 CMAB 招募
        selected_worker_ids, cost_t, selection_details, est_quality_state = greedy_select_workers(
            available_workers=available_workers,
            slot_id=slot_id,
            round_tasks=round_tasks,
            total_observations=total_observations,
            budget=PER_ROUND_BUDGET,
            bid_tasks_map=bid_tasks_map,
        )

        # Step C: 本轮业务任务评价
        eval_result = evaluate_round(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            round_tasks=round_tasks,
            slot_id=slot_id,
            delta=DELTA,
            bid_tasks_map=bid_tasks_map,
        )

        # Step D: 验证任务与 trust 更新，逻辑保持不变
        validation_tasks, _ = generate_validation_tasks_by_grid(
            available_workers=available_workers,
            workers=workers,
            task_grid_map=task_grid_map,
            round_tasks=round_tasks,
            slot_id=slot_id,
            top_m=VALIDATION_TOP_M,
        )

        update_trust_by_validation(
            validation_tasks=validation_tasks,
            available_workers=available_workers,
            workers=workers,
            slot_id=slot_id,
        )

        for worker in workers.values():
            if worker["category"] != "trusted":
                worker["is_member"] = False

        reward_t = eval_result["weighted_completion_quality"]
        efficiency_t = (reward_t / cost_t) if cost_t > 0 else 0.0
        update_worker_reward_cost(selected_worker_ids, workers)

        # Step E: LGSC 奖励金与沉没成本
        lgsc_result = update_lgsc_state(
            selected_worker_ids=selected_worker_ids,
            workers=workers,
            slot_id=slot_id,
            bid_tasks_map=bid_tasks_map,
        )

        platform_task_value = sum(float(task_result["platform_value"]) for task_result in eval_result["task_results"])
        platform_payment = sum(float(workers[worker_id]["bid_price"]) for worker_id in selected_worker_ids)
        platform_result = compute_platform_utility(
            platform_task_value=platform_task_value,
            platform_payment=platform_payment,
            membership_fee_income=membership_result["membership_fee_income"],
            bonus_payment=lgsc_result["bonus_payment"],
        )

        leave_result = update_worker_leave_state(
            workers=workers,
            round_id=round_id,
            selected_worker_ids=selected_worker_ids,
        )

        total_observations_before_round = total_observations
        total_observations += update_worker_statistics(
            selected_worker_ids,
            workers,
            slot_id,
            bid_tasks_map=bid_tasks_map,
        )

        current_active_workers = sum(1 for worker in workers.values() if worker["is_active"])
        cumulative_left_workers = sum(1 for worker in workers.values() if not worker["is_active"])
        covered_quality_sum = sum(
            float(task_result["best_quality"])
            for task_result in eval_result["task_results"]
            if task_result["covered"]
        )

        round_result = {
            "round_id": round_id,
            "slot_id": slot_id,
            "selection_mode": "paper_style_cmab_plus_validation_plus_pgrd_plus_lgsc",
            "num_available_workers": len(available_workers),
            "num_selected_workers": len(selected_worker_ids),
            "num_tasks": eval_result["num_tasks"],
            "num_covered": eval_result["num_covered"],
            "num_completed": eval_result["num_completed"],
            "coverage_rate": eval_result["coverage_rate"],
            "completion_rate": eval_result["completion_rate"],
            "avg_quality": eval_result["avg_quality"],
            "weighted_completion_quality": eval_result["weighted_completion_quality"],
            "normalized_completion_quality": eval_result["normalized_completion_quality"],
            "total_task_weight": eval_result["total_task_weight"],
            "covered_quality_sum": round(covered_quality_sum, 4),
            "reward": round(reward_t, 4),
            "cost": round(cost_t, 4),
            "efficiency": round(efficiency_t, 4),
            "num_validation_tasks": len(validation_tasks),
            "member_count": membership_result["member_count"],
            "membership_fee_income": platform_result["membership_fee_income"],
            "bonus_payment": platform_result["bonus_payment"],
            "bonus_trigger_count": lgsc_result["bonus_trigger_count"],
            "platform_task_value": platform_result["platform_task_value"],
            "platform_payment": platform_result["platform_payment"],
            "platform_utility": platform_result["platform_utility"],
            "num_active_workers": current_active_workers,
            "num_left_workers_this_round": leave_result["num_left_workers_this_round"],
            "cumulative_left_workers": cumulative_left_workers,
            "avg_leave_probability": leave_result["avg_leave_probability"],
            "total_observations_before_round": total_observations_before_round,
            "total_observations_after_round": total_observations,
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
            f"member={round_result['member_count']} | "
            f"fee={round_result['membership_fee_income']:.2f} | "
            f"bonus={round_result['bonus_payment']:.2f} | "
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
    plot_metric(round_results, "avg_leave_probability", "Average Leave Probability", PLOT_LEAVE_PROB)

    plot_metric(round_results, "member_count", "Member Count", PLOT_MEMBER_COUNT)
    plot_metric(round_results, "membership_fee_income", "Membership Fee Income", PLOT_MEMBERSHIP_FEE_INCOME)
    plot_metric(round_results, "bonus_payment", "Bonus Payment", PLOT_BONUS_PAYMENT)

    print("全部完成")
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
