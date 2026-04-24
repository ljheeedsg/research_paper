import random

from experiment2_重构_算法基类 import BaseAlgorithm
from experiment2_重构_算法数据结构 import AlgorithmDecision


class RandomAlgorithm(BaseAlgorithm):
    """
    随机招募算法子类。

    职责：
    在每一轮中，从当前可用工人中随机选择工人，
    同时满足预算约束和最大选择人数 K。
    """

    def __init__(self, config):
        super().__init__(config)
        self.name = "random"
        self.loader_mode = "base"
        self.selection_mode = "random"

    def run_round(self, context):
        k = self.config["K"]
        budget = context.budget

        candidates = []

        for worker in context.available_workers:
            bid_task_ids = worker["tasks_by_slot"].get(context.slot_id, [])

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

        while candidates and len(selected_ids) < k:
            remaining_budget = budget - total_cost

            feasible_candidates = [
                candidate
                for candidate in candidates
                if candidate["bid_price"] <= remaining_budget
            ]

            if not feasible_candidates:
                break

            chosen = random.choice(feasible_candidates)

            selected_ids.append(chosen["worker_id"])
            total_cost += chosen["bid_price"]

            chosen_detail = {
                "worker_id": chosen["worker_id"],
                "bid_price": round(chosen["bid_price"], 4),
                "bid_task_ids": chosen["bid_task_ids"],
                "selection_order": len(selected_ids),
                "remaining_budget_after_selection": round(budget - total_cost, 4),
            }

            selection_details.append(chosen_detail)

            candidates = [
                candidate
                for candidate in candidates
                if candidate["worker_id"] != chosen["worker_id"]
            ]

        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=round(total_cost, 4),
            selection_details=selection_details,
            estimated_state={},
            extra_info={
                "algorithm": "random"
            },
        )
