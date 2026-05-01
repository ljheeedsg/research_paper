import argparse
import random

import numpy as np

from experiment2_重构_CMAB算法 import CMABAlgorithm
from experiment2_重构_LGSC算法 import LGSCAlgorithm
from experiment2_重构_PGRD算法 import PGRDAlgorithm
from experiment2_重构_Trust算法 import TrustCMABAlgorithm
from experiment2_重构_数据加载 import DataLoader
from experiment2_重构_结果管理 import (
    aggregate_round_results,
    average_dict_records,
    plot_metric,
    save_json,
    summarize_results,
)
from experiment2_重构_实验器 import Simulator
from experiment2_重构_配置 import build_config
from experiment2_重构_随机算法 import RandomAlgorithm
from experiment2_重构_EpsilonFirst算法 import EpsilonFirstAlgorithm

ALGORITHM_FACTORY = {
    "random": RandomAlgorithm,
    "epsilon_first": EpsilonFirstAlgorithm,
    "cmab": CMABAlgorithm,
    "trust": TrustCMABAlgorithm,
    "pgrd": PGRDAlgorithm,
    "lgsc": LGSCAlgorithm,
}


def set_random_seed(seed):
    random.seed(seed)
    np.random.seed(seed)


def run_single_experiment(mode, seed, config):
    set_random_seed(seed)

    algorithm = ALGORITHM_FACTORY[mode](config)
    loader = DataLoader(
        worker_options_file=config["WORKER_OPTIONS_FILE"],
        mode=algorithm.loader_mode,
        trust_init_trusted=config["TRUST_INIT_TRUSTED"],
        trust_init_unknown=config["TRUST_INIT_UNKNOWN"],
        rho_init=config["RHO_INIT"],
    )
    workers, task_dict, tasks_by_slot, task_grid_map, initial_stats = loader.load()

    simulator = Simulator(
        workers=workers,
        tasks_by_slot=tasks_by_slot,
        task_grid_map=task_grid_map,
        algorithm=algorithm,
        config=config,
    )
    round_results = simulator.run()
    summary = summarize_results(round_results, workers, algorithm, initial_stats)
    return round_results, summary


def run_experiment(mode, overrides=None):
    config = build_config(mode, overrides=overrides)
    seeds = [
        config["RANDOM_SEED"] + i * config["SEED_STEP"]
        for i in range(config["NUM_EXPERIMENT_RUNS"])
    ]
    print(f"开始重复实验，共 {config['NUM_EXPERIMENT_RUNS']} 次，随机种子: {seeds}")

    all_round_results = []
    all_summaries = []
    all_runs_payload = []

    for run_idx, seed in enumerate(seeds, start=1):
        print(f"\n===== Run {run_idx}/{config['NUM_EXPERIMENT_RUNS']} | seed={seed} =====")
        round_results, summary = run_single_experiment(mode, seed, config)
        all_round_results.append(round_results)
        all_summaries.append(summary)
        all_runs_payload.append(
            {
                "run_index": run_idx,
                "seed": seed,
                "summary": summary,
                "round_results": round_results,
            }
        )

    avg_round_results = aggregate_round_results(all_round_results)
    avg_summary = average_dict_records(all_summaries)
    avg_summary["num_experiment_runs"] = config["NUM_EXPERIMENT_RUNS"]
    avg_summary["experiment_seeds"] = seeds

    save_json(all_runs_payload, config["ALL_RUNS_FILE"])
    save_json(avg_round_results, config["ROUND_RESULTS_FILE"])
    save_json(avg_summary, config["SUMMARY_FILE"])

    plot_labels = {
        "coverage_rate": "Coverage Rate",
        "completion_rate": "Completion Rate",
        "avg_quality": "Average Realized Quality",
        "cumulative_coverage_rate": "Cumulative Coverage Rate",
        "cumulative_completion_rate": "Cumulative Completion Rate",
        "cumulative_avg_quality": "Cumulative Average Quality",
        "platform_utility": "Platform Utility",
        "cumulative_platform_utility": "Cumulative Platform Utility",
        "num_left_workers_this_round": "Left Workers per Round",
        "cumulative_left_workers": "Cumulative Left Workers",
        "trusted_count": "Trusted Count",
        "unknown_count": "Unknown Count",
        "malicious_count": "Malicious Count",
        "num_validation_tasks": "Validation Task Count",
        "member_count": "Member Count",
        "trusted_member_count": "Trusted Member Count",
        "membership_fee_income": "Membership Fee Income",
        "bonus_payment": "Bonus Payment",
    }
    for key in config["plot_keys"]:
        ylabel = plot_labels[key]
        plot_metric(avg_round_results, key, ylabel, config["PLOT_FILES"][key])

    return avg_round_results, avg_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=list(ALGORITHM_FACTORY.keys()),
        default="lgsc",
    )
    parser.add_argument("--runs", type=int, default=None)
    args = parser.parse_args()

    overrides = {}
    if args.runs is not None:
        overrides["NUM_EXPERIMENT_RUNS"] = args.runs

    _, summary = run_experiment(args.mode, overrides=overrides)
    print("全部完成")
    print("Average Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
