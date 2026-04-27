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
        "label": r"$\varepsilon$-First",
        "path": "experiment2_epsilon_first_longrun_round_results.json",
        "color": "#F58518",
        "marker": "s",
        "linewidth": 2.2,
    },
    {
        "label": "CMAB",
        "path": "experiment2_cmab_longrun_round_results.json",
        "color": "#54A24B",
        "marker": "^",
        "linewidth": 2.2,
    },
    {
        "label": "CMAB-Trust",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#E45756",
        "marker": "D",
        "linewidth": 2.2,
    },
    {
        "label": "CMAB-Trust-PGRD",
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
        "linewidth": 2.8,
    },
]


def load_round_results(path):
    with Path(path).open("r", encoding="utf-8") as f:
        records = json.load(f)
    return [item for item in records if int(item.get("num_tasks", 0)) > 0]


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


def _infer_ylim(all_y_values, default_bottom=0.0, padding_ratio=0.08):
    if not all_y_values:
        return default_bottom, 1.0

    y_min = min(all_y_values)
    y_max = max(all_y_values)
    if abs(y_max - y_min) < 1e-9:
        pad = max(1.0, abs(y_max) * padding_ratio)
    else:
        pad = (y_max - y_min) * padding_ratio

    bottom = min(default_bottom, y_min - pad)
    top = y_max + pad
    if y_min >= 0:
        bottom = max(0.0, bottom)
    return bottom, top


def plot_six_line_figure(
    metric_key,
    output_file,
    ylabel,
    ylim=None,
    legend_loc="best",
    legend_ncol=2,
):
    set_paper_style()

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    all_y_values = []
    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        x = [int(item["round_id"]) for item in rounds]
        y = [float(item[metric_key]) for item in rounds]
        all_y_values.extend(y)
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
    ax.set_ylabel(ylabel)
    ax.set_xlim(left=0)

    auto_bottom, auto_top = _infer_ylim(all_y_values)
    if ylim is None:
        ax.set_ylim(auto_bottom, auto_top)
    else:
        bottom, top = ylim
        if bottom is None:
            bottom = auto_bottom
        if top is None:
            top = auto_top
        ax.set_ylim(bottom, top)

    ax.grid(
        True,
        which="major",
        linestyle="--",
        linewidth=0.7,
        alpha=0.28,
    )

    ax.legend(
        loc=legend_loc,
        frameon=True,
        fancybox=False,
        framealpha=0.95,
        edgecolor="black",
        ncol=legend_ncol,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="in", length=4, width=1.0)

    fig.tight_layout()
    fig.savefig(output_file, dpi=600, bbox_inches="tight")
    fig.savefig(output_file.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)

    print(f"Saved {output_file}")
    print(f"Saved {output_file.replace('.png', '.pdf')}")


def plot_metric_relation_figure(
    x_key,
    y_key,
    output_file,
    xlabel,
    ylabel,
    xlim=None,
    ylim=None,
    legend_loc="best",
    legend_ncol=2,
):
    set_paper_style()

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    all_x_values = []
    all_y_values = []
    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        filtered_rounds = [
            item for item in rounds
            if x_key in item and y_key in item
        ]
        x = [float(item[x_key]) for item in filtered_rounds]
        y = [float(item[y_key]) for item in filtered_rounds]
        all_x_values.extend(x)
        all_y_values.extend(y)
        mark_every = max(1, len(x) // 10) if x else 1

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
            alpha=0.95,
        )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    auto_x_bottom, auto_x_top = _infer_ylim(all_x_values)
    auto_y_bottom, auto_y_top = _infer_ylim(all_y_values)

    if xlim is None:
        ax.set_xlim(auto_x_bottom, auto_x_top)
    else:
        left, right = xlim
        if left is None:
            left = auto_x_bottom
        if right is None:
            right = auto_x_top
        ax.set_xlim(left, right)

    if ylim is None:
        ax.set_ylim(auto_y_bottom, auto_y_top)
    else:
        bottom, top = ylim
        if bottom is None:
            bottom = auto_y_bottom
        if top is None:
            top = auto_y_top
        ax.set_ylim(bottom, top)

    ax.grid(
        True,
        which="major",
        linestyle="--",
        linewidth=0.7,
        alpha=0.28,
    )

    ax.legend(
        loc=legend_loc,
        frameon=True,
        fancybox=False,
        framealpha=0.95,
        edgecolor="black",
        ncol=legend_ncol,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="in", length=4, width=1.0)

    fig.tight_layout()
    fig.savefig(output_file, dpi=600, bbox_inches="tight")
    fig.savefig(output_file.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)

    print(f"Saved {output_file}")
    print(f"Saved {output_file.replace('.png', '.pdf')}")


def plot_final_scatter_figure(
    x_key,
    y_key,
    output_file,
    xlabel,
    ylabel,
    xlim=None,
    ylim=None,
    annotate=True,
):
    set_paper_style()

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x_values = []
    y_values = []
    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        if not rounds:
            continue
        final_point = rounds[-1]
        x = float(final_point[x_key])
        y = float(final_point[y_key])
        x_values.append(x)
        y_values.append(y)

        ax.scatter(
            x,
            y,
            s=90,
            color=config["color"],
            marker=config["marker"],
            edgecolors="black",
            linewidths=0.9,
            zorder=3,
            label=config["label"],
        )

        if annotate:
            ax.annotate(
                config["label"],
                (x, y),
                xytext=(6, 6),
                textcoords="offset points",
                fontsize=10,
            )

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    auto_x_bottom, auto_x_top = _infer_ylim(x_values)
    auto_y_bottom, auto_y_top = _infer_ylim(y_values)

    if xlim is None:
        ax.set_xlim(auto_x_bottom, auto_x_top)
    else:
        left, right = xlim
        if left is None:
            left = auto_x_bottom
        if right is None:
            right = auto_x_top
        ax.set_xlim(left, right)

    if ylim is None:
        ax.set_ylim(auto_y_bottom, auto_y_top)
    else:
        bottom, top = ylim
        if bottom is None:
            bottom = auto_y_bottom
        if top is None:
            top = auto_y_top
        ax.set_ylim(bottom, top)

    ax.grid(
        True,
        which="major",
        linestyle="--",
        linewidth=0.7,
        alpha=0.28,
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="in", length=4, width=1.0)

    fig.tight_layout()
    fig.savefig(output_file, dpi=600, bbox_inches="tight")
    fig.savefig(output_file.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)

    print(f"Saved {output_file}")
    print(f"Saved {output_file.replace('.png', '.pdf')}")
