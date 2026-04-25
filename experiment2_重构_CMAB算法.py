import math

from experiment2_重构_算法基类 import BaseAlgorithm
from experiment2_重构_算法数据结构 import AlgorithmDecision


def compute_ucb(worker, total_observations, config):
    if worker["n_obs"] <= 0:
        return float(config["DEFAULT_INIT_UCB"])

    total_learned_counts = max(2, total_observations)
    explore = math.sqrt((int(config["K"]) + 1) * math.log(total_learned_counts) / worker["n_obs"])
    return min(1.0, float(worker["avg_quality"]) + explore)


def compute_worker_marginal_gain(
    worker,
    slot_id,
    round_task_ids,
    current_best_quality,
    total_observations,
    config,
    bid_tasks_map=None,
):
    candidate_bid_tasks = (
        bid_tasks_map.get(worker["worker_id"], [])
        if bid_tasks_map is not None else worker["tasks_by_slot"].get(slot_id, [])
    )
    bid_task_ids = [task_id for task_id in candidate_bid_tasks if task_id in round_task_ids]
    if not bid_task_ids:
        return None

    q_hat = compute_ucb(worker, total_observations, config)
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
        "trust": round(float(worker.get("trust", 0.0)), 4),
        "category": worker.get("category", "base"),
    }


def greedy_select_workers(
    available_workers,
    slot_id,
    round_tasks,
    total_observations,
    budget,
    config,
    bid_tasks_map=None,
    exclude_malicious=False,
):
    round_task_ids = {task["task_id"] for task in round_tasks}
    if exclude_malicious:
        remaining_workers = {
            worker["worker_id"]: worker
            for worker in available_workers
            if worker.get("category") != "malicious"
        }
    else:
        remaining_workers = {worker["worker_id"]: worker for worker in available_workers}

    current_best_quality = {task_id: 0.0 for task_id in round_task_ids}
    selected_ids = []
    selection_details = []
    total_cost = 0.0

    while remaining_workers and len(selected_ids) < int(config["K"]):
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
                config=config,
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


class CMABAlgorithm(BaseAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "cmab"
        self.loader_mode = "base"
        self.selection_mode = "paper_style_cmab_marginal_gain_over_bid_price_longrun"

    def run_round(self, context):
        selected_ids, total_cost, selection_details, est_quality_state = greedy_select_workers(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            round_tasks=context.round_tasks,
            total_observations=context.total_observations,
            budget=context.budget,
            config=self.config,
        )
        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=total_cost,
            selection_details=selection_details,
            estimated_state=est_quality_state,
            extra_info={},
        )
