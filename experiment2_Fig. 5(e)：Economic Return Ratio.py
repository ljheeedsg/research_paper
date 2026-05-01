import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


SERIES_CONFIG = [
    {
        "label": "Random",
        "csv_key": "random",
        "path": "experiment2_random_longrun_round_results.json",
        "color": "#4C78A8",
        "marker": "o",
        "zorder": 3,
    },
    {
        "label": "Explore-First",
        "csv_key": "epsilon_first",
        "path": "experiment2_epsilon_first_longrun_round_results.json",
        "color": "#F58518",
        "marker": "s",
        "zorder": 3,
    },
    {
        "label": "UCB-Greedy",
        "csv_key": "cmab",
        "path": "experiment2_cmab_longrun_round_results.json",
        "color": "#54A24B",
        "marker": "^",
        "zorder": 4,
    },
    {
        "label": "Trust-Aware",
        "csv_key": "cmab_trust",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#E45756",
        "marker": "D",
        "zorder": 4,
    },
    {
        "label": "Incentive-Aware",
        "csv_key": "cmab_trust_pgrd",
        "path": "experiment2_cmab_trust_pgrd_round_results.json",
        "color": "#72B7B2",
        "marker": "v",
        "zorder": 4,
    },
    {
        "label": "TruthRide",
        "csv_key": "truthride",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        "color": "#000000",
        "marker": "P",
        "zorder": 5,
    },
]


OUTPUT_PNG = "experiment2_Fig. 5(e)：Cost-Utility Bubble Plot.png"
OUTPUT_PDF = "experiment2_Fig. 5(e)：Cost-Utility Bubble Plot.pdf"
OUTPUT_CSV = "experiment2_Fig. 5(e)：Cost-Utility Bubble Plot.csv"


def load_round_results(path):
    with Path(path).open("r", encoding="utf-8") as f:
        records = json.load(f)
    return [item for item in records if int(item.get("num_tasks", 0)) > 0]


def compute_bubble_data(round_results):
    """
    Bubble plot data:
    X-axis: total cost = cumulative platform payment + cumulative bonus payment
    Y-axis: cumulative platform utility
    Bubble size: cumulative covered tasks if available; otherwise cumulative completed tasks;
                 otherwise cumulative number of tasks.
    """
    last = round_results[-1]

    cumulative_utility = float(last.get("cumulative_platform_utility", 0.0))
    cumulative_payment = float(last.get("cumulative_platform_payment", 0.0))
    cumulative_bonus = float(last.get("cumulative_bonus_payment", 0.0))
    total_cost = cumulative_payment + cumulative_bonus

    # 优先使用累计覆盖任务数；如果没有这个字段，就依次降级使用其他字段
    task_scale = float(
        last.get(
            "cumulative_covered_tasks",
            last.get(
                "cumulative_completed_tasks",
                last.get("cumulative_num_tasks", last.get("round_id", 1)),
            ),
        )
    )

    return total_cost, cumulative_utility, task_scale


def save_plot_data_csv(rows):
    headers = [
        "algorithm",
        "csv_key",
        "total_cost",
        "cumulative_utility",
        "task_scale",
        "bubble_size",
    ]
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def scale_bubble_sizes(values, min_size=250, max_size=1600):
    if not values:
        return []

    v_min = min(values)
    v_max = max(values)

    if v_max == v_min:
        return [(min_size + max_size) / 2 for _ in values]

    return [
        min_size + (value - v_min) / (v_max - v_min) * (max_size - min_size)
        for value in values
    ]


def set_figure_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 10.0,
            "axes.labelsize": 12.0,
            "xtick.labelsize": 9.6,
            "ytick.labelsize": 9.6,
            "legend.fontsize": 8.8,
            "axes.linewidth": 0.95,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 150,
            "savefig.dpi": 600,
        }
    )


def plot_figure():
    set_figure_style()

    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_axisbelow(True)

    costs = []
    utilities = []
    task_scales = []
    labels = []
    colors = []
    markers = []
    zorders = []
    csv_rows = []

    for config in SERIES_CONFIG:
        round_results = load_round_results(config["path"])
        total_cost, cumulative_utility, task_scale = compute_bubble_data(round_results)

        costs.append(total_cost)
        utilities.append(cumulative_utility)
        task_scales.append(task_scale)
        labels.append(config["label"])
        colors.append(config["color"])
        markers.append(config["marker"])
        zorders.append(config["zorder"])

    bubble_sizes = scale_bubble_sizes(task_scales)

    for i, label in enumerate(labels):
        ax.scatter(
            costs[i],
            utilities[i],
            s=bubble_sizes[i],
            color=colors[i],
            marker=markers[i],
            alpha=0.72,
            edgecolors="black",
            linewidth=0.85,
            zorder=zorders[i],
        )

        ax.annotate(
            label,
            (costs[i], utilities[i]),
            xytext=(6, 5),
            textcoords="offset points",
            fontsize=8.8,
            ha="left",
            va="bottom",
            zorder=zorders[i] + 1,
        )

        csv_rows.append(
            [
                label,
                SERIES_CONFIG[i]["csv_key"],
                round(costs[i], 6),
                round(utilities[i], 6),
                round(task_scales[i], 6),
                round(bubble_sizes[i], 6),
            ]
        )

    ax.axhline(0.0, color="#666666", linestyle=":", linewidth=1.0, alpha=0.85, zorder=2)
    ax.set_xlabel("Total Cost")
    ax.set_ylabel("Cumulative Utility")

    if costs:
        x_min, x_max = min(costs), max(costs)
        x_margin = max((x_max - x_min) * 0.12, 1.0)
        ax.set_xlim(x_min - x_margin, x_max + x_margin)

    if utilities:
        y_min, y_max = min(utilities), max(utilities)
        y_margin = max((y_max - y_min) * 0.12, 1.0)
        ax.set_ylim(y_min - y_margin, y_max + y_margin)

    ax.grid(
        True,
        axis="both",
        which="major",
        linestyle="--",
        linewidth=0.65,
        color="#b8b8b8",
        alpha=0.55,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.95)
    ax.spines["left"].set_linewidth(0.95)

    ax.tick_params(
        axis="both",
        which="both",
        direction="in",
        top=False,
        right=False,
        length=3.8,
        width=0.9,
    )

    legend_handles = [
        Line2D(
            [0],
            [0],
            label=config["label"],
            marker=config["marker"],
            linestyle="None",
            markersize=7,
            markerfacecolor=config["color"],
            markeredgecolor="black",
            markeredgewidth=0.8,
            alpha=0.8,
        )
        for config in SERIES_CONFIG
    ]

    ax.legend(
        handles=legend_handles,
        loc="lower right",
        ncol=2,
        frameon=True,
        fancybox=False,
        framealpha=0.9,
        facecolor="white",
        edgecolor="#666666",
        handletextpad=0.45,
        columnspacing=1.0,
        labelspacing=0.45,
    )

    fig.subplots_adjust(left=0.15, right=0.97, bottom=0.15, top=0.96)

    fig.savefig(OUTPUT_PNG, bbox_inches="tight")
    fig.savefig(OUTPUT_PDF, bbox_inches="tight")
    plt.close(fig)

    save_plot_data_csv(csv_rows)

    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    plot_figure()
