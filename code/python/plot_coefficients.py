"""Vertical coefficient plots with 90% confidence intervals (10% level).
Variables on the x-axis, coefficients on the y-axis. Point + 90% CI whisker.
Reads output/analysis_results.pkl (SE recovered as coef/t).
"""
from pathlib import Path
import pickle
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

BUNDLE = Path("output/analysis_results.pkl")
OUTA = Path("output/coef_drift.png")
OUTB = Path("output/coef_attention.png")
Z90 = 1.645

SIG = "#2A6F97"
NULLC = "#C1666B"
GRID = "#E4E4E4"


def ci_from(tab, var):
    coef = tab.loc[var, "coef"]
    t = tab.loc[var, "t"]
    se = abs(coef / t) if t != 0 else np.nan
    return {"c": coef, "se": se}


def style_ax(ax):
    ax.axhline(0, color="#333333", linestyle="--", linewidth=1, zorder=1)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.xaxis.grid(False)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#888888")
    ax.spines["bottom"].set_color("#888888")
    ax.tick_params(colors="#444444")


def vplot(ax, labels, pts, title):
    x = np.arange(len(labels))
    for xi, p in zip(x, pts):
        c, se = p["c"], p["se"]
        lo, hi = c - Z90 * se, c + Z90 * se
        color = NULLC if (lo <= 0 <= hi) else SIG
        ax.plot([xi, xi], [lo, hi], color=color, lw=2.6, zorder=2)
        ax.plot([xi - 0.06, xi + 0.06], [lo, lo], color=color, lw=2.6)
        ax.plot([xi - 0.06, xi + 0.06], [hi, hi], color=color, lw=2.6)
        ax.plot(xi, c, "o", color=color, markersize=9,
                markeredgecolor="white", markeredgewidth=1.4, zorder=3)
        ax.annotate(f"{c:.3f}", (xi, c), textcoords="offset points",
                    xytext=(11, 0), va="center", fontsize=8, color="#333333")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Coefficient (90% CI)", fontsize=9)
    ax.set_title(title, fontsize=10, fontweight="bold", color="#222222", pad=10)
    style_ax(ax)
    ax.set_xlim(-0.5, len(labels) - 0.5)


def main():
    with BUNDLE.open("rb") as f:
        R = pickle.load(f)

    legend = [
        Patch(color=SIG, label="Significant at 10%"),
        Patch(color=NULLC, label="Not significant"),
    ]

    ft = R["full_controls"]["table"]
    varsA = ["fdr", "beta", "size", "bm", "mom"]
    labelsA = ["FDR", "Beta", "Size", "Book-to-\nmarket", "Momentum"]
    figA, axA = plt.subplots(figsize=(7.5, 4.2))
    vplot(axA, labelsA, [ci_from(ft, v) for v in varsA],
          "Drift regression: 12-month BHAR on FDR and controls")
    axA.legend(handles=legend, frameon=False, fontsize=8, loc="upper right")
    plt.tight_layout(); plt.savefig(OUTA, dpi=160)
    print(f"saved -> {OUTA}")

    it = R["attention"]["interaction"]["table"]
    lo = R["attention"]["low_attention"]["table"]
    hi = R["attention"]["high_attention"]["table"]
    figB, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))
    vplot(ax1, ["FDR x\nLOWATT", "FDR x\nSIZE"],
          [ci_from(it, v) for v in ["fdr_lowatt", "fdr_size"]],
          "Interaction model")
    vplot(ax2, ["Low\nattention", "High\nattention"],
          [ci_from(lo, "fdr"), ci_from(hi, "fdr")],
          "FDR coefficient by group")
    figB.legend(handles=legend, frameon=False, fontsize=8, loc="lower center",
                ncol=2, bbox_to_anchor=(0.5, -0.02))
    plt.tight_layout(rect=[0, 0.05, 1, 1]); plt.savefig(OUTB, dpi=160)
    print(f"saved -> {OUTB}")


if __name__ == "__main__":
    main()
