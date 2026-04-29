import math

from experiment2_重构_算法基类 import BaseAlgorithm
from experiment2_重构_算法数据结构 import AlgorithmDecision


def compute_ucb(worker, total_observations, config):
    if worker["n_obs"] <= 0:
        return float(config["DEFAULT_INIT_UCB"])

    total_learned_counts = max(2, total_observations)
    alpha = float(config.get("UCB_EXPLORATION_ALPHA", 1.0))
    explore = alpha * math.sqrt(
        (int(config["K"]) + 1) * math.log(total_learned_counts) / worker["n_obs"]
    )
    return min(1.0, float(worker["avg_quality"]) + explore)


def compute_effective_quality(worker, q_hat, config):
    if worker["n_obs"] <= 0:
        return min(1.0, float(config["DEFAULT_INIT_UCB"]))

    delta_cap = float(config.get("UCB_STATE_DELTA_CAP", 1.0))
    conservative_q = float(worker["avg_quality"]) + delta_cap
    return min(1.0, min(float(q_hat), conservative_q))


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
    effective_q = compute_effective_quality(worker, q_hat, config)
    marginal_gain = 0.0
    marginal_details = []

    for task_id in bid_task_ids:
        task = worker["task_map"][task_id]
        weight = float(task["weight"])
        prev_best = float(current_best_quality.get(task_id, 0.0))
        delta_quality = max(0.0, effective_q - prev_best)
        weighted_gain = weight * delta_quality

        if weighted_gain > 0:
            marginal_gain += weighted_gain
            marginal_details.append({
                "task_id": task_id,
                "weight": weight,
                "prev_best_quality": round(prev_best, 4),
                "estimated_quality": round(q_hat, 4),
                "effective_quality": round(effective_q, 4),
                "delta_quality": round(delta_quality, 4),
                "weighted_gain": round(weighted_gain, 4),
            })

    cost = float(worker["bid_price"])
    base_score = (marginal_gain / cost) if (marginal_gain > 0 and cost > 0) else 0.0
    quality_bonus = float(config.get("QUALITY_SCORE_LAMBDA", 0.0)) * float(worker["avg_quality"])
    uncertainty_penalty = float(config.get("UNCERTAINTY_PENALTY_MU", 0.0)) / math.sqrt(
        float(worker["n_obs"]) + 1.0
    )
    was_selected_last_round = float(worker.get("recent_reward", 0.0)) > 0.0
    stability_bonus = float(config.get("STABILITY_BONUS_GAMMA", 0.0)) if was_selected_last_round else 0.0

    cold_start_penalty = 0.0
    if worker["n_obs"] <= 0:
        cold_start_penalty = float(config.get("COLD_START_PENALTY_ZERO", 0.0))
    elif worker["n_obs"] < int(config.get("COLD_START_MIN_OBS", 0)):
        cold_start_penalty = float(config.get("COLD_START_PENALTY_FEW", 0.0))

    final_score = (
        base_score
        + quality_bonus
        + stability_bonus
        - uncertainty_penalty
        - cold_start_penalty
    )

    return {
        "worker_id": worker["worker_id"],
        "bid_price": round(cost, 4),
        "q_hat": round(q_hat, 4),
        "effective_q": round(effective_q, 4),
        "bid_task_ids": bid_task_ids,
        "marginal_task_count": len(marginal_details),
        "marginal_gain": round(marginal_gain, 4),
        "score": round(base_score, 6),
        "quality_bonus": round(quality_bonus, 6),
        "stability_bonus": round(stability_bonus, 6),
        "uncertainty_penalty": round(uncertainty_penalty, 6),
        "cold_start_penalty": round(cold_start_penalty, 6),
        "final_score": round(final_score, 6),
        "was_selected_last_round": was_selected_last_round,
        "is_new_worker": worker["n_obs"] <= 0,
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
    new_worker_count = 0
    max_new_workers = int(config.get("MAX_NEW_WORKERS_PER_ROUND", int(config["K"])))

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

        observed_candidates = [item for item in candidates if not item["is_new_worker"]]
        if observed_candidates and new_worker_count >= max_new_workers:
            candidates = observed_candidates

        candidates.sort(
            key=lambda item: (
                -item["final_score"],
                -item["marginal_gain"],
                -item["marginal_task_count"],
                item["bid_price"],
                item["worker_id"],
            )
        )
        best = candidates[0]
        selected_ids.append(best["worker_id"])
        total_cost += best["bid_price"]
        if best["is_new_worker"]:
            new_worker_count += 1

        for task_id in best["bid_task_ids"]:
            current_best_quality[task_id] = max(
                current_best_quality.get(task_id, 0.0),
                float(best["effective_q"]),
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
