import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SERIES_CONFIG = [
    {
        "label": "B1 Random",
        "paths": [
            "experiment2_random_longrun_round_results.json",
            "experiment2_random_round_results.json",
        ],
        "color": "#4C78A8",
        "marker": "o",
    },
    {
        "label": "B2 Epsilon-First",
        "paths": [
            "experiment2_epsilon_first_longrun_round_results.json",
            "experiment2_epsilon_first_round_results.json",
        ],
        "color": "#F58518",
        "marker": "s",
    },
    {
        "label": "B3 Pure CMAB",
        "paths": [
            "experiment2_cmab_longrun_round_results.json",
            "experiment2_cmab_round_results.json",
        ],
        "color": "#54A24B",
        "marker": "^",
    },
]

METRICS_TO_PLOT = [
    {
        "key": "coverage_rate",
        "ylabel": "Coverage Rate",
        "title": "Experiment 2 B1-B2-B3: Coverage Rate Comparison",
        "filename": "experiment2_B1_B2_B3_coverage_rate_raw.png",
    },
    {
        "key": "coverage_rate",
        "ylabel": "Coverage Rate",
        "title": "Experiment 2 B1-B2-B3: Coverage Rate Comparison (Smoothed)",
        "filename": "experiment2_B1_B2_B3_coverage_rate_smoothed.png",
        "smooth_window": 7,
    },
    {
        "key": "completion_rate",
        "ylabel": "Completion Rate",
        "title": "Experiment 2 B1-B2-B3: Completion Rate Comparison",
        "filename": "experiment2_B1_B2_B3_completion_rate_raw.png",
    },
    {
        "key": "completion_rate",
        "ylabel": "Completion Rate",
        "title": "Experiment 2 B1-B2-B3: Completion Rate Comparison (Smoothed)",
        "filename": "experiment2_B1_B2_B3_completion_rate_smoothed.png",
        "smooth_window": 7,
    },
    {
        "key": "cumulative_coverage_rate",
        "ylabel": "Cumulative Coverage Rate",
        "title": "Experiment 2 B1-B2-B3: Cumulative Coverage Rate Comparison",
        "filename": "experiment2_B1_B2_B3_cumulative_coverage_rate.png",
    },
    {
        "key": "cumulative_completion_rate",
        "ylabel": "Cumulative Completion Rate",
        "title": "Experiment 2 B1-B2-B3: Cumulative Completion Rate Comparison",
        "filename": "experiment2_B1_B2_B3_cumulative_completion_rate.png",
    },
    {
        "key": "avg_quality",
        "ylabel": "Average Realized Quality",
        "title": "Experiment 2 B1-B2-B3: Average Realized Quality Comparison",
        "filename": "experiment2_B1_B2_B3_avg_quality_raw.png",
    },
    {
        "key": "avg_quality",
        "ylabel": "Average Realized Quality",
        "title": "Experiment 2 B1-B2-B3: Average Realized Quality Comparison (Smoothed)",
        "filename": "experiment2_B1_B2_B3_avg_quality_smoothed.png",
        "smooth_window": 7,
    },
    {
        "key": "cumulative_avg_quality",
        "ylabel": "Cumulative Average Quality",
        "title": "Experiment 2 B1-B2-B3: Cumulative Average Quality Comparison",
        "filename": "experiment2_B1_B2_B3_cumulative_avg_quality.png",
    },
    {
        "key": "platform_utility",
        "ylabel": "Platform Utility",
        "title": "Experiment 2 B1-B2-B3: Platform Utility Comparison",
        "filename": "experiment2_B1_B2_B3_platform_utility.png",
    },
    {
        "key": "cumulative_platform_utility",
        "ylabel": "Cumulative Platform Utility",
        "title": "Experiment 2 B1-B2-B3: Cumulative Platform Utility Comparison",
        "filename": "experiment2_B1_B2_B3_cumulative_platform_utility.png",
    },
    {
        "key": "num_left_workers_this_round",
        "ylabel": "Left Workers per Round",
        "title": "Experiment 2 B1-B2-B3: Left Workers per Round Comparison",
        "filename": "experiment2_B1_B2_B3_left_workers_per_round.png",
        "smooth_window": 7,
    },
]

B3_WORKER_TYPE_METRIC = {
    "title": "Experiment 2 B3: Worker Type Count by Round",
    "filename": "experiment2_B3_worker_type_count.png",
    "series": [
        {
            "key": "trusted_count",
            "label": "Trusted Workers",
            "color": "#54A24B",
            "marker": "o",
        },
        {
            "key": "unknown_count",
            "label": "Unknown Workers",
            "color": "#4C78A8",
            "marker": "s",
        },
        {
            "key": "malicious_count",
            "label": "Malicious Workers",
            "color": "#E45756",
            "marker": "^",
        },
    ],
}


def resolve_result_path(candidate_paths):
    for candidate in candidate_paths:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def load_round_results(filepath):
    with filepath.open("r", encoding="utf-8") as f:
        round_results = json.load(f)
    return [item for item in round_results if int(item.get("num_tasks", 0)) > 0]


def build_series():
    series = []
    for config in SERIES_CONFIG:
        path = resolve_result_path(config["paths"])
        if path is None:
            print(f"Skip {config['label']}: no result file found in {config['paths']}")
            continue

        rounds = load_round_results(path)
        if not rounds:
            print(f"Skip {config['label']}: no non-empty rounds in {path.name}")
            continue

        series.append(
            {
                "label": config["label"],
                "path": path,
                "color": config["color"],
                "marker": config["marker"],
                "rounds": rounds,
            }
        )

    if not series:
        raise ValueError("No available B1/B2/B3 experiment2 result files were found.")

    return series


def moving_average(values, window):
    if window <= 1 or len(values) <= 2:
        return values

    half_window = window // 2
    smoothed = []
    for idx in range(len(values)):
        start = max(0, idx - half_window)
        end = min(len(values), idx + half_window + 1)
        smoothed.append(sum(values[start:end]) / (end - start))
    return smoothed


def plot_metric(series, metric):
    plt.figure(figsize=(11, 6))

    plotted_count = 0
    for config in series:
        rounds = [item for item in config["rounds"] if metric["key"] in item]
        if not rounds:
            continue

        x = [int(item["round_id"]) for item in rounds]
        y = [float(item[metric["key"]]) for item in rounds]
        y = moving_average(y, int(metric.get("smooth_window", 1)))
        mark_every = max(1, len(x) // 12)

        plt.plot(
            x,
            y,
            label=config["label"],
            color=config["color"],
            marker=config["marker"],
            linewidth=2.0,
            markersize=5,
            markevery=mark_every,
        )
        plotted_count += 1

    if plotted_count == 0:
        print(f"Skip metric {metric['key']}: no algorithm contains this field.")
        plt.close()
        return

    plt.xlabel("Round")
    plt.ylabel(metric["ylabel"])
    plt.title(metric["title"])
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.legend()
    plt.tight_layout()
    plt.savefig(metric["filename"], dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved {metric['filename']}")


def plot_b3_worker_type_counts(series):
    b3_series = next(
        (config for config in series if config["label"] == "B3 Pure CMAB"),
        None,
    )
    if b3_series is None:
        print("Skip B3 worker type count: B3 series is unavailable.")
        return

    plt.figure(figsize=(11, 6))

    plotted_count = 0
    for metric in B3_WORKER_TYPE_METRIC["series"]:
        rounds = [item for item in b3_series["rounds"] if metric["key"] in item]
        if not rounds:
            continue

        x = [int(item["round_id"]) for item in rounds]
        y = [float(item[metric["key"]]) for item in rounds]
        mark_every = max(1, len(x) // 12)

        plt.plot(
            x,
            y,
            label=metric["label"],
            color=metric["color"],
            marker=metric["marker"],
            linewidth=2.0,
            markersize=5,
            markevery=mark_every,
        )
        plotted_count += 1

    if plotted_count == 0:
        print("Skip B3 worker type count: no worker type fields were found.")
        plt.close()
        return

    plt.xlabel("Round")
    plt.ylabel("Worker Count")
    plt.title(B3_WORKER_TYPE_METRIC["title"])
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.legend()
    plt.tight_layout()
    plt.savefig(B3_WORKER_TYPE_METRIC["filename"], dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved {B3_WORKER_TYPE_METRIC['filename']}")


def main():
    series = build_series()
    for metric in METRICS_TO_PLOT:
        plot_metric(series, metric)
    plot_b3_worker_type_counts(series)


if __name__ == "__main__":
    main()
