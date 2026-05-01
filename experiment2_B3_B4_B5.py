import json
from pathlib import Path

import matplotlib.pyplot as plt


SERIES_CONFIG = [
    {
        "label": "B3 CMAB + Validation",
        "paths": [
            "experiment2_cmab_trust_round_results.json",
        ],
        "color": "#54A24B",
        "marker": "^",
    },
    {
        "label": "B4 CMAB + Validation + PGRD",
        "paths": [
            "experiment2_cmab_trust_pgrd_round_results.json",
        ],
        "color": "#E45756",
        "marker": "D",
    },
    {
        "label": "B5 CMAB + Validation + PGRD + LGSC",
        "paths": [
            "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        ],
        "color": "#72B7B2",
        "marker": "P",
    },
]

METRICS_TO_PLOT = [
    {
        "key": "coverage_rate",
        "ylabel": "Coverage Rate",
        "title": "Experiment 2 B3-B4-B5: Coverage Rate Comparison (Smoothed)",
        "filename": "experiment2_B3_B4_B5_coverage_rate.png",
        "smooth_window": 7,
    },
    {
        "key": "completion_rate",
        "ylabel": "Completion Rate",
        "title": "Experiment 2 B3-B4-B5: Completion Rate Comparison (Smoothed)",
        "filename": "experiment2_B3_B4_B5_completion_rate.png",
        "smooth_window": 7,
    },
    {
        "key": "cumulative_coverage_rate",
        "ylabel": "Cumulative Coverage Rate",
        "title": "Experiment 2 B3-B4-B5: Cumulative Coverage Rate Comparison",
        "filename": "experiment2_B3_B4_B5_cumulative_coverage_rate.png",
    },
    {
        "key": "cumulative_completion_rate",
        "ylabel": "Cumulative Completion Rate",
        "title": "Experiment 2 B3-B4-B5: Cumulative Completion Rate Comparison",
        "filename": "experiment2_B3_B4_B5_cumulative_completion_rate.png",
    },
    {
        "key": "avg_quality",
        "ylabel": "Average Realized Quality",
        "title": "Experiment 2 B3-B4-B5: Average Realized Quality Comparison (Smoothed)",
        "filename": "experiment2_B3_B4_B5_avg_quality.png",
        "smooth_window": 7,
    },
    {
        "key": "cumulative_avg_quality",
        "ylabel": "Cumulative Average Quality",
        "title": "Experiment 2 B3-B4-B5: Cumulative Average Quality Comparison",
        "filename": "experiment2_B3_B4_B5_cumulative_avg_quality.png",
    },
    {
        "key": "platform_utility",
        "ylabel": "Platform Utility",
        "title": "Experiment 2 B3-B4-B5: Platform Utility Comparison",
        "filename": "experiment2_B3_B4_B5_platform_utility.png",
    },
    {
        "key": "cumulative_platform_utility",
        "ylabel": "Cumulative Platform Utility",
        "title": "Experiment 2 B3-B4-B5: Cumulative Platform Utility Comparison",
        "filename": "experiment2_B3_B4_B5_cumulative_platform_utility.png",
    },
    {
        "key": "num_left_workers_this_round",
        "ylabel": "Left Workers per Round",
        "title": "Experiment 2 B3-B4-B5: Left Workers per Round Comparison",
        "filename": "experiment2_B3_B4_B5_left_workers_per_round.png",
        "smooth_window": 7,
    },
]


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
        raise ValueError("No available B3/B4/B5 experiment2 result files were found.")

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


def main():
    series = build_series()
    for metric in METRICS_TO_PLOT:
        plot_metric(series, metric)


if __name__ == "__main__":
    main()
