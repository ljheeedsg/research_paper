import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


WORKER_OPTIONS_FILE = "experiment2_worker_options.json"
OUTPUT_PNG = "experiment2_Fig. 15：Seed Trusted Worker Retention Rate.png"
OUTPUT_PDF = "experiment2_Fig. 15：Seed Trusted Worker Retention Rate.pdf"
OUTPUT_CSV = "experiment2_Fig. 15：Seed Trusted Worker Retention Rate.csv"
SMOOTH_WINDOW = 1
LEGEND_MODE = "manual"
LEGEND_LOC = "upper center"
LEGEND_BBOX_TO_ANCHOR = (0.65, 0.98)
LEGEND_NCOL = 2
YLIM_MODE = "manual"
YLIM = (0.0, 1.02)

SERIES_CONFIG = [
    {
        "label": "Trust-Aware",
        "csv_key": "trust_aware",
        "path": "experiment2_cmab_trust_round_results_all_runs.json",
        "color": "#E45756",
        "marker": "D",
        "linestyle": "-",
        "linewidth": 2.1,
        "markersize": 4.2,
        "alpha": 0.98,
        "zorder": 4,
    },
    {
        "label": "Membership-Aware",
        "csv_key": "membership_aware",
        "path": "experiment2_cmab_trust_pgrd_round_results_all_runs.json",
        "color": "#72B7B2",
        "marker": "v",
        "linestyle": "-",
        "linewidth": 2.1,
        "markersize": 4.4,
        "alpha": 0.98,
        "zorder": 4,
    },
    {
        "label": "TruthRide",
        "csv_key": "truthride",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results_all_runs.json",
        "color": "#000000",
        "marker": "P",
        "linestyle": "-",
        "linewidth": 2.9,
        "markersize": 4.8,
        "alpha": 1.0,
        "zorder": 5,
    },
]


def load_seed_trusted_worker_ids(path):
    with Path(path).open("r", encoding="utf-8") as f:
        worker_options = json.load(f)

    return {
        int(worker["worker_id"])
        for worker in worker_options.values()
        if worker.get("init_category") == "trusted"
    }


def load_all_runs(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


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


def compute_seed_retention_curve(all_runs_payload, seed_trusted_ids):
    seed_count = max(1, len(seed_trusted_ids))
    per_run_curves = []
    round_axis = None

    for run_payload in all_runs_payload:
        round_results = [
            item for item in run_payload["round_results"]
            if int(item.get("num_tasks", 0)) > 0
        ]
        rounds = [int(item["round_id"]) for item in round_results]
        if round_axis is None:
            round_axis = rounds

        left_seed_ids = set()
        retention_values = []
        for item in round_results:
            left_ids = {
                int(worker_id)
                for worker_id in item.get("left_worker_ids_this_round", [])
            }
            left_seed_ids.update(left_ids & seed_trusted_ids)
            retained = seed_count - len(left_seed_ids)
            retention_values.append(round(retained / seed_count, 4))

        per_run_curves.append(retention_values)

    if not per_run_curves:
        return [], []

    averaged_curve = []
    for idx in range(len(per_run_curves[0])):
        averaged_curve.append(
            round(sum(curve[idx] for curve in per_run_curves) / len(per_run_curves), 4)
        )

    return round_axis, averaged_curve


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

    seed_trusted_ids = load_seed_trusted_worker_ids(WORKER_OPTIONS_FILE)

    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_axisbelow(True)
    csv_rounds = None
    csv_series_rows = []
    legend_handles = []

    for config in SERIES_CONFIG:
        all_runs_payload = load_all_runs(config["path"])
        rounds, raw_values = compute_seed_retention_curve(
            all_runs_payload,
            seed_trusted_ids,
        )
        values = moving_average(raw_values, SMOOTH_WINDOW)

        if csv_rounds is None:
            csv_rounds = rounds
        csv_series_rows.append(values)

        ax.plot(
            rounds,
            values,
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
    ax.set_ylabel("Seed Trusted Worker Retention Rate")
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
    save_plot_data_csv(csv_rounds, csv_series_rows)

    print(f"Seed trusted worker count: {len(seed_trusted_ids)}")
    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    plot_figure()
