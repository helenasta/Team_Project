"""Plot trading volume around the 10-K filing date as a bar chart
(You & Zhang 2009, Figure 1, Panel A style).
Reads data/pulled/wrds_volume_event.parquet and writes output/volume_event.png.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

SRC = Path("data/pulled/wrds_volume_event.parquet")
OUT = Path("output/volume_event.png")


def main():
    ev = pd.read_parquet(SRC)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    days = ev["event_day"].to_numpy()
    vol = (ev["mean_scaled_volume"] * 100).to_numpy()  # in percent

    # color the filing-day bars (0 and +1) differently to highlight the reaction
    colors = ["#C44E52" if d in (0, 1) else "#4C72B0" for d in days]

    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.bar(days, vol, color=colors, edgecolor="white", width=0.8)

    # y-axis starts near the pre-filing baseline so the bump is visible,
    # but keep 0 in view is optional; here we zoom to make the pattern clear
    ymin = vol.min() * 0.95
    ymax = vol.max() * 1.03
    ax.set_ylim(ymin, ymax)

    ax.set_xlabel("Trading day relative to 10-K filing")
    ax.set_ylabel("Mean scaled volume (%)")
    ax.set_title("Trading volume around the 10-K filing date")
    ax.set_xticks(range(-10, 11, 2))
    ax.grid(True, axis="y", alpha=0.3)

    # legend via proxy handles
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color="#4C72B0", label="Surrounding days"),
        Patch(color="#C44E52", label="Filing day (0) and day +1"),
    ], frameon=False)

    plt.tight_layout()
    plt.savefig(OUT, dpi=150)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
