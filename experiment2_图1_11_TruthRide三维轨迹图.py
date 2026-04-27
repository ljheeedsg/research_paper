import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


INPUT_FILE = "experiment2_cmab_trust_pgrd_lgsc_round_results.json"
OUTPUT_FILE = "experiment2_图1_11_TruthRide三维轨迹图.png"


def load_round_results(path):
    with Path(path).open("r", encoding="utf-8") as f:
        records = json.load(f)
    return [item for item in records if int(item.get("num_tasks", 0)) > 0]


def set_paper_style():
    plt.rcParams.update({
        "font.family": "Times New Roman",
        "font.size": 12,
        "axes.labelsize": 13,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "savefig.dpi": 600,
        "figure.dpi": 150,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def main():
    set_paper_style()

    rounds = load_round_results(INPUT_FILE)
    x = np.array([int(item["round_id"]) for item in rounds], dtype=float)
    y = np.array([float(item["cumulative_avg_quality"]) for item in rounds], dtype=float)
    z = np.array([float(item["cumulative_platform_utility"]) for item in rounds], dtype=float)

    fig = plt.figure(figsize=(8.2, 5.8))
    ax = fig.add_subplot(111, projection="3d")

    ax.plot(
        x,
        y,
        z,
        color="#000000",
        linewidth=2.0,
        alpha=0.9,
    )
    scatter = ax.scatter(
        x,
        y,
        z,
        c=x,
        cmap="viridis",
        s=22,
        edgecolors="none",
        alpha=0.95,
    )

    # 标出起点与终点，更容易看轨迹方向。
    ax.scatter(x[0], y[0], z[0], color="#E45756", s=55, marker="o")
    ax.scatter(x[-1], y[-1], z[-1], color="#54A24B", s=65, marker="^")
    ax.text(x[0], y[0], z[0], "Start", fontsize=10)
    ax.text(x[-1], y[-1], z[-1], "End", fontsize=10)

    ax.set_xlabel("Round")
    ax.set_ylabel("Cumulative Avg Quality")
    ax.set_zlabel("Cumulative Platform Utility")
    ax.set_title("TruthRide 3D Trajectory")

    ax.view_init(elev=24, azim=-63)
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.colorbar(scatter, ax=ax, pad=0.08, shrink=0.75, label="Round")

    fig.tight_layout()
    fig.savefig(OUTPUT_FILE, dpi=600, bbox_inches="tight")
    fig.savefig(OUTPUT_FILE.replace(".png", ".pdf"), bbox_inches="tight")
    plt.close(fig)

    corr_quality_utility = float(np.corrcoef(y, z)[0, 1])
    corr_round_quality = float(np.corrcoef(x, y)[0, 1])
    corr_round_utility = float(np.corrcoef(x, z)[0, 1])

    print(f"Saved {OUTPUT_FILE}")
    print(f"Saved {OUTPUT_FILE.replace('.png', '.pdf')}")
    print(f"corr(cumulative_avg_quality, cumulative_platform_utility) = {corr_quality_utility:.4f}")
    print(f"corr(round, cumulative_avg_quality) = {corr_round_quality:.4f}")
    print(f"corr(round, cumulative_platform_utility) = {corr_round_utility:.4f}")
    print(f"start_point = (round={int(x[0])}, quality={y[0]:.4f}, utility={z[0]:.4f})")
    print(f"end_point = (round={int(x[-1])}, quality={y[-1]:.4f}, utility={z[-1]:.4f})")


if __name__ == "__main__":
    main()
