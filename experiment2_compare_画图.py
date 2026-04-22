import json
from pathlib import Path

import matplotlib.pyplot as plt


SERIES_CONFIG = [
    {
        "label": "Random",
        "paths": [
            "experiment2_random_longrun_round_results.json",
            "experiment2_random_round_results.json",
        ],
        "color": "#4C78A8",
        "marker": "o",
    },
    {
        "label": "CMAB",
        "paths": [
            "experiment2_cmab_longrun_round_results.json",
            "experiment2_cmab_round_results.json",
        ],
        "color": "#F58518",
        "marker": "s",
    },
    {
        "label": "CMAB + Validation",
        "paths": [
            "experiment2_cmab_trust_round_results.json",
        ],
        "color": "#54A24B",
        "marker": "^",
    },
    {
        "label": "CMAB + Validation + PGRD",
        "paths": [
            "experiment2_cmab_trust_pgrd_round_results.json",
        ],
        "color": "#E45756",
        "marker": "D",
    },
    {
        "label": "CMAB + Validation + PGRD + Incentive",
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
        "title": "Experiment 2: Coverage Rate Comparison",
        "filename": "experiment2_compare_coverage_rate.png",
    },
    {
        "key": "completion_rate",
        "ylabel": "Completion Rate",
        "title": "Experiment 2: Completion Rate Comparison",
        "filename": "experiment2_compare_completion_rate.png",
    },
    {
        "key": "cumulative_coverage_rate",
        "ylabel": "Cumulative Coverage Rate",
        "title": "Experiment 2: Cumulative Coverage Rate Comparison",
        "filename": "experiment2_compare_cumulative_coverage_rate.png",
    },
    {
        "key": "cumulative_completion_rate",
        "ylabel": "Cumulative Completion Rate",
        "title": "Experiment 2: Cumulative Completion Rate Comparison",
        "filename": "experiment2_compare_cumulative_completion_rate.png",
    },
    {
        "key": "avg_quality",
        "ylabel": "Average Realized Quality",
        "title": "Experiment 2: Average Realized Quality Comparison",
        "filename": "experiment2_compare_avg_quality.png",
    },
    {
        "key": "cumulative_avg_quality",
        "ylabel": "Cumulative Average Quality",
        "title": "Experiment 2: Cumulative Average Quality Comparison",
        "filename": "experiment2_compare_cumulative_avg_quality.png",
    },
    {
        "key": "platform_utility",
        "ylabel": "Platform Utility",
        "title": "Experiment 2: Platform Utility Comparison",
        "filename": "experiment2_compare_platform_utility.png",
    },
    {
        "key": "cumulative_platform_utility",
        "ylabel": "Cumulative Platform Utility",
        "title": "Experiment 2: Cumulative Platform Utility Comparison",
        "filename": "experiment2_compare_cumulative_platform_utility.png",
    },
    {
        "key": "retention_rate",
        "ylabel": "Worker Retention Rate",
        "title": "Experiment 2: Worker Retention Rate Comparison",
        "filename": "experiment2_compare_retention_rate.png",
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


def load_summary(filepath):
    summary_path = filepath.with_name(filepath.name.replace("_round_results.json", "_summary.json"))
    if not summary_path.exists():
        return {}
    with summary_path.open("r", encoding="utf-8") as f:
        return json.load(f)


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

        summary = load_summary(path)
        initial_total_workers = float(summary.get("initial_total_workers", 0.0))
        for item in rounds:
            active_workers = float(item.get("num_active_workers", 0.0))
            item["retention_rate"] = (
                round(active_workers / initial_total_workers, 4)
                if initial_total_workers > 0
                else 0.0
            )

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
        raise ValueError("No available experiment2 round result files were found.")

    return series


def plot_metric(series, metric):
    plt.figure(figsize=(11, 6))

    plotted_count = 0
    for config in series:
        rounds = [item for item in config["rounds"] if metric["key"] in item]
        if not rounds:
            continue

        x = [int(item["round_id"]) for item in rounds]
        y = [float(item[metric["key"]]) for item in rounds]
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
