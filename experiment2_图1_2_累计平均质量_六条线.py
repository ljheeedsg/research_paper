import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SERIES_CONFIG = [
    {
        "label": "Random",
        "path": "experiment2_random_longrun_round_results.json",
        "color": "#4C78A8",
        "marker": "o",
        "linewidth": 2.2,
    },
    {
        "label": "Explore-First",
        "path": "experiment2_epsilon_first_longrun_round_results.json",
        "color": "#F58518",
        "marker": "s",
        "linewidth": 2.2,
    },
    {
        "label": "UCB-Greedy",
        "path": "experiment2_cmab_longrun_round_results.json",
        "color": "#54A24B",
        "marker": "^",
        "linewidth": 2.2,
    },
    {
        "label": "Trust-Aware",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#E45756",
        "marker": "D",
        "linewidth": 2.2,
    },
    {
        "label": "Membership-Aware",
        "path": "experiment2_cmab_trust_pgrd_round_results.json",
        "color": "#72B7B2",
        "marker": "v",
        "linewidth": 2.2,
    },
    {
        "label": "TruthRide",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        "color": "#000000",
        "marker": "P",
        "linewidth": 2.6,
    },
]

OUTPUT_FILE = "experiment2_图1_2_累计平均质量_六条线.png"


def load_round_results(path):
    with Path(path).open("r", encoding="utf-8") as f:
        records = json.load(f)

    return [
        item for item in records
        if int(item.get("num_tasks", 0)) > 0
    ]


def set_paper_style():
    plt.rcParams.update({
        "font.family": "Times New Roman",
        "font.size": 13,
        "axes.labelsize": 15,
        "axes.titlesize": 15,
        "xtick.labelsize": 12,
        "ytick.labelsize": 12,
        "legend.fontsize": 11,
        "axes.linewidth": 1.1,
        "lines.linewidth": 2.2,
        "savefig.dpi": 600,
        "figure.dpi": 150,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def main():
    set_paper_style()

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        x = [int(item["round_id"]) for item in rounds]
        y = [float(item["cumulative_avg_quality"]) for item in rounds]
        mark_every = max(1, len(x) // 10)

        ax.plot(
            x,
            y,
            label=config["label"],
            color=config["color"],
            marker=config["marker"],
            linewidth=config["linewidth"],
            markersize=5.2,
            markevery=mark_every,
            markerfacecolor="white",
            markeredgewidth=1.2,
        )

    ax.set_xlabel("Round")
    ax.set_ylabel("Cumulative Average Quality")

    ax.set_xlim(left=0)
    ax.set_ylim(0.35, 1.02)

    ax.grid(
        True,
        which="major",
        linestyle="--",
        linewidth=0.7,
        alpha=0.28,
    )

    ax.legend(
        loc="lower right",
        frameon=True,
        fancybox=False,
        framealpha=0.95,
        edgecolor="black",
        ncol=2,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.tick_params(
        direction="in",
        length=4,
        width=1.0,
    )

    fig.tight_layout()

    fig.savefig(OUTPUT_FILE, dpi=600, bbox_inches="tight")
    fig.savefig(OUTPUT_FILE.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)

    print(f"Saved {OUTPUT_FILE}")
    print(f"Saved {OUTPUT_FILE.replace('.png', '.pdf')}")


if __name__ == "__main__":
    main()