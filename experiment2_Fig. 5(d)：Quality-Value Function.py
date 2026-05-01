import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from experiment2_重构_配置 import BASE_CONFIG
from experiment2_重构_评价 import quality_value


OUTPUT_PNG = "experiment2_Fig. 5(d)：Quality-Value Function.png"
OUTPUT_PDF = "experiment2_Fig. 5(d)：Quality-Value Function.pdf"
OUTPUT_CSV = "experiment2_Fig. 5(d)：Quality-Value Function.csv"
LEGEND_MODE = "manual"
LEGEND_LOC = "upper left"
LEGEND_BBOX_TO_ANCHOR = (0.03, 0.97)
LEGEND_NCOL = 1
YLIM_MODE = "manual"
YLIM = (-32.0, 32.0)
NUM_POINTS = 201

R_MAX = float(BASE_CONFIG["QUALITY_VALUE_R_MAX"])
K = float(BASE_CONFIG["QUALITY_VALUE_K"])
Q0 = float(BASE_CONFIG["QUALITY_VALUE_Q0"])
RHO = float(BASE_CONFIG["RHO"])


def save_plot_data_csv(q_values, nonlinear_values, linear_values):
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["quality_q", "nonlinear_value", "linear_baseline"])
        for q, nonlinear, linear in zip(q_values, nonlinear_values, linear_values):
            writer.writerow([q, nonlinear, linear])


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


def build_series():
    q_values = [round(i / (NUM_POINTS - 1), 4) for i in range(NUM_POINTS)]
    nonlinear_values = [
        round(quality_value(q, r_max=R_MAX, k=K, q0=Q0), 4) for q in q_values
    ]
    linear_values = [round(RHO * q, 4) for q in q_values]
    return q_values, nonlinear_values, linear_values


def plot_figure():
    set_figure_style()
    q_values, nonlinear_values, linear_values = build_series()

    fig, ax = plt.subplots(figsize=(6.2, 4.8))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_axisbelow(True)

    ax.plot(
        q_values,
        nonlinear_values,
        color="#000000",
        linestyle="-",
        linewidth=2.8,
        zorder=5,
        solid_capstyle="round",
        solid_joinstyle="round",
        antialiased=True,
    )
    ax.plot(
        q_values,
        linear_values,
        color="#E45756",
        linestyle="--",
        linewidth=2.0,
        zorder=4,
        solid_capstyle="round",
        solid_joinstyle="round",
        antialiased=True,
    )

    ax.axhline(0.0, color="#666666", linestyle=":", linewidth=1.0, alpha=0.85, zorder=2)
    ax.axvline(Q0, color="#54A24B", linestyle=":", linewidth=1.1, alpha=0.9, zorder=2)
    ax.text(
        Q0 + 0.015,
        YLIM[0] + (YLIM[1] - YLIM[0]) * 0.08,
        rf"$q_0={Q0:.1f}$",
        color="#2E7D32",
        fontsize=9.5,
    )

    ax.set_xlabel("Data Quality $q$")
    ax.set_ylabel("Task Value")
    ax.set_xlim(0.0, 1.0)
    ax.set_xticks([i / 10 for i in range(0, 11, 2)])
    if YLIM_MODE == "manual":
        ax.set_ylim(*YLIM)
        ax.set_yticks(range(-20, 21, 10))

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

    legend_handles = [
        Line2D(
            [0],
            [0],
            label=rf"Nonlinear $R(q)$  $(R_{{max}}={R_MAX:.0f},\,k={K:.0f},\,q_0={Q0:.1f})$",
            color="#000000",
            linestyle="-",
            linewidth=2.8,
        ),
        Line2D(
            [0],
            [0],
            label=rf"Linear baseline  $(\rho q,\ \rho={RHO:.0f})$",
            color="#E45756",
            linestyle="--",
            linewidth=2.0,
        ),
        Line2D(
            [0],
            [0],
            label="Zero-value boundary",
            color="#666666",
            linestyle=":",
            linewidth=1.0,
        ),
    ]

    legend_kwargs = {
        "handles": legend_handles,
        "loc": LEGEND_LOC if LEGEND_MODE == "manual" else "best",
        "ncol": LEGEND_NCOL,
        "frameon": True,
        "fancybox": False,
        "framealpha": 0.9,
        "facecolor": "white",
        "edgecolor": "#666666",
        "handlelength": 2.4,
        "handletextpad": 0.55,
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
    save_plot_data_csv(q_values, nonlinear_values, linear_values)

    print(f"Saved {OUTPUT_PNG}")
    print(f"Saved {OUTPUT_PDF}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    plot_figure()
