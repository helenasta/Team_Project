"""Replicate You & Zhang (2009) Figure 4 with our data.
Five FDR quintiles on the x-axis; three grouped bars per quintile for the
3-, 6- and 12-month cumulative size-adjusted return.

Reads prepared_data.parquet (FDR, year) + wrds_cumret.parquet (m3, m6, m12).
Writes output/fig4_cumret.png.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PREP = Path("data/generated/prepared_data.parquet")
CUM = Path("data/pulled/wrds_cumret.parquet")
OUT = Path("output/fig4_cumret.png")

# You & Zhang colours: light blue (3m), dark red (6m), pale yellow (12m)
COLORS = {"m3": "#8E9FD4", "m6": "#8E2F4C", "m12": "#F2EDA0"}
HORIZONS = [("m3", "3 months"), ("m6", "6 months"), ("m12", "12 months")]


def main():
    df = pd.read_parquet(PREP)[["accessionNumber", "fdr", "filing_year"]]
    cum = pd.read_parquet(CUM)
    d = df.merge(cum, on="accessionNumber", how="inner").dropna(subset=["fdr"])

    # FDR quintiles with prior-year breakpoints
    d = d.sort_values("filing_year"); d["q"] = np.nan
    for y in sorted(d["filing_year"].unique()):
        prior = d[d["filing_year"] == y - 1]["fdr"]
        if len(prior) < 100:
            continue
        edges = prior.quantile([.2, .4, .6, .8]).values
        d.loc[d["filing_year"] == y, "q"] = (
            np.digitize(d.loc[d["filing_year"] == y, "fdr"], edges) + 1)
    d = d.dropna(subset=["q"]); d["q"] = d["q"].astype(int)

    quintiles = [1, 2, 3, 4, 5]
    means = {col: [d[d["q"] == q][col].mean() * 100 for q in quintiles]
             for col, _ in HORIZONS}

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    x = np.arange(len(quintiles))
    w = 0.26
    for i, (col, lbl) in enumerate(HORIZONS):
        ax.bar(x + (i - 1) * w, means[col], width=w, label=lbl,
               color=COLORS[col], edgecolor="#333333", linewidth=0.7)

    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_ylim(top=2)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{q}" for q in quintiles])
    ax.set_xlabel("FDR quintile (1 = lowest, 5 = highest)")
    ax.set_ylabel("Cumulative size-adjusted return (%)")
    ax.set_title("Average size-adjusted abnormal returns by FDR quintile")
    ax.legend(frameon=True, fontsize=9, loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(); plt.savefig(OUT, dpi=160)

    print("quintile  m3      m6      m12")
    for j, q in enumerate(quintiles):
        print(f"   {q}     {means['m3'][j]:6.2f}  {means['m6'][j]:6.2f}  "
              f"{means['m12'][j]:6.2f}")
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
