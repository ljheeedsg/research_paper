import json
from pathlib import Path

import matplotlib.pyplot as plt


SERIES_CONFIG = [
    {
        "label": "Random",
        "path": "experiment2_random_round_results.json",
        "color": "#4C78A8",
        "marker": "o",
    },
    {
        "label": "CMAB",
        "path": "experiment2_cmab_round_results.json",
        "color": "#F58518",
        "marker": "s",
    },
    {
        "label": "CMAB + Validation",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#54A24B",
        "marker": "^",
    },
    {
        "label": "All Added",
        "path": "experiment2_cmab_trust_pgrd_round_results.json",
        "color": "#E45756",
        "marker": "D",
    },
]

OUTPUT_FILE = "experiment2_compare_cumulative_avg_quality.png"


def load_round_results(filepath):
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Missing result file: {filepath}")

    with path.open("r", encoding="utf-8") as f:
        round_results = json.load(f)

    valid_rounds = [item for item in round_results if int(item.get("num_tasks", 0)) > 0]
    if not valid_rounds:
        raise ValueError(f"No valid rounds found in: {filepath}")

    return valid_rounds


def plot_cumulative_avg_quality():
    plt.figure(figsize=(11, 6))

    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        x = [int(item["round_id"]) for item in rounds]
        y = [float(item["cumulative_avg_quality"]) for item in rounds]
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

    plt.xlabel("Round")
    plt.ylabel("Cumulative Average Quality")
    plt.title("Experiment 2: Cumulative Average Quality Comparison")
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved comparison plot to {OUTPUT_FILE}")


if __name__ == "__main__":
    plot_cumulative_avg_quality()
