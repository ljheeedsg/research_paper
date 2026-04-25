from collections import defaultdict

import numpy as np

from experiment2_重构_CMAB算法 import CMABAlgorithm


def generate_validation_tasks_by_grid(available_workers, workers, task_grid_map, round_tasks, slot_id, top_m):
    available_ids = {worker["worker_id"] for worker in available_workers}
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
        key=lambda item: (-item["unknown_count"], -item["trusted_count"], item["grid_id"])
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


def update_trust_by_validation(validation_tasks, available_workers, workers, slot_id, config):
    trust_update_records = []
    available_ids = {worker["worker_id"] for worker in available_workers}

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

            if error <= float(config["ERROR_GOOD"]):
                new_trust = old_trust + float(config["ETA"])
            elif error <= float(config["ERROR_BAD"]):
                new_trust = old_trust
            else:
                new_trust = old_trust - float(config["ETA"])

            new_trust = max(0.0, min(1.0, new_trust))
            worker["trust"] = new_trust

            old_category = worker["category"]
            if new_trust >= float(config["THETA_HIGH"]):
                worker["category"] = "trusted"
            elif new_trust <= float(config["THETA_LOW"]):
                worker["category"] = "malicious"
                worker["is_member"] = False
            else:
                worker["category"] = "unknown"
                if worker.get("is_member"):
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


class TrustCMABAlgorithm(CMABAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "trust"
        self.loader_mode = "trust"
        self.selection_mode = "paper_style_cmab_plus_validation_longrun"

    def run_round(self, context):
        from experiment2_重构_CMAB算法 import greedy_select_workers

        selected_ids, total_cost, selection_details, est_quality_state = greedy_select_workers(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            round_tasks=context.round_tasks,
            total_observations=context.total_observations,
            budget=context.budget,
            config=self.config,
            exclude_malicious=True,
        )
        from experiment2_重构_算法数据结构 import AlgorithmDecision

        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=total_cost,
            selection_details=selection_details,
            estimated_state=est_quality_state,
            extra_info={},
        )

    def update(self, feedback):
        validation_tasks, validation_candidates = generate_validation_tasks_by_grid(
            available_workers=feedback["available_workers"],
            workers=feedback["workers"],
            task_grid_map=feedback["task_grid_map"],
            round_tasks=feedback["round_tasks"],
            slot_id=feedback["slot_id"],
            top_m=self.config["VALIDATION_TOP_M"],
        )
        trust_update_records = update_trust_by_validation(
            validation_tasks=validation_tasks,
            available_workers=feedback["available_workers"],
            workers=feedback["workers"],
            slot_id=feedback["slot_id"],
            config=self.config,
        )
        trusted_count, unknown_count, malicious_count = self._count_categories(feedback["workers"])
        return {
            "num_validation_tasks": len(validation_tasks),
            "validation_tasks": validation_tasks,
            "validation_candidates": validation_candidates,
            "trust_update_records": trust_update_records,
            "trusted_count": trusted_count,
            "unknown_count": unknown_count,
            "malicious_count": malicious_count,
        }

    @staticmethod
    def _count_categories(workers):
        trusted_count = 0
        unknown_count = 0
        malicious_count = 0
        for worker in workers.values():
            if worker["category"] == "trusted":
                trusted_count += 1
            elif worker["category"] == "unknown":
                unknown_count += 1
            elif worker["category"] == "malicious":
                malicious_count += 1
        return trusted_count, unknown_count, malicious_count
