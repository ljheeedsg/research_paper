from experiment2_重构_工人状态 import (
    get_available_workers,
    update_active_rounds,
    update_worker_bonus_rewards,
    update_worker_leave_state,
    update_worker_reward_cost,
    update_worker_statistics,
)
from experiment2_重构_算法数据结构 import RoundContext
from experiment2_重构_评价 import compute_platform_utility, evaluate_round, update_cumulative_metrics


class Simulator:
    def __init__(self, workers, tasks_by_slot, task_grid_map, algorithm, config):
        self.workers = workers
        self.tasks_by_slot = tasks_by_slot
        self.task_grid_map = task_grid_map
        self.algorithm = algorithm
        self.config = config

    def run(self):
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

        for slot_id in range(self.config["TOTAL_SLOTS"]):
            round_id = slot_id + 1
            round_tasks = self.tasks_by_slot.get(slot_id, [])

            if self.config["SKIP_EMPTY_ROUNDS"] and not round_tasks:
                continue

            available_workers = get_available_workers(self.workers, slot_id)
            update_active_rounds(available_workers)

            context = RoundContext(
                round_id=round_id,
                slot_id=slot_id,
                available_workers=available_workers,
                round_tasks=round_tasks,
                workers=self.workers,
                total_observations=total_observations,
                budget=self.config["PER_ROUND_BUDGET"],
                task_grid_map=self.task_grid_map,
                config=self.config,
            )

            decision = self.algorithm.run_round(context)
            bid_tasks_map = decision.extra_info.get("bid_tasks_map")

            eval_result = evaluate_round(
                selected_worker_ids=decision.selected_worker_ids,
                workers=self.workers,
                round_tasks=round_tasks,
                slot_id=slot_id,
                delta=self.config["DELTA"],
                bid_tasks_map=bid_tasks_map,
                rho=self.config["RHO"],
                quality_value_r_max=self.config["QUALITY_VALUE_R_MAX"],
                quality_value_k=self.config["QUALITY_VALUE_K"],
                quality_value_q0=self.config["QUALITY_VALUE_Q0"],
            )

            reward_t = eval_result["weighted_completion_quality"]
            efficiency_t = (reward_t / decision.cost) if decision.cost > 0 else 0.0
            update_worker_reward_cost(
                decision.selected_worker_ids,
                self.workers,
                self.config["WORKER_COST_RATIO"],
                mode=self.algorithm.loader_mode,
                config=self.config,
                bid_tasks_map=bid_tasks_map,
                member_task_ids=decision.extra_info.get("member_task_ids"),
            )

            feedback = {
                "round_id": round_id,
                "slot_id": slot_id,
                "workers": self.workers,
                "available_workers": available_workers,
                "round_tasks": round_tasks,
                "task_grid_map": self.task_grid_map,
                "selected_worker_ids": decision.selected_worker_ids,
                "bid_tasks_map": bid_tasks_map,
                "eval_result": eval_result,
                "decision": decision,
            }
            algorithm_update = self.algorithm.update(feedback) or {}
            update_worker_bonus_rewards(
                self.workers,
                algorithm_update.get("bonus_reward_map", {}),
            )

            platform_result = compute_platform_utility(
                eval_result=eval_result,
                selected_worker_ids=decision.selected_worker_ids,
                workers=self.workers,
                membership_fee_income=decision.extra_info.get("membership_fee_income", 0.0),
                bonus_payment=algorithm_update.get("bonus_payment", 0.0),
            )
            leave_result = update_worker_leave_state(
                workers=self.workers,
                round_id=round_id,
                selected_worker_ids=decision.selected_worker_ids,
                config=self.config,
                mode=self.algorithm.loader_mode,
            )

            total_observations_before_round = total_observations
            total_observations += update_worker_statistics(
                decision.selected_worker_ids,
                self.workers,
                slot_id,
                self.config,
                bid_tasks_map=bid_tasks_map,
            )

            cumulative_left_workers = sum(
                1 for worker in self.workers.values() if not worker["is_active"]
            )

            round_result = {
                "round_id": round_id,
                "slot_id": slot_id,
                "selection_mode": self.algorithm.selection_mode,
                "num_available_workers": len(available_workers),
                "num_selected_workers": len(decision.selected_worker_ids),
                "selected_workers": decision.selected_worker_ids,
                "selection_details": decision.selection_details,
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
                "cost": round(decision.cost, 4),
                "efficiency": round(efficiency_t, 4),
                "covered_tasks": eval_result["covered_tasks"],
                "completed_tasks": eval_result["completed_tasks"],
                "uncompleted_tasks": eval_result["uncompleted_tasks"],
                "task_results": eval_result["task_results"],
                "platform_task_value": platform_result["platform_task_value"],
                "platform_payment": platform_result["platform_payment"],
                "platform_utility": platform_result["platform_utility"],
                "num_left_workers_this_round": leave_result["num_left_workers_this_round"],
                "left_worker_ids_this_round": leave_result["left_worker_ids"],
                "cumulative_left_workers": cumulative_left_workers,
                "total_observations_before_round": total_observations_before_round,
                "total_observations_after_round": total_observations,
            }

            if decision.estimated_state:
                round_result["estimated_best_quality_state"] = decision.estimated_state
            if self.algorithm.loader_mode in {"pgrd", "lgsc"}:
                round_result["membership_fee_income"] = platform_result["membership_fee_income"]
            if self.algorithm.loader_mode == "lgsc":
                round_result["bonus_payment"] = platform_result["bonus_payment"]

            round_result.update(decision.extra_info)
            round_result.update(algorithm_update)

            update_cumulative_metrics(round_result, cumulative_state)
            round_results.append(round_result)
            self._print_round(round_result)

        return round_results

    def _print_round(self, round_result):
        print(
            f"[Round {round_result['round_id']:03d}] "
            f"tasks={round_result['num_tasks']} | "
            f"selected={round_result['num_selected_workers']} | "
            f"coverage={round_result['coverage_rate']:.4f} | "
            f"completion={round_result['completion_rate']:.4f} | "
            f"avg_quality={round_result['avg_quality']:.4f} | "
            f"platform_utility={round_result['platform_utility']:.2f} | "
            f"left_this_round={round_result['num_left_workers_this_round']} | "
            f"cum_utility={round_result['cumulative_platform_utility']:.2f}"
        )
