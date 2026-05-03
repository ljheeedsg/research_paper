import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from experiment2_重构_main import run_experiment


MALICIOUS_RATIOS = [0.10, 0.20, 0.30, 0.40, 0.50]
TRUSTED_RATIO = 0.20
STEP1_SEED = 10
STEP2_SEED = 100
STEP3_SEED = 100
RUNS_PER_RATIO = 10
RESULTS_BUNDLE_FILE = "experiment2_恶意比例鲁棒性_results.json"

COLOR_LIST = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#000000"]
MARKER_LIST = ["o", "s", "^", "D", "P"]

FIGURE_SPECS = {
    "fig20": {
        "output_png": "experiment2_Fig. 20：不同恶意比例下每轮平均数据质量.png",
        "output_pdf": "experiment2_Fig. 20：不同恶意比例下每轮平均数据质量.pdf",
        "output_csv": "experiment2_Fig. 20：不同恶意比例下每轮平均数据质量.csv",
        "ylabel": "Per-Round Average Data Quality",
        "metric_key": "avg_quality",
        "smooth_window": 5,
        "ylim": (0.0, 0.9),
        "legend_loc": "lower right",
    },
    "fig21": {
        "output_png": "experiment2_Fig. 21：不同恶意比例下每轮平台效用.png",
        "output_pdf": "experiment2_Fig. 21：不同恶意比例下每轮平台效用.pdf",
        "output_csv": "experiment2_Fig. 21：不同恶意比例下每轮平台效用.csv",
        "ylabel": "Per-Round Platform Utility",
        "metric_key": "platform_utility",
        "smooth_window": 5,
        "ylim": None,
        "legend_loc": "lower right",
    },
    "fig22": {
        "output_png": "experiment2_Fig. 22：不同恶意比例下种子可信工人留存率.png",
        "output_pdf": "experiment2_Fig. 22：不同恶意比例下种子可信工人留存率.pdf",
        "output_csv": "experiment2_Fig. 22：不同恶意比例下种子可信工人留存率.csv",
        "ylabel": "Retention Rate",
        "metric_key": None,
        "smooth_window": 1,
        "ylim": (0.0, 1.02),
        "legend_loc": "upper right",
    },
    "fig23": {
        "output_png": "experiment2_Fig. 23：不同恶意比例下任务完成率.png",
        "output_pdf": "experiment2_Fig. 23：不同恶意比例下任务完成率.pdf",
        "output_csv": "experiment2_Fig. 23：不同恶意比例下任务完成率.csv",
        "ylabel": "Task Completion Rate",
        "metric_key": "completion_rate",
        "smooth_window": 5,
        "ylim": (0.0, 1.02),
        "legend_loc": "lower right",
    },
    "fig20_supp": {
        "output_png": "experiment2_Fig. 20补充：不同恶意比例下累计平均数据质量.png",
        "output_pdf": "experiment2_Fig. 20补充：不同恶意比例下累计平均数据质量.pdf",
        "output_csv": "experiment2_Fig. 20补充：不同恶意比例下累计平均数据质量.csv",
        "ylabel": "Cumulative Average Data Quality",
        "metric_key": "cumulative_avg_quality",
        "smooth_window": 1,
        "ylim": (0.0, 0.9),
        "legend_loc": "lower right",
    },
    "fig21_supp": {
        "output_png": "experiment2_Fig. 21补充：不同恶意比例下累计平台效用.png",
        "output_pdf": "experiment2_Fig. 21补充：不同恶意比例下累计平台效用.pdf",
        "output_csv": "experiment2_Fig. 21补充：不同恶意比例下累计平台效用.csv",
        "ylabel": "Cumulative Platform Utility",
        "metric_key": "cumulative_platform_utility",
        "smooth_window": 1,
        "ylim": None,
        "legend_loc": "lower right",
    },
    "fig23_supp": {
        "output_png": "experiment2_Fig. 23补充：不同恶意比例下累计任务完成率.png",
        "output_pdf": "experiment2_Fig. 23补充：不同恶意比例下累计任务完成率.pdf",
        "output_csv": "experiment2_Fig. 23补充：不同恶意比例下累计任务完成率.csv",
        "ylabel": "Cumulative Task Completion Rate",
        "metric_key": "cumulative_completion_rate",
        "smooth_window": 1,
        "ylim": (0.0, 1.02),
        "legend_loc": "lower right",
    },
}


def save_json(payload, path):
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_json(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def run_command(args):
    print("\n>>>", " ".join(str(arg) for arg in args))
    subprocess.run([str(arg) for arg in args], check=True)


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


def ratio_label(malicious_ratio):
    return f"{int(round(malicious_ratio * 100))}%"


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
        "avg_quality": round(float(entry.get("avg_quality", 0.0)), 4),
        "platform_utility": round(float(entry.get("platform_utility", 0.0)), 4),
        "completion_rate": round(float(entry.get("completion_rate", 0.0)), 4),
        "cumulative_avg_quality": round(float(entry.get("cumulative_avg_quality", 0.0)), 4),
        "cumulative_platform_utility": round(
            float(entry.get("cumulative_platform_utility", 0.0)), 4
        ),
        "cumulative_completion_rate": round(
            float(entry.get("cumulative_completion_rate", 0.0)), 4
        ),
    }


def compact_retention_entry(entry, seed_trusted_ids, left_seed_ids, seed_count):
    left_ids = {int(worker_id) for worker_id in entry.get("left_worker_ids_this_round", [])}
    left_seed_ids.update(left_ids & seed_trusted_ids)
    retained = seed_count - len(left_seed_ids)
    return {
        "round_id": int(entry["round_id"]),
        "num_tasks": int(entry.get("num_tasks", 0)),
        "retention_rate": round(retained / seed_count, 4),
    }


def build_compact_round_metrics(round_results):
    return [compact_round_entry(entry) for entry in round_results]


def build_compact_retention_curve(all_runs_payload, seed_trusted_worker_ids):
    seed_trusted_ids = {int(worker_id) for worker_id in seed_trusted_worker_ids}
    seed_count = max(1, len(seed_trusted_ids))
    per_run_curves = []
    round_axis = None

    for run_payload in all_runs_payload:
        round_results = [
            entry for entry in run_payload["round_results"] if int(entry.get("num_tasks", 0)) > 0
        ]
        compact_curve = []
        left_seed_ids = set()
        for entry in round_results:
            compact_curve.append(
                compact_retention_entry(entry, seed_trusted_ids, left_seed_ids, seed_count)
            )

        rounds = [entry["round_id"] for entry in compact_curve]
        if round_axis is None:
            round_axis = rounds
        per_run_curves.append(compact_curve)

    averaged_curve = []
    for idx, round_id in enumerate(round_axis or []):
        averaged_curve.append(
            {
                "round_id": round_id,
                "num_tasks": per_run_curves[0][idx]["num_tasks"],
                "retention_rate": round(
                    sum(curve[idx]["retention_rate"] for curve in per_run_curves) / len(per_run_curves),
                    4,
                ),
            }
        )

    return averaged_curve


def compact_item_payload(item):
    if "round_metrics" in item and "retention_curve" in item:
        return {
            "malicious_ratio": float(item["malicious_ratio"]),
            "ratio_tag": int(item["ratio_tag"]),
            "round_metrics": item["round_metrics"],
            "retention_curve": item["retention_curve"],
        }

    round_results = item["round_results"]
    all_runs_payload = item["all_runs_payload"]
    seed_trusted_worker_ids = item["seed_trusted_worker_ids"]

    return {
        "malicious_ratio": float(item["malicious_ratio"]),
        "ratio_tag": int(item["ratio_tag"]),
        "round_metrics": build_compact_round_metrics(round_results),
        "retention_curve": build_compact_retention_curve(
            all_runs_payload,
            seed_trusted_worker_ids,
        ),
    }


def compact_bundle(bundle):
    return {
        "experiment_name": bundle["experiment_name"],
        "bundle_format": "compact_round_metrics_v1",
        "trusted_ratio": float(bundle["trusted_ratio"]),
        "malicious_ratios": [float(ratio) for ratio in bundle["malicious_ratios"]],
        "runs_per_ratio": int(bundle["runs_per_ratio"]),
        "items": [compact_item_payload(item) for item in bundle["items"]],
    }


def load_round_results_from_item(item):
    round_entries = item.get("round_metrics", item.get("round_results", []))
    return [entry for entry in round_entries if int(entry.get("num_tasks", 0)) > 0]


def enrich_round_metrics(round_results):
    cumulative_num_tasks = 0
    cumulative_num_completed = 0
    cumulative_platform_utility = 0.0
    cumulative_quality_weighted_sum = 0.0
    enriched = []

    for entry in round_results:
        enriched_entry = dict(entry)
        num_tasks = int(enriched_entry.get("num_tasks", 0))
        completion_rate = float(enriched_entry.get("completion_rate", 0.0))
        num_completed = enriched_entry.get("num_completed")
        if num_completed is None:
            num_completed = int(round(num_tasks * completion_rate))
        else:
            num_completed = int(num_completed)

        avg_quality = float(enriched_entry.get("avg_quality", 0.0))
        platform_utility = float(enriched_entry.get("platform_utility", 0.0))

        cumulative_num_tasks += num_tasks
        cumulative_num_completed += num_completed
        cumulative_platform_utility += platform_utility
        cumulative_quality_weighted_sum += avg_quality * num_completed

        enriched_entry["num_completed"] = num_completed
        enriched_entry["cumulative_completion_rate"] = round(
            cumulative_num_completed / cumulative_num_tasks if cumulative_num_tasks > 0 else 0.0,
            4,
        )
        enriched_entry["cumulative_platform_utility"] = round(cumulative_platform_utility, 4)
        enriched_entry["cumulative_avg_quality"] = round(
            cumulative_quality_weighted_sum / cumulative_num_completed
            if cumulative_num_completed > 0 else 0.0,
            4,
        )
        enriched.append(enriched_entry)

    return enriched


def compute_seed_retention_curve(all_runs_payload, seed_trusted_ids):
    seed_trusted_ids = {int(worker_id) for worker_id in seed_trusted_ids}
    seed_count = max(1, len(seed_trusted_ids))
    per_run_curves = []
    round_axis = None

    for run_payload in all_runs_payload:
        round_results = [
            entry for entry in run_payload["round_results"] if int(entry.get("num_tasks", 0)) > 0
        ]
        rounds = [int(entry["round_id"]) for entry in round_results]
        if round_axis is None:
            round_axis = rounds

        left_seed_ids = set()
        retention_values = []
        for entry in round_results:
            left_ids = {int(worker_id) for worker_id in entry.get("left_worker_ids_this_round", [])}
            left_seed_ids.update(left_ids & seed_trusted_ids)
            retained = seed_count - len(left_seed_ids)
            retention_values.append(round(retained / seed_count, 4))

        per_run_curves.append(retention_values)

    averaged_curve = []
    for idx in range(len(per_run_curves[0])):
        averaged_curve.append(
            round(sum(curve[idx] for curve in per_run_curves) / len(per_run_curves), 4)
        )

    return round_axis, averaged_curve


def build_metric_curve(item, metric_key, smooth_window):
    round_results = enrich_round_metrics(load_round_results_from_item(item))
    rounds = [int(entry["round_id"]) for entry in round_results]
    values = [float(entry[metric_key]) for entry in round_results]
    return rounds, moving_average(values, smooth_window)


def build_retention_curve(item, smooth_window):
    if "retention_curve" in item:
        retention_entries = [
            entry for entry in item["retention_curve"] if int(entry.get("num_tasks", 0)) > 0
        ]
        rounds = [int(entry["round_id"]) for entry in retention_entries]
        values = [float(entry["retention_rate"]) for entry in retention_entries]
        return rounds, moving_average(values, smooth_window)

    rounds, values = compute_seed_retention_curve(
        item["all_runs_payload"],
        item["seed_trusted_worker_ids"],
    )
    return rounds, moving_average(values, smooth_window)


def plot_figure(bundle, figure_key):
    spec = FIGURE_SPECS[figure_key]
    items = sorted(bundle["items"], key=lambda item: item["malicious_ratio"])
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
        label = ratio_label(item["malicious_ratio"])
        labels.append(label)

        if figure_key == "fig22":
            rounds, values = build_retention_curve(item, spec["smooth_window"])
        else:
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
            linewidth=2.0 if idx < 4 else 2.8,
            markersize=4.2 if idx < 4 else 4.8,
            markerfacecolor="white",
            markeredgewidth=0.95,
            alpha=0.98 if idx < 4 else 1.0,
            zorder=4 + idx,
        )
        legend_handles.append(
            Line2D(
                [0], [0], label=label, color=COLOR_LIST[idx], linestyle="-",
                linewidth=2.0 if idx < 4 else 2.8, marker=MARKER_LIST[idx],
                markersize=4.2 if idx < 4 else 4.8, markerfacecolor="white",
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
        margin = max((y_max - y_min) * 0.08, 20.0)
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
    for figure_key in ("fig20", "fig21", "fig22", "fig23", "fig20_supp", "fig21_supp", "fig23_supp"):
        plot_figure(bundle, figure_key)


def run_single_ratio_experiment(malicious_ratio, runs_per_ratio, workspace_root):
    ratio_tag = int(round(malicious_ratio * 100))
    print(f"\n========== Malicious Ratio {ratio_tag}% ==========")

    with tempfile.TemporaryDirectory(
        prefix=f"experiment2_malicious_{ratio_tag}_",
        dir=str(workspace_root),
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        vehicle_file = temp_dir / "vehicle.csv"
        vehicle_plot = temp_dir / "vehicle.png"
        vehicle_summary = temp_dir / "vehicle_summary.json"
        vehicle_summary_all = temp_dir / "vehicle_summary_all_runs.json"

        task_csv = temp_dir / "tasks.csv"
        task_json = temp_dir / "task_segments.json"
        task_plot = temp_dir / "tasks_distribution.png"
        task_summary = temp_dir / "tasks_summary.json"
        task_summary_all = temp_dir / "tasks_summary_all_runs.json"

        worker_json = temp_dir / "worker_options.json"
        worker_summary = temp_dir / "worker_summary.json"
        worker_summary_all = temp_dir / "worker_summary_all_runs.json"

        prefix = temp_dir / f"truthride_malicious_{ratio_tag}"

        run_command(
            [
                sys.executable,
                "experiment2_第1步产生车数据.py",
                "--output-seg", vehicle_file,
                "--output-plot", vehicle_plot,
                "--summary-file", vehicle_summary,
                "--all-runs-summary-file", vehicle_summary_all,
                "--trusted-ratio", TRUSTED_RATIO,
                "--malicious-ratio", malicious_ratio,
                "--seed", STEP1_SEED,
                "--runs", 1,
            ]
        )
        run_command(
            [
                sys.executable,
                "experiment2_第2步产生任务数据.py",
                "--vehicle-file", vehicle_file,
                "--task-csv", task_csv,
                "--task-json", task_json,
                "--plot-file", task_plot,
                "--summary-file", task_summary,
                "--all-runs-summary-file", task_summary_all,
                "--seed", STEP2_SEED,
                "--runs", 1,
            ]
        )
        run_command(
            [
                sys.executable,
                "experiment2_第3步产生工人可选项.py",
                "--vehicle-file", vehicle_file,
                "--task-file", task_csv,
                "--output-json", worker_json,
                "--summary-file", worker_summary,
                "--all-runs-summary-file", worker_summary_all,
                "--seed", STEP3_SEED,
                "--runs", 1,
            ]
        )

        run_experiment(
            "lgsc",
            overrides={
                "WORKER_OPTIONS_FILE": str(worker_json),
                "NUM_EXPERIMENT_RUNS": runs_per_ratio,
                "prefix": str(prefix),
            },
        )

        worker_options = load_json(worker_json)
        seed_trusted_worker_ids = sorted(
            int(worker["worker_id"])
            for worker in worker_options.values()
            if worker.get("init_category") == "trusted"
        )

        return compact_item_payload(
            {
            "malicious_ratio": malicious_ratio,
            "ratio_tag": ratio_tag,
            "seed_trusted_worker_ids": seed_trusted_worker_ids,
            "round_results": load_json(f"{prefix}_round_results.json"),
            "all_runs_payload": load_json(f"{prefix}_round_results_all_runs.json"),
            }
        )


def run_full_experiment(ratios=None, runs_per_ratio=RUNS_PER_RATIO, keep_temp=False):
    workspace_root = Path.cwd()
    ratios = ratios or MALICIOUS_RATIOS
    items = []
    temp_root = workspace_root / "experiment2_恶意比例鲁棒性_tmp"

    try:
        if keep_temp:
            temp_root.mkdir(exist_ok=True)
            work_root = temp_root
        else:
            work_root = workspace_root

        for ratio in ratios:
            items.append(run_single_ratio_experiment(ratio, runs_per_ratio, work_root))
    finally:
        if temp_root.exists() and not keep_temp:
            shutil.rmtree(temp_root, ignore_errors=True)

    bundle = compact_bundle(
        {
        "experiment_name": "experiment2_恶意比例鲁棒性",
        "trusted_ratio": TRUSTED_RATIO,
        "malicious_ratios": ratios,
        "runs_per_ratio": runs_per_ratio,
        "items": items,
        }
    )
    save_json(bundle, RESULTS_BUNDLE_FILE)
    return bundle


def load_results_bundle():
    return compact_bundle(load_json(RESULTS_BUNDLE_FILE))
