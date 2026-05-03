import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


WORKER_OPTIONS_FILE = "experiment2_worker_options.json"
OUTPUT_PNG = "experiment2_Fig. 18：Worker Participation Length.png"
OUTPUT_PDF = "experiment2_Fig. 18：Worker Participation Length.pdf"
OUTPUT_CSV = "experiment2_Fig. 18：Worker Participation Length.csv"
LEGEND_MODE = "manual"
LEGEND_LOC = "upper center"
LEGEND_BBOX_TO_ANCHOR = (0.5, 0.98)
LEGEND_NCOL = 3
YLIM_MODE = "auto"
YLIM = (0, 20)
YTICK_STEP = 2
BAR_WIDTH = 0.22

ALGORITHM_CONFIG = [
    {
        "label": "Trust-Aware",
        "csv_key": "Trust-Aware",
        "path": "experiment2_cmab_trust_round_results_all_runs.json",
    },
    {
        "label": "Membership-Aware",
        "csv_key": "Membership-Aware",
        "path": "experiment2_cmab_trust_pgrd_round_results_all_runs.json",
    },
    {
        "label": "TruthRide",
        "csv_key": "TruthRide",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results_all_runs.json",
    },
]

CATEGORY_CONFIG = [
    {
        "key": "trusted",
        "label": "Trusted",
        "csv_key": "trusted_participation",
        "color": "#1B9E77",
        "hatch": "//",
    },
    {
        "key": "unknown",
        "label": "Unknown",
        "csv_key": "unknown_participation",
        "color": "#D95F02",
        "hatch": "\\\\",
    },
    {
        "key": "malicious",
        "label": "Malicious",
        "csv_key": "malicious_participation",
        "color": "#7570B3",
        "hatch": "xx",
    },
]


def load_worker_categories(path):
    with Path(path).open("r", encoding="utf-8") as f:
        worker_options = json.load(f)

    worker_category_map = {}
    for worker in worker_options.values():
        worker_category_map[int(worker["worker_id"])] = worker["init_category"]
    return worker_category_map


def load_all_runs(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def compute_run_participation_means(run_payload, worker_category_map):
    selected_counter = Counter()
    for round_result in run_payload["round_results"]:
        for worker_id in round_result.get("selected_workers", []):
            selected_counter[int(worker_id)] += 1

    grouped_values = defaultdict(list)
    for worker_id, category in worker_category_map.items():
        grouped_values[category].append(selected_counter.get(worker_id, 0))

    return {
        category: round(float(np.mean(grouped_values[category])), 4)
        if grouped_values[category] else 0.0
        for category in grouped_values
    }


def compute_algorithm_participation(path, worker_category_map):
    all_runs_payload = load_all_runs(path)
    per_run_means = []
    for run_payload in all_runs_payload:
        per_run_means.append(compute_run_participation_means(run_payload, worker_category_map))

    averaged = {}
    for category in ["trusted", "unknown", "malicious"]:
        values = [run_mean.get(category, 0.0) for run_mean in per_run_means]
        averaged[category] = round(float(np.mean(values)), 4) if values else 0.0
    return averaged


def save_plot_data_csv(rows):
    headers = ["algorithm"] + [config["csv_key"] for config in CATEGORY_CONFIG]
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(
                [
                    row["algorithm"],
                    row["trusted"],
                    row["unknown"],
                    row["malicious"],
                ]
            )


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


def plot_figure(rows):
    set_figure_style()

    algorithms = [row["algorithm"] for row in rows]
    x = np.arange(len(algorithms))

    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_axisbelow(True)

    all_values = []
    for idx, category_config in enumerate(CATEGORY_CONFIG):
        offsets = x + (idx - 1) * BAR_WIDTH
        values = [row[category_config["key"]] for row in rows]
        all_values.extend(values)

        ax.bar(
            offsets,
            values,
            width=BAR_WIDTH,
            label=category_config["label"],
            color=category_config["color"],
            edgecolor="#333333",
            linewidth=0.8,
            hatch=category_config["hatch"],
            alpha=0.9,
            zorder=3,
        )

    ax.set_xlabel("Algorithm")
    ax.set_ylabel("Average Participation Rounds")
    ax.set_xticks(x)
    ax.set_xticklabels(algorithms)

    if YLIM_MODE == "manual":
        ax.set_ylim(*YLIM)
        ax.set_yticks(range(YLIM[0], YLIM[1] + 1, YTICK_STEP))
    elif all_values:
        y_min = 0.0
        y_max = max(all_values)
        margin = max(y_max * 0.12, 0.8)
        ax.set_ylim(y_min, y_max + margin)

    ax.grid(
        True,
        axis="y",
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
    ax.tick_params(axis="both", which="both", direction="in", top=False, right=False, length=3.8, width=0.9)

    legend_kwargs = {
        "loc": LEGEND_LOC if LEGEND_MODE == "manual" else "best",
        "ncol": LEGEND_NCOL,
        "frameon": True,
        "fancybox": False,
        "framealpha": 0.9,
        "facecolor": "white",
        "edgecolor": "#666666",
        "handlelength": 1.8,
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


def main():
    worker_category_map = load_worker_categories(WORKER_OPTIONS_FILE)
    rows = []

    for algorithm_config in ALGORITHM_CONFIG:
        averaged = compute_algorithm_participation(
            algorithm_config["path"],
            worker_category_map,
        )
        rows.append(
            {
                "algorithm": algorithm_config["csv_key"],
                "trusted": averaged["trusted"],
                "unknown": averaged["unknown"],
                "malicious": averaged["malicious"],
            }
        )

    save_plot_data_csv(rows)
    plot_figure(rows)

    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
