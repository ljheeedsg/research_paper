from experiment2_图1_绘图工具 import plot_six_line_figure


OUTPUT_FILE = "experiment2_图1_4_活跃工人数_六条线.png"


def main():
    plot_six_line_figure(
        metric_key="num_active_workers",
        output_file=OUTPUT_FILE,
        ylabel="Number of Active Workers",
        legend_loc="upper right",
        legend_ncol=2,
    )


if __name__ == "__main__":
    main()
