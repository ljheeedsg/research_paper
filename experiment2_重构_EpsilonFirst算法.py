import random

from experiment2_重构_算法基类 import BaseAlgorithm
from experiment2_重构_算法数据结构 import AlgorithmDecision


def estimate_mean_quality(worker):
    if worker["n_obs"] <= 0:
        return 0.0
    return float(worker["avg_quality"])


def compute_worker_mean_gain(
    worker,
    slot_id,
    round_task_ids,
    current_best_quality,
    bid_tasks_map=None,
):
    candidate_bid_tasks = (
        bid_tasks_map.get(worker["worker_id"], [])
        if bid_tasks_map is not None else worker["tasks_by_slot"].get(slot_id, [])
    )
    bid_task_ids = [task_id for task_id in candidate_bid_tasks if task_id in round_task_ids]
    if not bid_task_ids:
        return None

    q_hat = estimate_mean_quality(worker)
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
        "category": worker.get("category", "base"),
    }


def random_select_workers(available_workers, slot_id, round_tasks, budget, config):
    round_task_ids = {task["task_id"] for task in round_tasks}
    candidates = []

    for worker in available_workers:
        bid_task_ids = [
            task_id
            for task_id in worker["tasks_by_slot"].get(slot_id, [])
            if task_id in round_task_ids
        ]
        if not bid_task_ids:
            continue

        candidates.append({
            "worker_id": worker["worker_id"],
            "bid_price": float(worker["bid_price"]),
            "bid_task_ids": bid_task_ids,
        })

    selected_ids = []
    selection_details = []
    total_cost = 0.0

    while candidates and len(selected_ids) < int(config["K"]):
        remaining_budget = budget - total_cost
        feasible = [
            candidate for candidate in candidates
            if candidate["bid_price"] <= remaining_budget
        ]

        if not feasible:
            break

        chosen = random.choice(feasible)
        selected_ids.append(chosen["worker_id"])
        total_cost += chosen["bid_price"]

        selection_details.append({
            "worker_id": chosen["worker_id"],
            "bid_price": round(chosen["bid_price"], 4),
            "bid_task_ids": chosen["bid_task_ids"],
            "selection_order": len(selected_ids),
            "remaining_budget_after_selection": round(budget - total_cost, 4),
            "stage": "explore",
        })

        candidates = [
            candidate for candidate in candidates
            if candidate["worker_id"] != chosen["worker_id"]
        ]

    return selected_ids, round(total_cost, 4), selection_details, {}


def greedy_mean_select_workers(available_workers, slot_id, round_tasks, budget, config, bid_tasks_map=None):
    round_task_ids = {task["task_id"] for task in round_tasks}
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

            candidate = compute_worker_mean_gain(
                worker=worker,
                slot_id=slot_id,
                round_task_ids=round_task_ids,
                current_best_quality=current_best_quality,
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
        best["stage"] = "exploit"
        selection_details.append(best)

        remaining_workers.pop(best["worker_id"], None)

    return selected_ids, round(total_cost, 4), selection_details, current_best_quality


class EpsilonFirstAlgorithm(BaseAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "epsilon_first"
        self.loader_mode = "base"
        self.selection_mode = "epsilon_first_random_then_mean_greedy"

    def run_round(self, context):
        total_slots = int(self.config["TOTAL_SLOTS"])
        ratio = float(self.config.get("EPSILON_FIRST_RATIO", 0.2))
        explore_rounds = max(1, int(round(total_slots * ratio)))

        if context.round_id <= explore_rounds:
            selected_ids, total_cost, selection_details, estimated_state = random_select_workers(
                available_workers=context.available_workers,
                slot_id=context.slot_id,
                round_tasks=context.round_tasks,
                budget=context.budget,
                config=self.config,
            )
            stage = "explore"
        else:
            selected_ids, total_cost, selection_details, estimated_state = greedy_mean_select_workers(
                available_workers=context.available_workers,
                slot_id=context.slot_id,
                round_tasks=context.round_tasks,
                budget=context.budget,
                config=self.config,
            )
            stage = "exploit"

        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=total_cost,
            selection_details=selection_details,
            estimated_state=estimated_state,
            extra_info={
                "algorithm": "epsilon_first",
                "epsilon_first_stage": stage,
                "epsilon_first_explore_rounds": explore_rounds,
            },
        )