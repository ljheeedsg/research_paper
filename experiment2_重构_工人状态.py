import math
import random

import numpy as np


def sigmoid(x: float) -> float:
    x = max(-20.0, min(20.0, x))
    return 1.0 / (1.0 + math.exp(-x))


def get_available_workers(workers, slot_id):
    return [
        worker
        for worker in workers.values()
        if slot_id in worker["available_slots"] and worker["is_active"]
    ]


def update_worker_statistics(selected_worker_ids, workers, slot_id, config, bid_tasks_map=None):
    total_new_observations = 0
    round_level_quality_update = bool(config.get("ROUND_LEVEL_QUALITY_UPDATE", False))

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

        if round_level_quality_update:
            round_avg_quality = sum(qualities) / len(qualities)
            new_n = old_n + 1
            new_avg = ((old_n * old_avg) + round_avg_quality) / new_n
            total_new_observations += 1
        else:
            new_obs = len(qualities)
            new_total_quality = old_n * old_avg + sum(qualities)
            new_n = old_n + new_obs
            new_avg = new_total_quality / new_n
            total_new_observations += new_obs

        worker["n_obs"] = new_n
        worker["avg_quality"] = float(new_avg)

    return total_new_observations


def update_worker_reward_cost(selected_worker_ids, workers, worker_cost_ratio):
    selected_set = set(selected_worker_ids)

    for worker_id, worker in workers.items():
        if worker_id in selected_set:
            reward_t = float(worker["bid_price"])
            cost_t = worker_cost_ratio * reward_t
            worker["recent_reward"] = reward_t
            worker["cumulative_reward"] += reward_t
            worker["cumulative_cost"] += cost_t
            worker["selected_rounds"] += 1
        else:
            worker["recent_reward"] = 0.0


def update_worker_leave_state(workers, round_id, selected_worker_ids, config, mode):
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

        if mode == "lgsc":
            member_flag = 1 if worker.get("is_member", False) else 0
            sunk_threshold = max(float(config.get("SUNK_THRESHOLD", 1.0)), 1e-8)
            sunk_progress = float(worker.get("sunk_value", 0.0)) / sunk_threshold
            leave_probability = sigmoid(
                float(config["BETA0"])
                + float(config["BETA1"]) * float(worker["cumulative_cost"])
                - float(config["BETA2"]) * float(avg_reward)
                - float(config.get("BETA3", 0.0)) * member_flag
                - float(config.get("BETA4", 0.0)) * sunk_progress
            )
        else:
            leave_probability = sigmoid(
                float(config["BETA0"])
                + float(config["BETA1"]) * float(worker["cumulative_cost"])
                - float(config["BETA2"]) * float(avg_reward)
            )

        worker["leave_probability"] = float(leave_probability)
        leave_probabilities.append(float(leave_probability))

        if random.random() < leave_probability:
            worker["is_active"] = False
            worker["left_round_id"] = round_id
            if "is_member" in worker:
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
