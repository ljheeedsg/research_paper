import importlib.util
from pathlib import Path

from experiment2_重构_Trust算法 import TrustCMABAlgorithm
from experiment2_重构_算法数据结构 import AlgorithmDecision


def _load_legacy_module(filename, module_name):
    module_path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_legacy_pgrd = _load_legacy_module(
    "experiment2_第6步加入PGRD_重构前备份.py",
    "experiment2_legacy_pgrd",
)


class PGRDAlgorithm(TrustCMABAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "pgrd"
        self.loader_mode = "pgrd"
        self.selection_mode = "paper_style_cmab_plus_validation_plus_pgrd"

    def run_round(self, context):
        for worker in context.workers.values():
            worker["is_member"] = False
            worker["membership_probability"] = 0.0

        member_task_ids, normal_task_ids = _legacy_pgrd.split_member_and_normal_tasks(
            context.round_tasks
        )
        membership_result = _legacy_pgrd.update_membership_by_pgrd(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            member_task_ids=member_task_ids,
            normal_task_ids=normal_task_ids,
        )
        bid_tasks_map = membership_result["bid_tasks_map"]

        selected_ids, total_cost, selection_details, est_quality_state = _legacy_pgrd.greedy_select_workers(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            round_tasks=context.round_tasks,
            total_observations=context.total_observations,
            budget=context.budget,
            bid_tasks_map=bid_tasks_map,
        )
        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=total_cost,
            selection_details=selection_details,
            estimated_state={
                task_id: round(value, 4) for task_id, value in est_quality_state.items()
            },
            extra_info={
                "bid_tasks_map": bid_tasks_map,
                "member_task_ids": sorted(list(member_task_ids)),
                "normal_task_ids": sorted(list(normal_task_ids)),
                "membership_records": membership_result["membership_records"],
                "member_worker_ids": membership_result["member_worker_ids"],
                "member_count": membership_result["member_count"],
                "membership_fee_income": membership_result["membership_fee_income"],
            },
        )

    def update(self, feedback):
        update_result = super().update(feedback)
        for worker in feedback["workers"].values():
            if worker.get("category") != "trusted":
                worker["is_member"] = False

        trusted_member_count = sum(
            1
            for worker in feedback["workers"].values()
            if worker.get("is_member") and worker.get("category") == "trusted"
        )
        update_result["trusted_member_count"] = trusted_member_count
        return update_result
