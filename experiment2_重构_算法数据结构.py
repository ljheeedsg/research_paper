from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RoundContext:
    """
    每一轮传给算法的信息。
    算法只看这个 context，不直接关心主程序怎么写。
    """
    round_id: int
    slot_id: int
    available_workers: list
    round_tasks: list
    workers: dict
    total_observations: int = 0
    budget: float = 0.0
    bid_tasks_map: Optional[dict] = None
    task_grid_map: Optional[dict] = None
    config: Optional[dict] = None


@dataclass
class AlgorithmDecision:
    """
    算法每一轮返回的结果。
    所有算法都统一返回这个结构。
    """
    selected_worker_ids: list
    cost: float
    selection_details: list = field(default_factory=list)
    estimated_state: dict = field(default_factory=dict)
    extra_info: dict[str, Any] = field(default_factory=dict)
