from experiment2_图1_绘图工具 import plot_six_line_figure


OUTPUT_FILE = "experiment2_图1_5_累计流失人数_六条线.png"


def main():
    plot_six_line_figure(
        metric_key="cumulative_left_workers",
        output_file=OUTPUT_FILE,
        ylabel="Cumulative Number of Left Workers",
        ylim=(0, None),
        legend_loc="upper left",
        legend_ncol=2,
    )


if __name__ == "__main__":
    main()
