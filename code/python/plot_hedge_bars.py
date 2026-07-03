"""You & Zhang (2009) style bar chart: hedge return (top minus bottom FDR
quintile) at the 3-, 6- and 12-month horizons.

Reads prepared_data.parquet (FDR, year) + wrds_cumret.parquet (m3, m6, m12).
Writes output/hedge_bars.png.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

PREP = Path("data/generated/prepared_data.parquet")
CUM = Path("data/pulled/wrds_cumret.parquet")
OUT = Path("output/hedge_bars.png")

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

    spreads, errs, sigs = [], [], []
    for col, _ in HORIZONS:
        p5 = d[d["q"] == 5][col].dropna()
        p1 = d[d["q"] == 1][col].dropna()
        spread = (p5.mean() - p1.mean()) * 100
        t, p = stats.ttest_ind(p5, p1, equal_var=False)
        se = spread / t if t != 0 else np.nan
        spreads.append(spread)
        errs.append(abs(1.96 * se))
        sigs.append(p < 0.05)

    fig, ax = plt.subplots(figsize=(7, 4.4))
    x = np.arange(len(HORIZONS))
    colors = ["#2A6F97" if s else "#C1666B" for s in sigs]
    bars = ax.bar(x, spreads, yerr=errs, capsize=6, color=colors,
                  edgecolor="white", width=0.6)
    ax.axhline(0, color="#333333", linewidth=1)
    for xi, v in zip(x, spreads):
        ax.annotate(f"{v:.1f}%", (xi, v),
                    textcoords="offset points",
                    xytext=(0, 8 if v >= 0 else -14),
                    ha="center", fontsize=9, color="#333333")
    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl in HORIZONS])
    ax.set_ylabel("Hedge return, Q5 minus Q1 (%)")
    ax.set_title("Post-filing drift: hedge return by horizon")
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.grid(True, axis="y", alpha=0.3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(); plt.savefig(OUT, dpi=160)
    print("horizon  spread%  95%CI")
    for (col, lbl), s, e in zip(HORIZONS, spreads, errs):
        print(f"  {lbl:10s} {s:6.2f}  +/-{e:.2f}")
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
