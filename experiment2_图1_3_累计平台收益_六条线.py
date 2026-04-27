from experiment2_图1_绘图工具 import plot_six_line_figure

OUTPUT_FILE = "experiment2_图1_3_累计平台收益_六条线.png"


def main():
    plot_six_line_figure(
        metric_key="cumulative_platform_utility",
        output_file=OUTPUT_FILE,
        ylabel="Cumulative Platform Utility",
        legend_loc="upper left",
        legend_ncol=2,
    )


if __name__ == "__main__":
    main()
