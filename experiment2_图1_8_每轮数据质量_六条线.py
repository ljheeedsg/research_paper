from experiment2_图1_绘图工具 import plot_six_line_figure


OUTPUT_FILE = "experiment2_图1_8_每轮数据质量_六条线.png"


def main():
    plot_six_line_figure(
        metric_key="avg_quality",
        output_file=OUTPUT_FILE,
        ylabel="Per-Round Average Quality",
        ylim=(0, 1.02),
        legend_loc="lower right",
        legend_ncol=2,
    )


if __name__ == "__main__":
    main()
