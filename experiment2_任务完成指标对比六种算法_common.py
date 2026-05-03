import csv
import json
import shutil
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from experiment2_重构_main import run_experiment


ALGORITHM_NAMES = ["random", "epsilon_first", "cmab", "trust", "pgrd", "lgsc"]
ALGORITHM_LABELS = {
    "random": "Random",
    "epsilon_first": "Explore-First",
    "cmab": "UCB-Greedy",
    "trust": "Trust-Aware",
    "pgrd": "Membership-Aware",
    "lgsc": "TruthRide",
}

RUNS_PER_ALGORITHM = 10
RESULTS_BUNDLE_FILE = "experiment2_对比六种算法_results.json"
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"

COLOR_LIST = ["#808080", "#FF9999", "#4C78A8", "#F58518", "#54A24B", "#E45756"]
MARKER_LIST = ["o", "x", "s", "^", "D", "v"]

FIGURE_SPECS = {
    "fig33": {
        "output_png": "experiment2_Fig. 33：任务覆盖率对比.png",
        "output_pdf": "experiment2_Fig. 33：任务覆盖率对比.pdf",
        "output_csv": "experiment2_Fig. 33：任务覆盖率对比.csv",
        "ylabel": "Task Coverage Rate",
        "metric_key": "coverage_rate",
        "smooth_window": 5,
        "ylim": (0.0, 1.05),
        "legend_loc": "lower right",
    },
    "fig34": {
        "output_png": "experiment2_Fig. 34：任务完成率对比.png",
        "output_pdf": "experiment2_Fig. 34：任务完成率对比.pdf",
        "output_csv": "experiment2_Fig. 34：任务完成率对比.csv",
        "ylabel": "Task Completion Rate",
        "metric_key": "completion_rate",
        "smooth_window": 5,
        "ylim": (0.0, 1.05),
        "legend_loc": "lower right",
    },
    "fig33_supp": {
        "output_png": "experiment2_Fig. 33补充：累计任务覆盖率对比.png",
        "output_pdf": "experiment2_Fig. 33补充：累计任务覆盖率对比.pdf",
        "output_csv": "experiment2_Fig. 33补充：累计任务覆盖率对比.csv",
        "ylabel": "Cumulative Task Coverage Rate",
        "metric_key": "cumulative_coverage_rate",
        "smooth_window": 1,
        "ylim": (0.0, 1.05),
        "legend_loc": "lower right",
    },
    "fig34_supp": {
        "output_png": "experiment2_Fig. 34补充：累计任务完成率对比.png",
        "output_pdf": "experiment2_Fig. 34补充：累计任务完成率对比.pdf",
        "output_csv": "experiment2_Fig. 34补充：累计任务完成率对比.csv",
        "ylabel": "Cumulative Task Completion Rate",
        "metric_key": "cumulative_completion_rate",
        "smooth_window": 1,
        "ylim": (0.0, 1.05),
        "legend_loc": "lower right",
    },
}


def save_json(payload, path):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_json(path):
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
            "legend.fontsize": 9.0,
            "axes.linewidth": 0.95,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.dpi": 150,
            "savefig.dpi": 600,
        }
    )


def algorithm_label(algo_name):
    return ALGORITHM_LABELS.get(algo_name, algo_name)


def save_plot_data_csv(rounds, series_rows, labels, output_csv):
    headers = ["round"] + labels
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for idx, round_id in enumerate(rounds):
            row = [round_id]
            row.extend(values[idx] for values in series_rows)
            writer.writerow(row)


def compact_round_entry(entry):
    return {
        "round_id": int(entry["round_id"]),
        "num_tasks": int(entry.get("num_tasks", 0)),
        "num_completed": int(entry.get("num_completed", 0)),
        "coverage_rate": round(float(entry.get("coverage_rate", 0.0)), 4),
        "completion_rate": round(float(entry.get("completion_rate", 0.0)), 4),
        "avg_quality": round(float(entry.get("avg_quality", 0.0)), 4),
        "platform_utility": round(float(entry.get("platform_utility", 0.0)), 4),
        "cumulative_coverage_rate": round(float(entry.get("cumulative_coverage_rate", 0.0)), 4),
        "cumulative_completion_rate": round(float(entry.get("cumulative_completion_rate", 0.0)), 4),
        "cumulative_avg_quality": round(float(entry.get("cumulative_avg_quality", 0.0)), 4),
        "cumulative_platform_utility": round(float(entry.get("cumulative_platform_utility", 0.0)), 4),
    }


def compact_item_payload(item):
    if "round_metrics" in item:
        return {
            "algorithm": item["algorithm"],
            "round_metrics": item["round_metrics"],
        }

    return {
        "algorithm": item["algorithm"],
        "round_metrics": [compact_round_entry(entry) for entry in item.get("round_results", [])],
    }


def compact_bundle(bundle):
    return {
        "experiment_name": bundle["experiment_name"],
        "bundle_format": "algorithm_comparison_v1",
        "algorithms": bundle["algorithms"],
        "runs_per_algorithm": int(bundle["runs_per_algorithm"]),
        "items": [compact_item_payload(item) for item in bundle["items"]],
    }


def load_round_results_from_item(item):
    round_entries = item.get("round_metrics", item.get("round_results", []))
    return [entry for entry in round_entries if int(entry.get("num_tasks", 0)) > 0]


def build_metric_curve(item, metric_key, smooth_window):
    round_results = load_round_results_from_item(item)
    rounds = [int(entry["round_id"]) for entry in round_results]
    values = [float(entry.get(metric_key, 0.0)) for entry in round_results]
    return rounds, moving_average(values, smooth_window)


def plot_figure(bundle, figure_key):
    spec = FIGURE_SPECS[figure_key]
    items = sorted(bundle["items"], key=lambda item: ALGORITHM_NAMES.index(item["algorithm"]))
    set_figure_style()

    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_axisbelow(True)

    csv_rounds = None
    csv_series_rows = []
    labels = []
    legend_handles = []
    y_values_all = []

    for idx, item in enumerate(items):
        algo_name = item["algorithm"]
        label = algorithm_label(algo_name)
        labels.append(label)

        rounds, values = build_metric_curve(item, spec["metric_key"], spec["smooth_window"])

        if csv_rounds is None:
            csv_rounds = rounds
        csv_series_rows.append(values)
        y_values_all.extend(values)

        ax.plot(
            rounds,
            values,
            label=label,
            color=COLOR_LIST[idx],
            marker=MARKER_LIST[idx],
            linestyle="-",
            linewidth=2.0 if idx < 5 else 2.8,
            markersize=4.2 if idx < 5 else 4.8,
            markerfacecolor="white",
            markeredgewidth=0.95,
            alpha=0.98 if idx < 5 else 1.0,
            zorder=4 + idx,
        )
        legend_handles.append(
            Line2D(
                [0], [0], label=label, color=COLOR_LIST[idx], linestyle="-",
                linewidth=2.0 if idx < 5 else 2.8, marker=MARKER_LIST[idx],
                markersize=4.2 if idx < 5 else 4.8, markerfacecolor="white",
                markeredgewidth=0.95,
            )
        )

    ax.set_xlabel("Round")
    ax.set_ylabel(spec["ylabel"])
    ax.set_xlim(0, 145)
    ax.set_xticks(range(0, 141, 20))

    if spec["ylim"] is not None:
        ax.set_ylim(*spec["ylim"])
        if spec["ylim"][1] <= 1.05:
            ax.set_yticks([i / 10 for i in range(0, 11, 2)])
    elif y_values_all:
        y_min = min(y_values_all)
        y_max = max(y_values_all)
        margin = max((y_max - y_min) * 0.08, 0.05)
        ax.set_ylim(y_min - margin, y_max + margin)

    ax.grid(True, axis="y", linestyle="--", linewidth=0.65, color="#b8b8b8", alpha=0.55)
    ax.grid(True, axis="x", linestyle=":", linewidth=0.5, color="#c7c7c7", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", which="both", direction="in", top=False, right=False, length=3.8, width=0.9)
    ax.legend(
        handles=legend_handles,
        loc=spec["legend_loc"],
        ncol=2,
        frameon=True,
        fancybox=False,
        framealpha=0.9,
        facecolor="white",
        edgecolor="#666666",
    )

    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.16, top=0.96)
    fig.savefig(spec["output_png"], bbox_inches="tight")
    fig.savefig(spec["output_pdf"], bbox_inches="tight")
    plt.close(fig)
    save_plot_data_csv(csv_rounds, csv_series_rows, labels, spec["output_csv"])
    print(f"Saved {spec['output_png']}")
    print(f"Saved {spec['output_pdf']}")
    print(f"Saved {spec['output_csv']}")


def plot_all_figures(bundle):
    for figure_key in ("fig33", "fig34", "fig33_supp", "fig34_supp"):
        plot_figure(bundle, figure_key)


def run_single_algorithm_experiment(algorithm_mode, runs_per_algorithm, workspace_root):
    print(f"\n========== Algorithm: {ALGORITHM_LABELS[algorithm_mode]} ==========")

    with tempfile.TemporaryDirectory(
        prefix=f"experiment2_algorithm_{algorithm_mode}_",
        dir=str(workspace_root),
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        prefix = temp_dir / f"truthride_algorithm_{algorithm_mode}"

        round_results, _ = run_experiment(
            algorithm_mode,
            overrides={
                "NUM_EXPERIMENT_RUNS": runs_per_algorithm,
                "prefix": str(prefix),
            },
        )

        return {
            "algorithm": algorithm_mode,
            "round_results": round_results,
        }


def run_full_experiment(algorithms=None, runs_per_algorithm=RUNS_PER_ALGORITHM, keep_temp=False):
    workspace_root = Path.cwd()
    algorithms = algorithms or ALGORITHM_NAMES
    items = []
    temp_root = workspace_root / "experiment2_对比六种算法_tmp"

    try:
        if keep_temp:
            temp_root.mkdir(exist_ok=True)
            work_root = temp_root
        else:
            work_root = workspace_root

        for algo in algorithms:
            items.append(
                run_single_algorithm_experiment(
                    algo,
                    runs_per_algorithm,
                    work_root,
                )
            )
    finally:
        if temp_root.exists() and not keep_temp:
            shutil.rmtree(temp_root, ignore_errors=True)

    bundle = compact_bundle(
        {
            "experiment_name": "experiment2_对比六种算法",
            "algorithms": algorithms,
            "runs_per_algorithm": runs_per_algorithm,
            "items": items,
        }
    )
    save_json(bundle, RESULTS_BUNDLE_FILE)
    return bundle


def load_results_bundle():
    return compact_bundle(load_json(RESULTS_BUNDLE_FILE))
