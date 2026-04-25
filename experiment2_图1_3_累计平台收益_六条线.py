import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SERIES_CONFIG = [
    {
        "label": "B1 Random",
        "path": "experiment2_random_longrun_round_results.json",
        "color": "#4C78A8",
        "marker": "o",
    },
    {
        "label": "B2 Epsilon-First",
        "path": "experiment2_epsilon_first_longrun_round_results.json",
        "color": "#F58518",
        "marker": "s",
    },
    {
        "label": "B3 CMAB",
        "path": "experiment2_cmab_longrun_round_results.json",
        "color": "#54A24B",
        "marker": "^",
    },
    {
        "label": "B4 Trust-CMAB",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#E45756",
        "marker": "D",
    },
    {
        "label": "B5 PGRD",
        "path": "experiment2_cmab_trust_pgrd_round_results.json",
        "color": "#72B7B2",
        "marker": "v",
    },
    {
        "label": "B6 LGSC",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        "color": "#B279A2",
        "marker": "P",
    },
]

OUTPUT_FILE = "experiment2_图1_3_累计平台收益_六条线.png"


def load_round_results(path):
    with Path(path).open("r", encoding="utf-8") as f:
        records = json.load(f)
    return [item for item in records if int(item.get("num_tasks", 0)) > 0]


def main():
    plt.figure(figsize=(11, 6))

    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        x = [int(item["round_id"]) for item in rounds]
        y = [float(item["cumulative_platform_utility"]) for item in rounds]
        mark_every = max(1, len(x) // 12)

        plt.plot(
            x,
            y,
            label=config["label"],
            color=config["color"],
            marker=config["marker"],
            linewidth=2.2,
            markersize=5,
            markevery=mark_every,
        )

    plt.xlabel("Round")
    plt.ylabel("Cumulative Platform Utility")
    plt.title("Figure 1-3 Cumulative Platform Utility")
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
