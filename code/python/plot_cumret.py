"""You & Zhang (2009) Figure 4: cumulative size-adjusted return over 12 months
after the filing, by FDR quintile. Reads prepared_data.parquet (for FDR and
year) + wrds_cumret.parquet (monthly cumulative returns).
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PREP = Path("data/generated/prepared_data.parquet")
CUM = Path("data/pulled/wrds_cumret.parquet")
OUT = Path("output/cumret_by_quintile.png")
MONTHS = 12


def main():
    df = pd.read_parquet(PREP)[["accessionNumber", "fdr", "filing_year"]]
    cum = pd.read_parquet(CUM)
    d = df.merge(cum, on="accessionNumber", how="inner").dropna(subset=["fdr"])

    # FDR quintiles using prior-year breakpoints
    d = d.sort_values("filing_year"); d["q"] = np.nan
    for y in sorted(d["filing_year"].unique()):
        prior = d[d["filing_year"] == y - 1]["fdr"]
        if len(prior) < 100:
            continue
        edges = prior.quantile([.2, .4, .6, .8]).values
        d.loc[d["filing_year"] == y, "q"] = (
            np.digitize(d.loc[d["filing_year"] == y, "fdr"], edges) + 1)
    d = d.dropna(subset=["q"]); d["q"] = d["q"].astype(int)

    mcols = [f"m{k}" for k in range(1, MONTHS + 1)]
    means = d.groupby("q")[mcols].mean() * 100  # percent

    fig, ax = plt.subplots(figsize=(8, 4.6))
    colors = plt.cm.RdYlBu(np.linspace(0, 1, 5))
    labels = {1: "Q1 (lowest FDR)", 2: "Q2", 3: "Q3", 4: "Q4",
              5: "Q5 (highest FDR)"}
    x = np.arange(1, MONTHS + 1)
    for i, q in enumerate([1, 2, 3, 4, 5]):
        if q in means.index:
            ax.plot(x, means.loc[q].values, marker="o", markersize=4,
                    color=colors[i], linewidth=2, label=labels[q])
    ax.axhline(0, color="#333333", linestyle="--", linewidth=1)
    ax.set_xlabel("Months after 10-K filing")
    ax.set_ylabel("Cumulative size-adjusted return (%)")
    ax.set_title("Cumulative return over 12 months, by FDR quintile")
    ax.set_xticks(x)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(True, alpha=0.3)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(); plt.savefig(OUT, dpi=160)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
