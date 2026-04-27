from experiment2_图1_绘图工具 import plot_six_line_figure


OUTPUT_FILE = "experiment2_图1_9_每轮任务完成率_六条线.png"


def main():
    plot_six_line_figure(
        metric_key="completion_rate",
        output_file=OUTPUT_FILE,
        ylabel="Per-Round Completion Ratio",
        ylim=(0, 1.02),
        legend_loc="lower right",
        legend_ncol=2,
    )


if __name__ == "__main__":
    main()
