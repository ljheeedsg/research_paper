import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from experiment2_rmse_plot_utils import (
    SERIES_CONFIG_RMSE,
    build_worker_indexes,
    compute_rmse_series,
    load_round_results,
    load_workers,
    save_plot_data_csv,
)


OUTPUT_PNG = "experiment2_Fig. 4：累计 RMSE.png"
OUTPUT_PDF = "experiment2_Fig. 4：累计 RMSE.pdf"
OUTPUT_CSV = "experiment2_Fig. 4：累计 RMSE.csv"
LEGEND_MODE = "manual"
LEGEND_LOC = "lower right"
LEGEND_BBOX_TO_ANCHOR = (0.6, 0.02)
LEGEND_NCOL = 2
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
    csv_rounds = None
    csv_series_rows = []
    legend_handles = []
    max_rmse = 0.0

    for config in SERIES_CONFIG_RMSE:
        round_results = load_round_results(config["path"])
        rounds, _, cumulative_rmse = compute_rmse_series(
            round_results,
            tasks_by_slot,
            task_detail_map,
            trusted_reference_map,
        )

        if csv_rounds is None:
            csv_rounds = rounds
        csv_series_rows.append(cumulative_rmse)
        if cumulative_rmse:
            max_rmse = max(max_rmse, max(cumulative_rmse))

        ax.plot(
            rounds,
            cumulative_rmse,
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
    ax.set_ylabel("Cumulative RMSE")
    ax.set_xlim(0, 145)
    ax.set_xticks(range(0, 141, 20))
    if YLIM_MODE == "manual":
        ax.set_ylim(*YLIM)
    else:
        ax.set_ylim(0.0, max(1.02, round(max_rmse * 1.08, 2)))

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
    save_plot_data_csv(OUTPUT_CSV, csv_rounds, csv_series_rows, SERIES_CONFIG_RMSE)

    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    plot_figure()
