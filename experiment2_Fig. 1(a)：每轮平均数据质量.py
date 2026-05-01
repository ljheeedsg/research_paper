import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SERIES_CONFIG = [
    {
        "label": "Random",
        "csv_key": "random",
        "path": "experiment2_random_longrun_round_results.json",
        "color": "#1f77b4",
        "marker": "o",
        "linewidth": 1.15,
        "markersize": 3.6,
        "zorder": 3,
    },
    {
        "label": r"$\epsilon$-First",
        "csv_key": "epsilon_first",
        "path": "experiment2_epsilon_first_longrun_round_results.json",
        "color": "#ff7f0e",
        "marker": "s",
        "linewidth": 1.15,
        "markersize": 3.6,
        "zorder": 3,
    },
    {
        "label": "CMAB",
        "csv_key": "cmab",
        "path": "experiment2_cmab_longrun_round_results.json",
        "color": "#2ca02c",
        "marker": "^",
        "linewidth": 1.15,
        "markersize": 3.8,
        "zorder": 4,
    },
    {
        "label": "CMAB-Trust",
        "csv_key": "cmab_trust",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#d62728",
        "marker": "D",
        "linewidth": 1.15,
        "markersize": 3.6,
        "zorder": 4,
    },
    {
        "label": "CMAB-Trust-PGRD",
        "csv_key": "cmab_trust_pgrd",
        "path": "experiment2_cmab_trust_pgrd_round_results.json",
        "color": "#17becf",
        "marker": "v",
        "linewidth": 1.15,
        "markersize": 3.8,
        "zorder": 4,
    },
    {
        "label": "TruthRide",
        "csv_key": "truthride",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        "color": "#000000",
        "marker": "P",
        "linewidth": 1.9,
        "markersize": 4.2,
        "zorder": 5,
    },
]


OUTPUT_PNG = "experiment2_Fig. 1(a)：每轮平均数据质量.png"
OUTPUT_PDF = "experiment2_Fig. 1(a)：每轮平均数据质量.pdf"
OUTPUT_CSV = "experiment2_Fig. 1(a)：每轮平均数据质量.csv"
METRIC_KEY = "avg_quality"
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


def save_plot_data_csv(rounds, series_rows):
    headers = ["round"] + [config["csv_key"] for config in SERIES_CONFIG]
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for idx, round_id in enumerate(rounds):
            row = [round_id]
            for values in series_rows:
                row.append(values[idx])
            writer.writerow(row)


def set_figure_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 9.5,
            "axes.labelsize": 11.5,
            "xtick.labelsize": 9.2,
            "ytick.labelsize": 9.2,
            "legend.fontsize": 8.8,
            "axes.linewidth": 0.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 600,
        }
    )


def plot_figure():
    set_figure_style()

    fig, ax = plt.subplots(figsize=(6.3, 4.25))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    csv_rounds = None
    csv_series_rows = []

    for config in SERIES_CONFIG:
        rounds = load_round_results(config["path"])
        x = [int(item["round_id"]) for item in rounds]
        y_raw = [float(item[METRIC_KEY]) for item in rounds]
        y = moving_average(y_raw, SMOOTH_WINDOW)
        mark_every = max(1, len(x) // 12)

        if csv_rounds is None:
            csv_rounds = x
        csv_series_rows.append(y)

        ax.plot(
            x,
            y,
            label=config["label"],
            color=config["color"],
            marker=config["marker"],
            linewidth=config["linewidth"],
            markersize=config["markersize"],
            markevery=mark_every,
            markerfacecolor="white",
            markeredgewidth=0.75,
            zorder=config["zorder"],
        )

    ax.set_xlabel("Round")
    ax.set_ylabel("Per-Round Average Quality")
    ax.set_xlim(0, 145)
    ax.set_ylim(0.0, 1.02)

    ax.grid(True, which="major", linestyle="--", linewidth=0.5, color="#b6b6b6", alpha=0.65)

    for side in ["top", "right", "bottom", "left"]:
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(0.8)

    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True, length=3.0, width=0.8)

    ax.legend(
        loc="lower right",
        ncol=2,
        frameon=True,
        fancybox=False,
        framealpha=1.0,
        edgecolor="black",
        borderpad=0.28,
        handlelength=1.8,
        handletextpad=0.4,
        columnspacing=0.7,
        labelspacing=0.3,
    )

    fig.tight_layout(pad=0.4)
    fig.savefig(OUTPUT_PNG, bbox_inches="tight")
    fig.savefig(OUTPUT_PDF, bbox_inches="tight")
    plt.close(fig)
    save_plot_data_csv(csv_rounds, csv_series_rows)

    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    plot_figure()
