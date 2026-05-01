from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from experiment2_rmse_plot_utils import (
    build_worker_indexes,
    compute_rmse_series,
    load_round_results,
    load_workers,
)


# 消融实验：三种算法
SERIES_CONFIG = [
    {
        "label": "UCB-Greedy",
        "csv_key": "cmab",
        "path": "experiment2_cmab_longrun_round_results.json",
        "color": "#54A24B",
    },
    {
        "label": "Trust-Aware",
        "csv_key": "cmab_trust",
        "path": "experiment2_cmab_trust_round_results.json",
        "color": "#E45756",
    },
    {
        "label": "TruthRide",
        "csv_key": "truthride",
        "path": "experiment2_cmab_trust_pgrd_lgsc_round_results.json",
        "color": "#000000",
    },
]


OUTPUT_PNG = "experiment2_Fig. 2(b)：消融下的最终累计RMSE.png"
OUTPUT_PDF = "experiment2_Fig. 2(b)：消融下的最终累计RMSE.pdf"
YLIM_MODE = "manual"
YLIM = (0.0, 0.4)


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
    workers = load_workers()
    tasks_by_slot, task_detail_map, trusted_reference_map = build_worker_indexes(workers)

    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_axisbelow(True)

    # 收集数据
    labels = []
    rmse_values = []
    colors = []

    for config in SERIES_CONFIG:
        records = load_round_results(config["path"])
        _, _, cumulative_rmse = compute_rmse_series(
            records,
            tasks_by_slot,
            task_detail_map,
            trusted_reference_map,
        )
        final_rmse = float(cumulative_rmse[-1]) if cumulative_rmse else 0.0

        labels.append(config["label"])
        rmse_values.append(final_rmse)
        colors.append(config["color"])

        print(f"{config['label']}: Final Cumulative RMSE = {final_rmse:.4f}")

    # 绘制柱状图
    x_pos = list(range(len(labels)))
    bars = ax.bar(
        x_pos,
        rmse_values,
        color=colors,
        edgecolor="#333333",
        linewidth=1.2,
        alpha=0.9,
        width=0.6,
    )

    # 在柱子上显示数值
    for idx, (bar, value) in enumerate(zip(bars, rmse_values)):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + 0.01,
            f"{value:.4f}",
            ha="center",
            va="bottom",
            fontsize=9.6,
            fontweight="normal",
        )

    ax.set_xlabel("Algorithm Variant")
    ax.set_ylabel("Final Cumulative RMSE")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, rotation=0)

    if YLIM_MODE == "manual":
        ax.set_ylim(*YLIM)
        # 生成在 YLIM 范围内的刻度
        y_min, y_max = YLIM
        ax.set_yticks([i for i in [i / 10 for i in range(0, 11, 2)] if i <= y_max])
    else:
        ax.set_ylim(0.0, max(rmse_values) * 1.15)
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

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.95)
    ax.spines["left"].set_linewidth(0.95)

    ax.tick_params(axis="both", which="both", direction="in", top=False, right=False, length=3.8, width=0.9)

    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.16, top=0.96)
    fig.savefig(OUTPUT_PNG, bbox_inches="tight")
    fig.savefig(OUTPUT_PDF, bbox_inches="tight")
    plt.close(fig)

    print(f"\nSaved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")


if __name__ == "__main__":
    plot_figure()
