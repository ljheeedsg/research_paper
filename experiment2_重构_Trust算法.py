import importlib.util
from pathlib import Path

from experiment2_重构_CMAB算法 import CMABAlgorithm


def _load_legacy_module(filename, module_name):
    module_path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_legacy_trust = _load_legacy_module(
    "experiment2_第5步加入验证任务该轮所有可做_重构前备份.py",
    "experiment2_legacy_trust",
)


class TrustCMABAlgorithm(CMABAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "trust"
        self.loader_mode = "trust"
        self.selection_mode = "paper_style_cmab_plus_validation_longrun"

    def run_round(self, context):
        selected_ids, total_cost, selection_details, est_quality_state = _legacy_trust.greedy_select_workers(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            round_tasks=context.round_tasks,
            total_observations=context.total_observations,
            budget=context.budget,
        )
        return self._build_decision(selected_ids, total_cost, selection_details, est_quality_state)

    def update(self, feedback):
        validation_tasks, validation_candidates = _legacy_trust.generate_validation_tasks_by_grid(
            available_workers=feedback["available_workers"],
            workers=feedback["workers"],
            task_grid_map=feedback["task_grid_map"],
            round_tasks=feedback["round_tasks"],
            slot_id=feedback["slot_id"],
            top_m=self.config["VALIDATION_TOP_M"],
        )
        trust_updates = _legacy_trust.update_trust_by_validation(
            validation_tasks=validation_tasks,
            available_workers=feedback["available_workers"],
            workers=feedback["workers"],
            slot_id=feedback["slot_id"],
        )
        trusted_count, unknown_count, malicious_count = self._count_categories(feedback["workers"])
        return {
            "num_validation_tasks": len(validation_tasks),
            "validation_tasks": validation_tasks,
            "validation_candidates": validation_candidates,
            "trust_updates": trust_updates,
            "trusted_count": trusted_count,
            "unknown_count": unknown_count,
            "malicious_count": malicious_count,
        }

    def _build_decision(self, selected_ids, total_cost, selection_details, est_quality_state):
        from experiment2_重构_算法数据结构 import AlgorithmDecision

        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=total_cost,
            selection_details=selection_details,
            estimated_state={
                task_id: round(value, 4) for task_id, value in est_quality_state.items()
            },
            extra_info={},
        )

    @staticmethod
    def _count_categories(workers):
        trusted_count = 0
        unknown_count = 0
        malicious_count = 0
        for worker in workers.values():
            category = worker.get("category")
            if category == "trusted":
                trusted_count += 1
            elif category == "unknown":
                unknown_count += 1
            elif category == "malicious":
                malicious_count += 1
        return trusted_count, unknown_count, malicious_count
