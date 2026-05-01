from experiment2_重构_PGRD算法 import PGRDAlgorithm


def update_lgsc_state(selected_worker_ids, workers, slot_id, config, bid_tasks_map=None):
    bonus_payment_t = 0.0
    bonus_trigger_count = 0
    bonus_reward_map = {}
    lgsc_records = []

    selected_set = set(selected_worker_ids)

    for worker_id in selected_set:
        worker = workers[worker_id]
        if not worker["is_member"]:
            worker["current_sunk_loss"] = (
                float(config["MEMBER_BONUS"]) / float(config["SUNK_THRESHOLD"])
            ) * worker["sunk_value"]
            continue

        task_ids = (
            bid_tasks_map.get(worker_id, [])
            if bid_tasks_map is not None else worker["tasks_by_slot"].get(slot_id, [])
        )
        if not task_ids:
            worker["current_sunk_loss"] = (
                float(config["MEMBER_BONUS"]) / float(config["SUNK_THRESHOLD"])
            ) * worker["sunk_value"]
            continue

        round_cost_sum = 0.0
        for _ in task_ids:
            round_cost_sum += float(config["WORKER_COST_RATIO"]) * float(worker["bid_price"])

        worker["sunk_value"] += worker["sunk_rate"] * round_cost_sum
        worker["period_cost_sum"] += round_cost_sum

        bonus_triggered = False
        bonus_paid = 0.0

        if worker["sunk_value"] >= float(config["SUNK_THRESHOLD"]):
            bonus_paid = float(config["MEMBER_BONUS"])
            worker["cumulative_bonus"] += bonus_paid
            worker["bonus_count"] += 1

            g_i = worker["bonus_count"]
            c_last = max(worker["period_cost_sum"], 1e-8)
            worker["sunk_rate"] = 1.0 + (
                float(config["MEMBER_BONUS"]) * g_i
            ) / (float(config["MEMBER_BONUS"]) * g_i + c_last)

            worker["sunk_value"] = 0.0
            worker["period_cost_sum"] = 0.0
            bonus_payment_t += bonus_paid
            bonus_trigger_count += 1
            bonus_triggered = True
            bonus_reward_map[worker_id] = bonus_reward_map.get(worker_id, 0.0) + bonus_paid

        worker["current_sunk_loss"] = (
            float(config["MEMBER_BONUS"]) / float(config["SUNK_THRESHOLD"])
        ) * worker["sunk_value"]

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
        "bonus_reward_map": {worker_id: round(amount, 4) for worker_id, amount in bonus_reward_map.items()},
        "lgsc_records": lgsc_records,
    }


class LGSCAlgorithm(PGRDAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "lgsc"
        self.loader_mode = "lgsc"
        self.selection_mode = "paper_style_cmab_plus_validation_plus_pgrd_plus_lgsc"

    def update(self, feedback):
        update_result = super().update(feedback)
        lgsc_result = update_lgsc_state(
            selected_worker_ids=feedback["selected_worker_ids"],
            workers=feedback["workers"],
            slot_id=feedback["slot_id"],
            bid_tasks_map=feedback.get("bid_tasks_map"),
            config=self.config,
        )
        update_result.update(lgsc_result)
        return update_result
