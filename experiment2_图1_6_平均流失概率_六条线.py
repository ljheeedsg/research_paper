from experiment2_图1_绘图工具 import plot_six_line_figure


OUTPUT_FILE = "experiment2_图1_6_平均流失概率_六条线.png"


def main():
    plot_six_line_figure(
        metric_key="avg_leave_probability",
        output_file=OUTPUT_FILE,
        ylabel="Average Leave Probability",
        ylim=(0, 0.35),
        legend_loc="upper right",
        legend_ncol=2,
    )


if __name__ == "__main__":
    main()
