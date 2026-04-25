import math

from experiment2_重构_CMAB算法 import greedy_select_workers
from experiment2_重构_Trust算法 import TrustCMABAlgorithm
from experiment2_重构_算法数据结构 import AlgorithmDecision


def split_member_and_normal_tasks(round_tasks, member_ratio):
    if not round_tasks:
        return set(), set()

    if float(member_ratio) <= 0:
        return set(), {task["task_id"] for task in round_tasks}

    task_infos = []
    for task in round_tasks:
        task_id = task["task_id"]
        weight = float(task["weight"])
        member_score = float(task.get("weight", weight))
        task_infos.append((task_id, member_score))

    task_infos.sort(key=lambda item: (-item[1], item[0]))
    member_count = int(round(len(task_infos) * float(member_ratio)))
    member_count = min(member_count, len(task_infos))

    member_task_ids = {task_id for task_id, _ in task_infos[:member_count]}
    normal_task_ids = {task_id for task_id, _ in task_infos[member_count:]}
    return member_task_ids, normal_task_ids


def _sigmoid(value):
    value = max(-20.0, min(20.0, value))
    return 1.0 / (1.0 + math.exp(-value))


def update_membership_by_pgrd(available_workers, slot_id, member_task_ids, normal_task_ids, config):
    membership_records = []
    member_worker_ids = []
    membership_fee_income_t = 0.0
    bid_tasks_map = {}

    for worker in available_workers:
        worker["membership_probability"] = 0.0

        bid_task_ids = set(worker["tasks_by_slot"].get(slot_id, []))
        member_bid_tasks = sorted(list(bid_task_ids & member_task_ids))
        normal_bid_tasks = sorted(list(bid_task_ids & normal_task_ids))

        if not member_task_ids:
            worker["is_member"] = False
            bid_tasks_map[worker["worker_id"]] = sorted(list(bid_task_ids & normal_task_ids))
            continue

        if worker["category"] == "malicious":
            worker["is_member"] = False
            bid_tasks_map[worker["worker_id"]] = []
            continue

        if worker["category"] != "trusted":
            worker["is_member"] = False
            bid_tasks_map[worker["worker_id"]] = normal_bid_tasks
            continue

        n_m = len(member_bid_tasks)
        n_n = len(normal_bid_tasks)

        if n_m == 0 and n_n == 0:
            worker["is_member"] = False
            bid_tasks_map[worker["worker_id"]] = []
            continue

        member_net_values = []
        for task_id in member_bid_tasks:
            weight = float(worker["task_map"][task_id]["weight"])
            p_m = float(config["MEMBER_REWARD_MULTIPLIER"]) * weight
            c_m = float(config["WORKER_COST_RATIO"]) * float(worker["bid_price"])
            member_net_values.append(p_m - c_m)

        normal_net_values = []
        for task_id in normal_bid_tasks:
            weight = float(worker["task_map"][task_id]["weight"])
            p_n = float(config["NORMAL_REWARD_MULTIPLIER"]) * weight
            c_n = float(config["WORKER_COST_RATIO"]) * float(worker["bid_price"])
            normal_net_values.append(p_n - c_n)

        avg_member_net = sum(member_net_values) / len(member_net_values) if member_net_values else 0.0
        avg_normal_net = sum(normal_net_values) / len(normal_net_values) if normal_net_values else 0.0

        r_a = n_m * avg_member_net - float(config["MEMBERSHIP_FEE"])
        r_b = n_n * avg_normal_net
        ref_loss = max(0.0, r_a - r_b)
        diff = r_a - r_b + float(config["PGRD_LAMBDA"]) * ref_loss
        psi = _sigmoid(float(config["PGRD_XI"]) * diff)

        is_member = psi >= float(config["MEMBERSHIP_THRESHOLD"])
        worker["membership_probability"] = float(psi)
        worker["is_member"] = bool(is_member)

        if is_member:
            member_worker_ids.append(worker["worker_id"])
            membership_fee_income_t += float(config["MEMBERSHIP_FEE"])
            worker["cumulative_membership_fee"] += float(config["MEMBERSHIP_FEE"])
            worker["member_rounds"] += 1
            bid_tasks_map[worker["worker_id"]] = sorted(member_bid_tasks + normal_bid_tasks)
        else:
            bid_tasks_map[worker["worker_id"]] = normal_bid_tasks

        membership_records.append({
            "worker_id": worker["worker_id"],
            "member_task_count": n_m,
            "normal_task_count": n_n,
            "R_A": round(r_a, 4),
            "R_B": round(r_b, 4),
            "reference_loss": round(ref_loss, 4),
            "membership_probability": round(psi, 4),
            "is_member": bool(is_member),
            "bid_task_ids": bid_tasks_map[worker["worker_id"]],
        })

    return {
        "membership_records": membership_records,
        "member_worker_ids": member_worker_ids,
        "member_count": len(member_worker_ids),
        "membership_fee_income": round(membership_fee_income_t, 4),
        "bid_tasks_map": bid_tasks_map,
    }


class PGRDAlgorithm(TrustCMABAlgorithm):
    def __init__(self, config):
        super().__init__(config)
        self.name = "pgrd"
        self.loader_mode = "pgrd"
        self.selection_mode = "paper_style_cmab_plus_validation_plus_pgrd"

    def run_round(self, context):
        member_task_ids, normal_task_ids = split_member_and_normal_tasks(
            context.round_tasks,
            self.config["MEMBER_TASK_RATIO"],
        )
        membership_result = update_membership_by_pgrd(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            member_task_ids=member_task_ids,
            normal_task_ids=normal_task_ids,
            config=self.config,
        )
        bid_tasks_map = membership_result["bid_tasks_map"]

        selected_ids, total_cost, selection_details, est_quality_state = greedy_select_workers(
            available_workers=context.available_workers,
            slot_id=context.slot_id,
            round_tasks=context.round_tasks,
            total_observations=context.total_observations,
            budget=context.budget,
            config=self.config,
            bid_tasks_map=bid_tasks_map,
            exclude_malicious=True,
        )
        return AlgorithmDecision(
            selected_worker_ids=selected_ids,
            cost=total_cost,
            selection_details=selection_details,
            estimated_state=est_quality_state,
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
        trusted_member_count = sum(
            1
            for worker in feedback["workers"].values()
            if worker.get("is_member") and worker.get("category") == "trusted"
        )
        update_result["trusted_member_count"] = trusted_member_count
        return update_result
