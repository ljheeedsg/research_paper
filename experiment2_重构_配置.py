from copy import deepcopy


BASE_CONFIG = {
    "WORKER_OPTIONS_FILE": "experiment2_worker_options.json",
    "TOTAL_SLOTS": 86400 // 600,
    "PER_ROUND_BUDGET": 1000,
    "K": 7,
    "RANDOM_SEED": 3,
    "NUM_EXPERIMENT_RUNS": 10,
    "SEED_STEP": 1,

    "DELTA": 0.2, # 完成任务的质量阈值，低于该值视为失败
    "UCB_EXPLORATION_ALPHA": 0.5,
    "DEFAULT_INIT_UCB": 0.7,
    "QUALITY_SCORE_LAMBDA": 0.3,
    "UNCERTAINTY_PENALTY_MU": 0.2,
    "ROUND_LEVEL_QUALITY_UPDATE": True,
    "STABILITY_BONUS_GAMMA": 0.12,
    "MAX_NEW_WORKERS_PER_ROUND": 2,
    "UCB_STATE_DELTA_CAP": 0.12,
    "COLD_START_PENALTY_ZERO": 0.18,
    "COLD_START_PENALTY_FEW": 0.08,
    "COLD_START_MIN_OBS": 3,
    "RHO": 10.0, 
    "WORKER_COST_RATIO": 0.6,
    "BETA0": -0.5,
    "BETA1": 0.1,
    "BETA2": 0.3,
    "VALIDATION_TOP_M": 7,
    "TRUST_INIT_TRUSTED": 1.0,
    "TRUST_INIT_UNKNOWN": 0.5,
    "ETA": 0.05, # 信任更新步长
    "THETA_HIGH": 0.8,
    "THETA_LOW": 0.20,
    "ERROR_GOOD": 0.15, # 误差小于该值视为好
    "ERROR_BAD": 0.35, # 误差大于该值视为坏
    "MEMBERSHIP_FEE": 2, 
    "MEMBER_TASK_RATIO": 0.3, 
    "MEMBER_REWARD_MULTIPLIER": 1.6, # 会员任务奖励乘数
    "NORMAL_REWARD_MULTIPLIER": 1.0, # 非会员任务奖励乘数
    "PGRD_LAMBDA": 1.5, # PGRD损失函数中参考损失的权重
    "PGRD_XI": 4.0, # PGRD中sigmoid函数的参数，控制会员资格概率的分布
    "MEMBERSHIP_THRESHOLD": 0.45, # 会员资格概率阈值
    "SUNK_THRESHOLD": 30,
    "MEMBER_BONUS": 30,
    "RHO_INIT": 1.0, # PGRD初始rho值
    "BETA3": 1.0, # LGSC算法中当前沉没损失对会员资格概率的影响权重
    "BETA4": 2.0, # LGSC算法中累计沉没损失对会员资格概率的影响权重
    "SKIP_EMPTY_ROUNDS": True,
}


MODE_OUTPUTS = {
    "random": {
        "prefix": "experiment2_random_longrun",
        "plot_keys": [
            "coverage_rate",
            "completion_rate",
            "avg_quality",
            "cumulative_coverage_rate",
            "cumulative_completion_rate",
            "cumulative_avg_quality",
            "platform_utility",
            "cumulative_platform_utility",
            "num_left_workers_this_round",
            "cumulative_left_workers",
        ],
    },
    "epsilon_first": {
    "prefix": "experiment2_epsilon_first_longrun",
    "plot_keys": [
        "coverage_rate",
        "completion_rate",
        "avg_quality",
        "cumulative_coverage_rate",
        "cumulative_completion_rate",
        "cumulative_avg_quality",
        "platform_utility",
        "cumulative_platform_utility",
        "num_left_workers_this_round",
        "cumulative_left_workers",
    ],
    },
    "cmab": {
        "prefix": "experiment2_cmab_longrun",
        "plot_keys": [
            "coverage_rate",
            "completion_rate",
            "avg_quality",
            "cumulative_coverage_rate",
            "cumulative_completion_rate",
            "cumulative_avg_quality",
            "platform_utility",
            "cumulative_platform_utility",
            "num_left_workers_this_round",
            "cumulative_left_workers",
        ],
    },
    "trust": {
        "prefix": "experiment2_cmab_trust",
        "plot_keys": [
            "coverage_rate",
            "completion_rate",
            "avg_quality",
            "cumulative_coverage_rate",
            "cumulative_completion_rate",
            "cumulative_avg_quality",
            "trusted_count",
            "unknown_count",
            "malicious_count",
            "num_validation_tasks",
            "platform_utility",
            "cumulative_platform_utility",
            "num_left_workers_this_round",
            "cumulative_left_workers",
        ],
    },
    "pgrd": {
        "prefix": "experiment2_cmab_trust_pgrd",
        "plot_keys": [
            "coverage_rate",
            "completion_rate",
            "avg_quality",
            "cumulative_coverage_rate",
            "cumulative_completion_rate",
            "cumulative_avg_quality",
            "trusted_count",
            "unknown_count",
            "malicious_count",
            "num_validation_tasks",
            "platform_utility",
            "cumulative_platform_utility",
            "num_left_workers_this_round",
            "cumulative_left_workers",
            "member_count",
            "trusted_member_count",
            "membership_fee_income",
        ],
    },
    "lgsc": {
        "prefix": "experiment2_cmab_trust_pgrd_lgsc",
        "plot_keys": [
            "coverage_rate",
            "completion_rate",
            "avg_quality",
            "cumulative_coverage_rate",
            "cumulative_completion_rate",
            "cumulative_avg_quality",
            "platform_utility",
            "cumulative_platform_utility",
            "num_left_workers_this_round",
            "cumulative_left_workers",
            "member_count",
            "membership_fee_income",
            "bonus_payment",
        ],
    },
}


def build_config(mode, overrides=None):
    config = deepcopy(BASE_CONFIG)
    config["MODE"] = mode
    config.update(MODE_OUTPUTS[mode])

    # if mode == "random":
    #     config["BETA1"] = 0.02
    # elif mode == "cmab":
    #     config["BETA1"] = 0.02
    # elif mode in {"trust", "pgrd", "lgsc"}:
    #     config["BETA1"] = 0.1

    if mode == "epsilon_first":
        config["EPSILON_FIRST_RATIO"] = 0.3
        config["ROUND_LEVEL_QUALITY_UPDATE"] = False

    if mode == "random":
        config["ROUND_LEVEL_QUALITY_UPDATE"] = False

    if overrides:
        config.update(overrides)

    prefix = config["prefix"]
    config["ROUND_RESULTS_FILE"] = f"{prefix}_round_results.json"
    config["SUMMARY_FILE"] = f"{prefix}_summary.json"
    config["ALL_RUNS_FILE"] = f"{prefix}_round_results_all_runs.json"

    config["PLOT_FILES"] = {
        "coverage_rate": f"{prefix}_coverage_rate.png",
        "completion_rate": f"{prefix}_completion_rate.png",
        "avg_quality": f"{prefix}_avg_quality.png",
        "cumulative_coverage_rate": f"{prefix}_cumulative_coverage_rate.png",
        "cumulative_completion_rate": f"{prefix}_cumulative_completion_rate.png",
        "cumulative_avg_quality": f"{prefix}_cumulative_avg_quality.png",
        "platform_utility": f"{prefix}_platform_utility.png",
        "cumulative_platform_utility": f"{prefix}_cumulative_platform_utility.png",
        "num_left_workers_this_round": f"{prefix}_left_workers_per_round.png",
        "cumulative_left_workers": f"{prefix}_left_workers.png",
        "trusted_count": f"{prefix}_trusted_count.png",
        "unknown_count": f"{prefix}_unknown_count.png",
        "malicious_count": f"{prefix}_malicious_count.png",
        "num_validation_tasks": f"{prefix}_validation_count.png",
        "member_count": f"{prefix}_member_count.png",
        "trusted_member_count": f"{prefix}_trusted_member_count.png",
        "membership_fee_income": f"{prefix}_membership_fee_income.png",
        "bonus_payment": f"{prefix}_bonus_payment.png",
    }
    return config
