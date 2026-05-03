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
        "linestyle": "-",
        "linewidth": 1.8,
        "markersize": 4.2,
        "alpha": 0.95,
        "zorder": 3,
    },
    {
        "label": "Explore-First",
        "csv_key": "epsilon_first",
        "path": "experiment2_epsilon_first_longrun_round_results.json",
        "color": "#F58518",
        "marker": "s",
        "linestyle": "-",
        "linewidth": 1.8,
        "markersize": 4.0,
        "alpha": 0.95,
        "zorder": 3,
    },
    {
        "label": "UCB-Greedy",
        "csv_key": "cmab",
        "path": "experiment2_cmab_longrun_round_results.json",
        "color": "#54A24B",
        "marker": "^",
        "linestyle": "-",
        "linewidth": 1.8,
        "markersize": 4.4,
        "alpha": 0.95,
        "zorder": 4,
    },
    {
        "label": "Trust-Aware",
        "csv_key": "cmab_trust",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#E45756",
        "marker": "D",
        "linestyle": "-",
        "linewidth": 2.0,
        "markersize": 4.2,
        "alpha": 0.98,
        "zorder": 4,
    },
    {
        "label": "Incentive-Aware",
        "csv_key": "cmab_trust_pgrd",
        "path": "experiment2_cmab_trust_pgrd_round_results.json",
        "color": "#72B7B2",
        "marker": "v",
        "linestyle": "-",
        "linewidth": 2.1,
        "markersize": 4.3,
        "alpha": 0.98,
        "zorder": 4,
    },
    {
        "label": "TruthRide",
        "csv_key": "truthride",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        "color": "#000000",
        "marker": "P",
        "linestyle": "-",
        "linewidth": 2.9,
        "markersize": 4.8,
        "alpha": 1.0,
        "zorder": 5,
    },
]


OUTPUT_PNG = "experiment2_Fig. 11补充：每轮覆盖率与完成率.png"
OUTPUT_PDF = "experiment2_Fig. 11补充：每轮覆盖率与完成率.pdf"
OUTPUT_CSV = "experiment2_Fig. 11补充：每轮覆盖率与完成率.csv"
SMOOTH_WINDOW = 5


def load_round_results(path):
    with Path(path).open("r", encoding="utf-8") as f:
        records = json.load(f)
    return [item for item in records if int(item.get("num_tasks", 0)) > 0]


def moving_average(values, window):
    if window <= 1 or len(values) <= 2:
        return [round(float(value), 4) for value in values]

    half_window = window // 2
    smoothed = []
    for idx in range(len(values)):
        start = max(0, idx - half_window)
        end = min(len(values), idx + half_window + 1)
        smoothed.append(round(sum(values[start:end]) / (end - start), 4))
    return smoothed


def save_plot_data_csv(rounds, coverage_rows, completion_rows):
    headers = ["round"]
    headers.extend([f"coverage_{config['csv_key']}" for config in SERIES_CONFIG])
    headers.extend([f"completion_{config['csv_key']}" for config in SERIES_CONFIG])

    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for idx, round_id in enumerate(rounds):
            row = [round_id]
            row.extend(values[idx] for values in coverage_rows)
            row.extend(values[idx] for values in completion_rows)
            writer.writerow(row)


def set_figure_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 10.0,
            "axes.labelsize": 11.5,
            "xtick.labelsize": 9.4,
            "ytick.labelsize": 9.4,
            "legend.fontsize": 8.8,
            "axes.linewidth": 0.95,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 150,
            "savefig.dpi": 600,
        }
    )


def style_axis(ax, ylabel):
    ax.set_facecolor("white")
    ax.set_axisbelow(True)
    ax.set_xlabel("Round")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, 145)
    ax.set_xticks(range(0, 141, 20))
    ax.set_ylim(0.0, 1.05)
    ax.set_yticks([i / 10 for i in range(0, 11, 2)])
    ax.grid(
        True,
        axis="y",
        which="major",
        linestyle="--",
        linewidth=0.65,
        color="#b8b8b8",
        alpha=0.55,
    )
    ax.grid(
        True,
        axis="x",
        which="major",
        linestyle=":",
        linewidth=0.5,
        color="#c7c7c7",
        alpha=0.35,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.95)
    ax.spines["left"].set_linewidth(0.95)
    ax.tick_params(axis="both", which="both", direction="in", top=False, right=False, length=3.8, width=0.9)


def plot_metric(ax, metric_key):
    rounds_for_csv = None
    series_rows = []
    legend_handles = []

    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        x = [int(item["round_id"]) for item in rounds]
        raw_y = [float(item[metric_key]) for item in rounds]
        y = moving_average(raw_y, SMOOTH_WINDOW)

        if rounds_for_csv is None:
            rounds_for_csv = x
        series_rows.append(y)

        ax.plot(
            x,
            y,
            color=config["color"],
            marker=config["marker"],
            linestyle=config["linestyle"],
            linewidth=config["linewidth"],
            markersize=config["markersize"],
            markevery=1,
            markerfacecolor="white",
            markeredgewidth=0.95,
            alpha=config["alpha"],
            zorder=config["zorder"],
            solid_capstyle="round",
            solid_joinstyle="round",
            antialiased=True,
        )
        legend_handles.append(
            Line2D(
                [0],
                [0],
                label=config["label"],
                color=config["color"],
                linestyle=config["linestyle"],
                linewidth=config["linewidth"],
                marker=config["marker"],
                markersize=config["markersize"],
                markerfacecolor="white",
                markeredgewidth=0.95,
            )
        )

    return rounds_for_csv, series_rows, legend_handles


def plot_figure():
    set_figure_style()

    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.6), sharex=True, sharey=True)
    fig.patch.set_facecolor("white")

    coverage_rounds, coverage_rows, legend_handles = plot_metric(axes[0], "coverage_rate")
    completion_rounds, completion_rows, _ = plot_metric(axes[1], "completion_rate")

    style_axis(axes[0], "Per-Round Coverage Rate")
    style_axis(axes[1], "Per-Round Completion Rate")
    axes[0].set_title("(a) Coverage")
    axes[1].set_title("(b) Completion")

    fig.legend(
        handles=legend_handles,
        loc="lower center",
        ncol=3,
        frameon=True,
        fancybox=False,
        framealpha=0.9,
        facecolor="white",
        edgecolor="#666666",
        handlelength=2.2,
        handletextpad=0.5,
        columnspacing=1.2,
        bbox_to_anchor=(0.5, -0.01),
    )

    fig.subplots_adjust(left=0.08, right=0.995, bottom=0.22, top=0.92, wspace=0.14)
    fig.savefig(OUTPUT_PNG, bbox_inches="tight")
    fig.savefig(OUTPUT_PDF, bbox_inches="tight")
    plt.close(fig)

    if coverage_rounds != completion_rounds:
        raise ValueError("Coverage and completion rounds do not align.")
    save_plot_data_csv(coverage_rounds, coverage_rows, completion_rows)

    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    plot_figure()
