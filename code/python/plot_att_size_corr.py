"""Scatter of log attention vs log firm size, with regression line and
correlation. Motivates the abnormal-attention adjustment.
Reads prepared_data.parquet + attention_downloads.parquet.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PREP = Path("data/generated/prepared_data.parquet")
ATT = Path("data/pulled/attention_downloads.parquet")
WIN = Path("data/generated/attention_windows.parquet")
OUT = Path("output/att_size_corr.png")


def main():
    df = pd.read_parquet(PREP)
    keep = ["accessionNumber", "size"]
    if "mktcap" in df.columns:
        keep.append("mktcap")
    df = df[keep]
    att = pd.read_parquet(ATT)[["accessionNumber", "att_nr_total"]]
    win = pd.read_parquet(WIN)[["accessionNumber", "log_usable"]]

    d = (df.merge(win, on="accessionNumber", how="inner")
           .query("log_usable")
           .merge(att, on="accessionNumber", how="left"))
    d["att_nr_total"] = d["att_nr_total"].fillna(0)

    # ensure we plot LOG market cap: if 'size' already looks logged (small
    # range) use it, otherwise build it from mktcap.
    if d["size"].max() > 50 and "mktcap" in d.columns:
        d["logsize"] = np.log(d["mktcap"].where(d["mktcap"] > 0))
    else:
        d["logsize"] = d["size"]
    d = d.dropna(subset=["logsize"])
    d["log_att"] = np.log1p(d["att_nr_total"])

    x = d["logsize"].values
    y = d["log_att"].values
    r = np.corrcoef(x, y)[0, 1]
    b1, b0 = np.polyfit(x, y, 1)

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    ax.scatter(x, y, s=6, alpha=0.12, color="#2A6F97", edgecolors="none")
    xs = np.linspace(x.min(), x.max(), 100)
    ax.plot(xs, b0 + b1 * xs, color="#C1666B", linewidth=2.5,
            label=f"Fit: slope {b1:.2f}")
    ax.set_xlabel("Firm size  (log market cap, $m)")
    ax.set_ylabel("Attention  (log 1 + downloads)")
    ax.set_title(f"Attention rises with firm size   (r = {r:.2f})",
                 fontsize=11, fontweight="bold")
    ax.legend(frameon=False, fontsize=9)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.grid(True, alpha=0.25)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(); plt.savefig(OUT, dpi=160)
    print(f"correlation r = {r:.3f}, slope = {b1:.3f}, N = {len(d):,}")
    print(f"x-range (log size): {x.min():.2f} to {x.max():.2f}")
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
