import importlib.util
from pathlib import Path

from experiment2_重构_算法基类 import BaseAlgorithm
from experiment2_重构_算法数据结构 import AlgorithmDecision


def _load_legacy_module(filename, module_name):
    module_path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_legacy_cmab = _load_legacy_module(
    "experiment2_第4步CMAB_重构前备份.py",
    "experiment2_legacy_cmab",
)


class CMABAlgorithm(BaseAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "cmab"
        self.loader_mode = "base"
        self.selection_mode = "paper_style_cmab_marginal_gain_over_bid_price_longrun"

    def run_round(self, context):
        selected_ids, total_cost, selection_details, est_quality_state = _legacy_cmab.greedy_select_workers(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            round_tasks=context.round_tasks,
            total_observations=context.total_observations,
            budget=context.budget,
        )
        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=total_cost,
            selection_details=selection_details,
            estimated_state={
                task_id: round(value, 4) for task_id, value in est_quality_state.items()
            },
            extra_info={},
        )
