from collections import defaultdict

import numpy as np

from experiment2_重构_CMAB算法 import CMABAlgorithm


def generate_validation_tasks_by_grid(
    available_workers,
    workers,
    task_grid_map,
    eval_result,
    slot_id,
    top_m,
):
    available_ids = {worker["worker_id"] for worker in available_workers}
    real_task_results = [
        item
        for item in eval_result.get("task_results", [])
        if item.get("covered") or item.get("executed_by")
    ]
    round_task_ids = {item["task_id"] for item in real_task_results}
    task_result_map = {
        item["task_id"]: item
        for item in real_task_results
    }

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
        task_result = task_result_map.get(chosen_task, {})
        validation_tasks.append({
            "task_id": chosen_task,
            "grid_id": item["grid_id"],
            "trusted_count": item["trusted_count"],
            "unknown_count": item["unknown_count"],
            "executed_by": list(task_result.get("executed_by", [])),
            "covered": bool(task_result.get("covered", False)),
        })

    return validation_tasks, candidate_grids


def _collect_validation_worker_ids(
    task_id,
    executed_worker_ids,
    available_workers,
    workers,
    slot_id,
    max_count,
    category,
):
    executed_set = {worker_id for worker_id in executed_worker_ids}
    available_ids = {worker["worker_id"] for worker in available_workers}

    reused_ids = []
    extra_ids = []

    for worker_id in sorted(executed_set):
        if worker_id not in available_ids:
            continue
        worker = workers.get(worker_id)
        if worker is None:
            continue
        if worker.get("category") != category:
            continue
        if task_id not in worker["tasks_by_slot"].get(slot_id, []):
            continue
        if task_id not in worker["task_map"]:
            continue
        reused_ids.append(worker_id)
        if len(reused_ids) >= max_count:
            return reused_ids, extra_ids

    for worker in sorted(available_workers, key=lambda item: item["worker_id"]):
        worker_id = worker["worker_id"]
        if worker_id in executed_set:
            continue
        if worker.get("category") != category:
            continue
        if task_id not in worker["tasks_by_slot"].get(slot_id, []):
            continue
        if task_id not in worker["task_map"]:
            continue
        extra_ids.append(worker_id)
        if len(reused_ids) + len(extra_ids) >= max_count:
            break

    return reused_ids, extra_ids


def update_trust_by_validation(validation_tasks, available_workers, workers, slot_id, config):
    trust_update_records = []
    validation_task_records = []
    total_ref_reports = 0
    total_unknown_reports = 0
    total_reused_reports = 0
    total_extra_reports = 0

    for item in validation_tasks:
        task_id = item["task_id"]
        executed_worker_ids = item.get("executed_by", [])
        max_ref = int(config.get("MAX_REF_WORKERS_PER_VALIDATION", 3))
        max_unknown = int(config.get("MAX_UNKNOWN_WORKERS_PER_VALIDATION", 5))

        reused_ref_ids, extra_ref_ids = _collect_validation_worker_ids(
            task_id=task_id,
            executed_worker_ids=executed_worker_ids,
            available_workers=available_workers,
            workers=workers,
            slot_id=slot_id,
            max_count=max_ref,
            category="trusted",
        )
        reused_unknown_ids, extra_unknown_ids = _collect_validation_worker_ids(
            task_id=task_id,
            executed_worker_ids=executed_worker_ids,
            available_workers=available_workers,
            workers=workers,
            slot_id=slot_id,
            max_count=max_unknown,
            category="unknown",
        )

        trusted_workers = reused_ref_ids + extra_ref_ids
        unknown_workers = reused_unknown_ids + extra_unknown_ids

        if not trusted_workers or not unknown_workers:
            validation_task_records.append({
                "task_id": task_id,
                "grid_id": item.get("grid_id"),
                "covered": bool(item.get("covered", False)),
                "executed_by": list(executed_worker_ids),
                "ref_worker_ids": [],
                "unknown_worker_ids": [],
                "num_ref_reports": 0,
                "num_unknown_reports": 0,
                "num_validation_reports": 0,
                "num_reused_validation_reports": 0,
                "num_extra_validation_reports": 0,
                "skipped": True,
            })
            continue

        trusted_data = [
            float(workers[worker_id]["task_map"][task_id]["task_data"])
            for worker_id in trusted_workers
        ]

        base_v = float(np.median(trusted_data))
        reused_report_count = len(reused_ref_ids) + len(reused_unknown_ids)
        extra_report_count = len(extra_ref_ids) + len(extra_unknown_ids)
        total_report_count = len(trusted_workers) + len(unknown_workers)

        total_ref_reports += len(trusted_workers)
        total_unknown_reports += len(unknown_workers)
        total_reused_reports += reused_report_count
        total_extra_reports += extra_report_count

        validation_task_records.append({
            "task_id": task_id,
            "grid_id": item.get("grid_id"),
            "covered": bool(item.get("covered", False)),
            "executed_by": list(executed_worker_ids),
            "ref_worker_ids": trusted_workers,
            "unknown_worker_ids": unknown_workers,
            "reused_ref_worker_ids": reused_ref_ids,
            "extra_ref_worker_ids": extra_ref_ids,
            "reused_unknown_worker_ids": reused_unknown_ids,
            "extra_unknown_worker_ids": extra_unknown_ids,
            "num_ref_reports": len(trusted_workers),
            "num_unknown_reports": len(unknown_workers),
            "num_validation_reports": total_report_count,
            "num_reused_validation_reports": reused_report_count,
            "num_extra_validation_reports": extra_report_count,
            "skipped": False,
        })

        for worker_id in unknown_workers:
            worker = workers[worker_id]

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
                "report_source": (
                    "reused" if worker_id in reused_unknown_ids else "extra"
                ),
            })

    return {
        "trust_update_records": trust_update_records,
        "validation_tasks": validation_task_records,
        "num_ref_reports": total_ref_reports,
        "num_unknown_reports": total_unknown_reports,
        "num_reused_validation_reports": total_reused_reports,
        "num_extra_validation_reports": total_extra_reports,
        "num_validation_reports": total_ref_reports + total_unknown_reports,
        "validation_cost": round(
            float(config.get("VALIDATION_REPORT_COST", 0.0)) * total_extra_reports,
            4,
        ),
    }


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
            eval_result=feedback["eval_result"],
            slot_id=feedback["slot_id"],
            top_m=self.config["VALIDATION_TOP_M"],
        )
        validation_result = update_trust_by_validation(
            validation_tasks=validation_tasks,
            available_workers=feedback["available_workers"],
            workers=feedback["workers"],
            slot_id=feedback["slot_id"],
            config=self.config,
        )
        trusted_count, unknown_count, malicious_count = self._count_categories(feedback["workers"])
        return {
            "num_validation_tasks": len(validation_tasks),
            "validation_tasks": validation_result["validation_tasks"],
            "validation_candidates": validation_candidates,
            "trust_update_records": validation_result["trust_update_records"],
            "validation_cost": validation_result["validation_cost"],
            "num_validation_reports": validation_result["num_validation_reports"],
            "num_reused_validation_reports": validation_result["num_reused_validation_reports"],
            "num_extra_validation_reports": validation_result["num_extra_validation_reports"],
            "num_ref_reports": validation_result["num_ref_reports"],
            "num_unknown_reports": validation_result["num_unknown_reports"],
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
