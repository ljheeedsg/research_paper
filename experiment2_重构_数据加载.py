import json
from collections import defaultdict

import numpy as np


class DataLoader:
    """
    通用数据加载类。

    mode:
        base  : 基础版本，适合 random / 原始 CMAB
        trust : 加入 trust / category / task_grid_map
        pgrd  : 在 trust 基础上加入会员机制字段
        lgsc  : 在 pgrd 基础上加入沉没成本字段
    """

    def __init__(
        self,
        worker_options_file,
        mode="base",
        trust_init_trusted=1.0,
        trust_init_unknown=0.5,
        rho_init=1.0,
    ):
        self.worker_options_file = worker_options_file
        self.mode = mode
        self.trust_init_trusted = trust_init_trusted
        self.trust_init_unknown = trust_init_unknown
        self.rho_init = rho_init

        valid_modes = {"base", "trust", "pgrd", "lgsc"}
        if self.mode not in valid_modes:
            raise ValueError(f"mode 必须是 {valid_modes} 之一，但当前是: {self.mode}")

    def load_worker_options(self):
        with open(self.worker_options_file, "r", encoding="utf-8") as f:
            worker_options = json.load(f)

        print(f"已加载工人可选项: {len(worker_options)} 个工人")
        return worker_options

    def load_all_tasks_from_workers(self, worker_options):
        """
        汇总所有任务，并按 slot_id 分组。

        返回：
            task_dict
            tasks_by_slot
            task_grid_map

        注意：
            base 模式下即使暂时不用 task_grid_map，也统一返回，方便后续模块复用。
        """
        task_dict = {}
        task_grid_map = {}

        for _, worker in worker_options.items():
            for task in worker.get("tasks", []):
                task_id = task["task_id"]

                if task_id not in task_dict:
                    task_dict[task_id] = {
                        "task_id": task_id,
                        "slot_id": int(task["slot_id"]),
                        "region_id": int(task["region_id"]),
                        "required_workers": int(task["required_workers"]),
                        "weight": float(task["weight"]),
                    }

                    task_grid_map[task_id] = int(task["region_id"])

        tasks_by_slot = defaultdict(list)

        for task in task_dict.values():
            tasks_by_slot[task["slot_id"]].append(task)

        for slot_id in tasks_by_slot:
            tasks_by_slot[slot_id].sort(key=lambda x: x["task_id"])

        print(f"从 worker options 中收集到任务: {len(task_dict)} 个")
        return task_dict, tasks_by_slot, task_grid_map

    def build_worker_profiles(self, worker_options):
        workers = {}

        for _, worker in worker_options.items():
            worker_id = int(worker["worker_id"])
            tasks = worker.get("tasks", [])

            task_map = {task["task_id"]: task for task in tasks}

            tasks_by_slot = defaultdict(list)
            for task in tasks:
                tasks_by_slot[int(task["slot_id"])].append(task["task_id"])

            for slot_id in tasks_by_slot:
                tasks_by_slot[slot_id].sort()

            bid_price = float(worker.get("bid_price", worker["cost"]))

            worker_profile = {
                "worker_id": worker_id,
                "cost": bid_price,
                "bid_price": bid_price,
                "init_category": worker["init_category"],
                "base_quality": float(worker["base_quality"]),
                "available_slots": set(worker.get("available_slots", [])),
                "task_map": task_map,
                "tasks_by_slot": tasks_by_slot,

                # CMAB 学习状态
                "n_obs": 0,
                "avg_quality": 0.0,

                # 长期运行状态
                "is_active": True,
                "cumulative_reward": 0.0,
                "cumulative_cost": 0.0,
                "recent_reward": 0.0,
                "leave_probability": 0.0,
                "selected_rounds": 0,
                "active_rounds": 0,
                "left_round_id": None,
            }

            if self.mode in {"trust", "pgrd", "lgsc"}:
                self.add_trust_fields(worker_profile, worker)

            if self.mode in {"pgrd", "lgsc"}:
                self.add_pgrd_fields(worker_profile)

            if self.mode == "lgsc":
                self.add_lgsc_fields(worker_profile)

            workers[worker_id] = worker_profile

        return workers

    def add_trust_fields(self, worker_profile, raw_worker):
        """
        第5步以后使用：
        平台初始只知道 trusted，其余真实 unknown / malicious 初始都视为 unknown。
        """
        init_category = raw_worker["init_category"]

        if init_category == "trusted":
            trust = self.trust_init_trusted
            category = "trusted"
        else:
            trust = self.trust_init_unknown
            category = "unknown"

        worker_profile.update({
            "trust": trust,
            "category": category,
        })

    def add_pgrd_fields(self, worker_profile):
        """
        第6步以后使用：PGRD 会员机制状态。
        """
        worker_profile.update({
            "is_member": False,
            "membership_probability": 0.0,
            "cumulative_membership_fee": 0.0,
            "member_rounds": 0,
        })

    def add_lgsc_fields(self, worker_profile):
        """
        第7步以后使用：LGSC / 沉没成本机制状态。
        """
        worker_profile.update({
            "sunk_value": 0.0,
            "sunk_rate": self.rho_init,
            "bonus_count": 0,
            "period_cost_sum": 0.0,
            "cumulative_bonus": 0.0,
            "current_sunk_loss": 0.0,
        })

    def summarize_initial_workers(self, workers):
        base_qualities = [float(worker["base_quality"]) for worker in workers.values()]

        trusted_qualities = [
            float(worker["base_quality"])
            for worker in workers.values()
            if worker["init_category"] == "trusted"
        ]

        unknown_qualities = [
            float(worker["base_quality"])
            for worker in workers.values()
            if worker["init_category"] == "unknown"
        ]

        malicious_qualities = [
            float(worker["base_quality"])
            for worker in workers.values()
            if worker["init_category"] == "malicious"
        ]

        total_workers = len(workers)

        def safe_mean(values):
            return round(float(np.mean(values)), 4) if values else 0.0

        return {
            "initial_total_workers": total_workers,
            "initial_true_trusted_count": len(trusted_qualities),
            "initial_true_unknown_count": len(unknown_qualities),
            "initial_true_malicious_count": len(malicious_qualities),
            "initial_true_trusted_ratio": round(len(trusted_qualities) / total_workers, 4)
            if total_workers > 0 else 0.0,
            "initial_avg_base_quality": safe_mean(base_qualities),
            "initial_true_trusted_avg_base_quality": safe_mean(trusted_qualities),
            "initial_true_unknown_avg_base_quality": safe_mean(unknown_qualities),
            "initial_true_malicious_avg_base_quality": safe_mean(malicious_qualities),
        }

    def load(self):
        worker_options = self.load_worker_options()

        task_dict, tasks_by_slot, task_grid_map = self.load_all_tasks_from_workers(
            worker_options
        )

        workers = self.build_worker_profiles(worker_options)

        initial_stats = self.summarize_initial_workers(workers)

        return workers, task_dict, tasks_by_slot, task_grid_map, initial_stats