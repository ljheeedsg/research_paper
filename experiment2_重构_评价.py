from collections import defaultdict
import math

import numpy as np


def quality_value(q, r_max=10.0, k=10.0, q0=0.6):
    q = max(0.0, min(1.0, float(q)))
    return float(r_max) * (2.0 / (1.0 + math.exp(-float(k) * (q - float(q0)))) - 1.0)


def evaluate_round(
    selected_worker_ids,
    workers,
    round_tasks,
    slot_id,
    delta,
    bid_tasks_map=None,
    rho=10.0,
    quality_value_r_max=10.0,
    quality_value_k=10.0,
    quality_value_q0=0.6,
):
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

        # 主统计口径使用任务内平均质量，best_quality 仅作为辅助分析字段保留。
        weighted_gain = weight * avg_quality
        weighted_completion_quality += weighted_gain
        platform_value = weight * quality_value(
            avg_quality,
            r_max=quality_value_r_max,
            k=quality_value_k,
            q0=quality_value_q0,
        )

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
        weighted_completion_quality / total_weight if total_weight > 0 else 0.0
    )
    covered_qualities = [tr["avg_quality"] for tr in task_results if tr["covered"]]
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


def compute_platform_utility(
    eval_result,
    selected_worker_ids,
    workers,
    membership_fee_income=0.0,
    bonus_payment=0.0,
    validation_cost=0.0,
):
    platform_task_value = sum(
        float(task_result["platform_value"])
        for task_result in eval_result["task_results"]
    )
    platform_payment = sum(
        float(workers[worker_id]["bid_price"])
        for worker_id in selected_worker_ids
    )
    total_platform_cost = platform_payment + bonus_payment + validation_cost
    net_platform_cost = total_platform_cost - membership_fee_income
    platform_utility = (
        platform_task_value
        + membership_fee_income
        - platform_payment
        - bonus_payment
        - validation_cost
    )

    return {
        "platform_task_value": round(platform_task_value, 4),
        "platform_payment": round(platform_payment, 4),
        "membership_fee_income": round(membership_fee_income, 4),
        "bonus_payment": round(bonus_payment, 4),
        "validation_cost": round(validation_cost, 4),
        "total_platform_cost": round(total_platform_cost, 4),
        "net_platform_cost": round(net_platform_cost, 4),
        "platform_utility": round(platform_utility, 4),
    }


def update_cumulative_metrics(round_result, cumulative_state):
    covered_task_results = [
        task_result for task_result in round_result["task_results"] if task_result["covered"]
    ]

    cumulative_state["num_tasks"] += round_result["num_tasks"]
    cumulative_state["num_covered"] += round_result["num_covered"]
    cumulative_state["num_completed"] += round_result["num_completed"]
    cumulative_state["task_weight_sum"] += round_result["total_task_weight"]
    cumulative_state["weighted_completion_quality_sum"] += round_result["weighted_completion_quality"]
    cumulative_state["quality_sum"] += sum(
        float(task_result["avg_quality"]) for task_result in covered_task_results
    )
    cumulative_state["quality_count"] += len(covered_task_results)
    cumulative_state["platform_task_value_sum"] += round_result["platform_task_value"]
    cumulative_state["platform_payment_sum"] += round_result["platform_payment"]
    cumulative_state["membership_fee_income_sum"] += round_result.get("membership_fee_income", 0.0)
    cumulative_state["bonus_payment_sum"] += round_result.get("bonus_payment", 0.0)
    cumulative_state["validation_cost_sum"] += round_result.get("validation_cost", 0.0)
    cumulative_state["total_platform_cost_sum"] += round_result.get("total_platform_cost", 0.0)
    cumulative_state["net_platform_cost_sum"] += round_result.get("net_platform_cost", 0.0)
    cumulative_state["validation_reports_sum"] += round_result.get("num_validation_reports", 0)
    cumulative_state["extra_validation_reports_sum"] += round_result.get("num_extra_validation_reports", 0)
    cumulative_state["reused_validation_reports_sum"] += round_result.get("num_reused_validation_reports", 0)
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
    round_result["cumulative_platform_task_value"] = round(
        cumulative_state["platform_task_value_sum"], 4
    )
    round_result["cumulative_platform_payment"] = round(
        cumulative_state["platform_payment_sum"], 4
    )
    round_result["cumulative_membership_fee_income"] = round(
        cumulative_state["membership_fee_income_sum"], 4
    )
    round_result["cumulative_bonus_payment"] = round(
        cumulative_state["bonus_payment_sum"], 4
    )
    round_result["cumulative_validation_cost"] = round(
        cumulative_state["validation_cost_sum"], 4
    )
    round_result["cumulative_total_platform_cost"] = round(
        cumulative_state["total_platform_cost_sum"], 4
    )
    round_result["cumulative_net_platform_cost"] = round(
        cumulative_state["net_platform_cost_sum"], 4
    )
    round_result["cumulative_validation_reports"] = cumulative_state["validation_reports_sum"]
    round_result["cumulative_extra_validation_reports"] = (
        cumulative_state["extra_validation_reports_sum"]
    )
    round_result["cumulative_reused_validation_reports"] = (
        cumulative_state["reused_validation_reports_sum"]
    )
    round_result["cumulative_platform_utility"] = round(
        cumulative_state["platform_utility_sum"], 4
    )
