import importlib.util
from pathlib import Path

from experiment2_重构_PGRD算法 import PGRDAlgorithm


def _load_legacy_module(filename, module_name):
    module_path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_legacy_lgsc = _load_legacy_module(
    "experiment2_第7步加入LGSC_重构前备份.py",
    "experiment2_legacy_lgsc",
)


class LGSCAlgorithm(PGRDAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "lgsc"
        self.loader_mode = "lgsc"
        self.selection_mode = "paper_style_cmab_plus_validation_plus_pgrd_plus_lgsc"

    def update(self, feedback):
        update_result = super().update(feedback)
        lgsc_result = _legacy_lgsc.update_lgsc_state(
            selected_worker_ids=feedback["selected_worker_ids"],
            workers=feedback["workers"],
            slot_id=feedback["slot_id"],
            bid_tasks_map=feedback.get("bid_tasks_map"),
        )
        update_result.update(lgsc_result)
        return update_result
