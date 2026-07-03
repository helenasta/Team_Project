"""Validation figure: horizontal stacked bar of the ticker cross-check result.
Shows that the CIK->PERMNO match is overwhelmingly correct.
Reads output/analysis_results.pkl['ticker_check']. Writes output/ticker_check.png.
"""
from pathlib import Path
import pickle
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

BUNDLE = Path("output/analysis_results.pkl")
OUT = Path("output/ticker_check.png")


def main():
    with BUNDLE.open("rb") as f:
        R = pickle.load(f)
    tc = R["ticker_check"]
    n = tc["n"]

    # segments in plotting order (left to right)
    segs = [
        ("Exact match (ticker valid at filing date)", tc["exact"], "#2A6F97"),
        ("Match at another date (ticker changed over time)", tc["other_time"], "#6BAED6"),
        ("Mismatch (mostly ticker recycling / shells)", tc["mismatch"], "#C1666B"),
        ("No CRSP ticker record", 1 - tc["exact"] - tc["other_time"] - tc["mismatch"], "#CCCCCC"),
    ]

    fig, ax = plt.subplots(figsize=(9, 2.6))
    left = 0.0
    for label, frac, color in segs:
        ax.barh(0, frac, left=left, color=color, edgecolor="white", height=0.6)
        if frac > 0.03:
            ax.text(left + frac / 2, 0, f"{frac*100:.1f}%",
                    ha="center", va="center", color="white",
                    fontsize=10, fontweight="bold")
        left += frac

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.5, 0.5)
    ax.axis("off")

    # big headline number
    match = tc["exact"] + tc["other_time"]
    ax.text(0.5, 0.62, f"{match*100:.1f}% of filings match  (N = {n:,})",
            ha="center", va="bottom", fontsize=13, fontweight="bold",
            color="#222222", transform=ax.transAxes)

    handles = [Patch(color=c, label=l) for l, _, c in segs]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.15),
              frameon=False, fontsize=8.5, ncol=2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(OUT, dpi=160, bbox_inches="tight")
    print(f"saved -> {OUT}  (match {match:.1%}, N={n})")


if __name__ == "__main__":
    main()
