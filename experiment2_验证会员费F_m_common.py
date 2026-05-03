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


MEMBERSHIP_FEE_VALUES = [1, 2, 3, 4, 5, 7]
RUNS_PER_VALUE = 10
RESULTS_BUNDLE_FILE = "experiment2_验证会员费F_m_results.json"
WORKER_OPTIONS_FILE = "experiment2_worker_options.json"

COLOR_LIST = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#000000"]
MARKER_LIST = ["o", "s", "^", "D", "v", "P"]

FIGURE_SPECS = {
    "fig30": {
        "output_png": "experiment2_Fig. 30：不同F_m下每轮平均数据质量.png",
        "output_pdf": "experiment2_Fig. 30：不同F_m下每轮平均数据质量.pdf",
        "output_csv": "experiment2_Fig. 30：不同F_m下每轮平均数据质量.csv",
        "ylabel": "Per-Round Average Data Quality",
        "metric_key": "avg_quality",
        "smooth_window": 5,
        "ylim": (0.0, 0.9),
        "legend_loc": "lower right",
    },
    "fig31": {
        "output_png": "experiment2_Fig. 31：不同F_m下每轮平台效用.png",
        "output_pdf": "experiment2_Fig. 31：不同F_m下每轮平台效用.pdf",
        "output_csv": "experiment2_Fig. 31：不同F_m下每轮平台效用.csv",
        "ylabel": "Per-Round Platform Utility",
        "metric_key": "platform_utility",
        "smooth_window": 5,
        "ylim": None,
        "legend_loc": "lower right",
    },
    "fig32": {
        "output_png": "experiment2_Fig. 32：不同F_m下种子可信工人留存率.png",
        "output_pdf": "experiment2_Fig. 32：不同F_m下种子可信工人留存率.pdf",
        "output_csv": "experiment2_Fig. 32：不同F_m下种子可信工人留存率.csv",
        "ylabel": "Retention Rate",
        "metric_key": None,
        "smooth_window": 1,
        "ylim": (0.0, 1.02),
        "legend_loc": "upper right",
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


def fm_label(membership_fee):
    return f"F_m={int(membership_fee)}"


def save_plot_data_csv(rounds, series_rows, labels, output_csv):
    headers = ["round"] + labels
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for idx, round_id in enumerate(rounds):
            row = [round_id]
            row.extend(values[idx] for values in series_rows)
            writer.writerow(row)


def load_seed_trusted_worker_ids():
    worker_options = load_json(WORKER_OPTIONS_FILE)
    return sorted(
        int(worker["worker_id"])
        for worker in worker_options.values()
        if worker.get("init_category") == "trusted"
    )


def compact_round_entry(entry):
    return {
        "round_id": int(entry["round_id"]),
        "num_tasks": int(entry.get("num_tasks", 0)),
        "num_completed": int(entry.get("num_completed", 0)),
        "avg_quality": round(float(entry.get("avg_quality", 0.0)), 4),
        "platform_utility": round(float(entry.get("platform_utility", 0.0)), 4),
        "completion_rate": round(float(entry.get("completion_rate", 0.0)), 4),
        "trusted_count": int(entry.get("trusted_count", 0)),
        "unknown_count": int(entry.get("unknown_count", 0)),
        "malicious_count": int(entry.get("malicious_count", 0)),
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
            "membership_fee": int(item["membership_fee"]),
            "round_metrics": item["round_metrics"],
            "retention_curve": item["retention_curve"],
        }

    return {
        "membership_fee": int(item["membership_fee"]),
        "round_metrics": build_compact_round_metrics(item["round_results"]),
        "retention_curve": build_compact_retention_curve(
            item["all_runs_payload"],
            item["seed_trusted_worker_ids"],
        ),
    }


def compact_bundle(bundle):
    return {
        "experiment_name": bundle["experiment_name"],
        "bundle_format": "membership_fee_compact_v1",
        "membership_fee_values": [int(value) for value in bundle["membership_fee_values"]],
        "runs_per_value": int(bundle["runs_per_value"]),
        "items": [compact_item_payload(item) for item in bundle["items"]],
    }


def load_round_results_from_item(item):
    round_entries = item.get("round_metrics", item.get("round_results", []))
    return [entry for entry in round_entries if int(entry.get("num_tasks", 0)) > 0]


def enrich_round_metrics(round_results):
    trusted_count = None
    unknown_count = None
    malicious_count = None
    enriched = []

    for entry in round_results:
        enriched_entry = dict(entry)

        if "trusted_count" not in enriched_entry:
            trusted_count = 0 if trusted_count is None else trusted_count
            enriched_entry["trusted_count"] = trusted_count
        else:
            trusted_count = int(enriched_entry["trusted_count"])

        if "unknown_count" not in enriched_entry:
            unknown_count = 0 if unknown_count is None else unknown_count
            enriched_entry["unknown_count"] = unknown_count
        else:
            unknown_count = int(enriched_entry["unknown_count"])

        if "malicious_count" not in enriched_entry:
            malicious_count = 0 if malicious_count is None else malicious_count
            enriched_entry["malicious_count"] = malicious_count
        else:
            malicious_count = int(enriched_entry["malicious_count"])

        enriched.append(enriched_entry)

    return enriched


def build_metric_curve(item, metric_key, smooth_window):
    round_results = enrich_round_metrics(load_round_results_from_item(item))
    rounds = [int(entry["round_id"]) for entry in round_results]
    values = [float(entry[metric_key]) for entry in round_results]
    return rounds, moving_average(values, smooth_window)


def build_retention_curve(item, smooth_window):
    retention_entries = [
        entry for entry in item["retention_curve"] if int(entry.get("num_tasks", 0)) > 0
    ]
    rounds = [int(entry["round_id"]) for entry in retention_entries]
    values = [float(entry["retention_rate"]) for entry in retention_entries]
    return rounds, moving_average(values, smooth_window)


def plot_figure(bundle, figure_key):
    spec = FIGURE_SPECS[figure_key]
    items = sorted(bundle["items"], key=lambda item: item["membership_fee"])
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
        label = fm_label(item["membership_fee"])
        labels.append(label)

        if figure_key == "fig32":
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
    for figure_key in ("fig30", "fig31", "fig32"):
        plot_figure(bundle, figure_key)


def run_single_value_experiment(membership_fee, runs_per_value, workspace_root, seed_trusted_worker_ids):
    print(f"\n========== Membership Fee F_m = {membership_fee} ==========")

    with tempfile.TemporaryDirectory(
        prefix=f"experiment2_membership_fee_{membership_fee}_",
        dir=str(workspace_root),
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        prefix = temp_dir / f"truthride_membership_fee_{membership_fee}"

        round_results, _ = run_experiment(
            "lgsc",
            overrides={
                "MEMBERSHIP_FEE": int(membership_fee),
                "NUM_EXPERIMENT_RUNS": runs_per_value,
                "prefix": str(prefix),
            },
        )

        return compact_item_payload(
            {
                "membership_fee": int(membership_fee),
                "round_results": round_results,
                "all_runs_payload": load_json(f"{prefix}_round_results_all_runs.json"),
                "seed_trusted_worker_ids": seed_trusted_worker_ids,
            }
        )


def run_full_experiment(membership_fee_values=None, runs_per_value=RUNS_PER_VALUE, keep_temp=False):
    workspace_root = Path.cwd()
    membership_fee_values = membership_fee_values or MEMBERSHIP_FEE_VALUES
    items = []
    seed_trusted_worker_ids = load_seed_trusted_worker_ids()
    temp_root = workspace_root / "experiment2_验证会员费F_m_tmp"

    try:
        if keep_temp:
            temp_root.mkdir(exist_ok=True)
            work_root = temp_root
        else:
            work_root = workspace_root

        for value in membership_fee_values:
            items.append(
                run_single_value_experiment(
                    value,
                    runs_per_value,
                    work_root,
                    seed_trusted_worker_ids,
                )
            )
    finally:
        if temp_root.exists() and not keep_temp:
            shutil.rmtree(temp_root, ignore_errors=True)

    bundle = compact_bundle(
        {
            "experiment_name": "experiment2_验证会员费F_m",
            "membership_fee_values": membership_fee_values,
            "runs_per_value": runs_per_value,
            "items": items,
        }
    )
    save_json(bundle, RESULTS_BUNDLE_FILE)
    return bundle


def load_results_bundle():
    return compact_bundle(load_json(RESULTS_BUNDLE_FILE))
