import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


ROUND_RESULTS_FILE = "experiment2_cmab_trust_pgrd_lgsc_round_results.json"
OUTPUT_PNG = "experiment2_Fig. 9：可信工人比例变化.png"
OUTPUT_PDF = "experiment2_Fig. 9：可信工人比例变化.pdf"
OUTPUT_CSV = "experiment2_Fig. 9：可信工人比例变化.csv"
SMOOTH_WINDOW = 1
LEGEND_MODE = "manual"
LEGEND_LOC = "lower right"
LEGEND_BBOX_TO_ANCHOR = (0.97, 0.03)
LEGEND_NCOL = 1
YLIM_MODE = "manual"
YLIM = (0.0, 1.0)

SERIES_CONFIG = [
    {
        "label": "TruthRide",
        "csv_key": "trusted_worker_ratio",
        "color": "#000000",
        "marker": "P",
        "linestyle": "-",
        "linewidth": 2.9,
        "markersize": 4.8,
        "alpha": 1.0,
        "zorder": 5,
    },
]


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
            "font.size": 10.0,
            "axes.labelsize": 12.0,
            "xtick.labelsize": 9.6,
            "ytick.labelsize": 9.6,
            "legend.fontsize": 9.2,
            "axes.linewidth": 0.95,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 150,
            "savefig.dpi": 600,
        }
    )


def plot_figure():
    set_figure_style()

    round_results = load_round_results(ROUND_RESULTS_FILE)
    rounds = [int(item["round_id"]) for item in round_results]
    raw_ratio = [
        round(
            float(item["trusted_count"]) /
            max(
                1,
                int(item["trusted_count"])
                + int(item["unknown_count"])
                + int(item["malicious_count"]),
            ),
            4,
        )
        for item in round_results
    ]
    ratio_values = moving_average(raw_ratio, SMOOTH_WINDOW)

    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_axisbelow(True)
    csv_series_rows = [ratio_values]
    legend_handles = []

    config = SERIES_CONFIG[0]
    ax.plot(
        rounds,
        ratio_values,
        label=config["label"],
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

    ax.set_xlabel("Round")
    ax.set_ylabel("Trusted Worker Ratio")
    ax.set_xlim(0, 145)
    ax.set_xticks(range(0, 141, 20))
    if YLIM_MODE == "manual":
        ax.set_ylim(*YLIM)
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

    legend_kwargs = {
        "handles": legend_handles,
        "loc": LEGEND_LOC if LEGEND_MODE == "manual" else "best",
        "ncol": LEGEND_NCOL,
        "frameon": True,
        "fancybox": False,
        "framealpha": 0.9,
        "facecolor": "white",
        "edgecolor": "#666666",
        "handlelength": 2.2,
        "handletextpad": 0.5,
        "columnspacing": 1.2,
        "labelspacing": 0.5,
    }
    if LEGEND_MODE == "manual":
        legend_kwargs["bbox_to_anchor"] = LEGEND_BBOX_TO_ANCHOR
    ax.legend(**legend_kwargs)

    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.16, top=0.96)
    fig.savefig(OUTPUT_PNG, bbox_inches="tight")
    fig.savefig(OUTPUT_PDF, bbox_inches="tight")
    plt.close(fig)
    save_plot_data_csv(rounds, csv_series_rows)

    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    plot_figure()
