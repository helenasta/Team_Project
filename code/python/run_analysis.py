"""Analysis: does the post-10-K drift exist in 2003-2017? (Table 3 equivalent)

Reads the analysis-ready sample and estimates the You & Zhang (2009) drift
regression: 12-month BHAR on FDR plus risk controls, with year and industry
(2-digit SIC) fixed effects and standard errors clustered by year (Petersen
2006). Saves a results bundle to output/ for the presentation to read.

    BHAR_12M = a0 + a1*FDR + a2*BETA + a3*SIZE + a4*BM + a5*MOM
               + year FE + industry FE + e

A positive, significant a1 means investors underreact to the 10-K (drift).
"""

from pathlib import Path
import pickle

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

PREPARED = Path("data/generated/prepared_data.parquet")
OUTPUT = Path("output/analysis_results.pkl")


def run_reg(df, formula, cluster):
    return smf.ols(formula, data=df).fit(
        cov_type="cluster", cov_kwds={"groups": df[cluster]}
    )


def tidy(model, keep):
    rows = []
    for v in keep:
        if v in model.params.index:
            rows.append({"var": v, "coef": model.params[v],
                         "t": model.tvalues[v], "p": model.pvalues[v]})
    return pd.DataFrame(rows).set_index("var")


def main():
    df = pd.read_parquet(PREPARED).copy()
    # patsy/statsmodels needs plain types, not nullable Int64 -> use string FE
    df["sic2"] = (df["sic"].astype("float").floordiv(100)).astype("string")
    df["year_fe"] = df["filing_year"].astype("int").astype("string")
    # ensure numeric columns are plain float64
    for c in ["bhar_12m", "fdr", "beta", "size", "bm", "mom"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    df["cluster_year"] = df["filing_year"].astype("int")
    print(f"sample: {len(df):,}")

    results = {}

    d1 = df.dropna(subset=["bhar_12m", "fdr", "sic2"])
    m1 = run_reg(d1, "bhar_12m ~ fdr + C(year_fe) + C(sic2)", "cluster_year")
    results["univariate"] = {"n": int(m1.nobs), "r2": m1.rsquared,
                             "table": tidy(m1, ["fdr"])}

    d2 = df.dropna(subset=["bhar_12m", "fdr", "beta", "size", "bm", "mom", "sic2"])
    m2 = run_reg(d2, "bhar_12m ~ fdr + beta + size + bm + mom + C(year_fe) + C(sic2)",
                 "cluster_year")
    results["full_controls"] = {"n": int(m2.nobs), "r2": m2.rsquared,
                                "table": tidy(m2, ["fdr", "beta", "size", "bm", "mom"])}

    d = df.dropna(subset=["bhar_12m", "fdr"]).sort_values("filing_year")
    d["q"] = np.nan
    for y in sorted(d["filing_year"].unique()):
        prior = d[d["filing_year"] == y - 1]["fdr"]
        if len(prior) < 100:
            continue
        edges = prior.quantile([.2, .4, .6, .8]).values
        d.loc[d["filing_year"] == y, "q"] = (
            np.digitize(d.loc[d["filing_year"] == y, "fdr"], edges) + 1)
    q = d.dropna(subset=["q"])
    qtab = q.groupby(q["q"].astype(int))["bhar_12m"].mean() * 100
    from scipy import stats
    p1, p5 = q[q["q"] == 1]["bhar_12m"], q[q["q"] == 5]["bhar_12m"]
    t, p = stats.ttest_ind(p5, p1, equal_var=False)
    results["quintiles"] = {"mean_bhar_pct": qtab,
                            "spread_pct": (p5.mean() - p1.mean()) * 100,
                            "spread_t": t, "spread_p": p}

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "wb") as f:
        pickle.dump(results, f)

    print("\n=== QUINTILE MEAN 12M BHAR (%) ===")
    print(qtab.round(2).to_string())
    print(f"P5-P1 spread: {results['quintiles']['spread_pct']:.2f}%  (t={t:.2f}, p={p:.4f})")
    print("\n=== SPEC 1: univariate (FDR only, +FE) ===")
    print(f"N={results['univariate']['n']:,}  R2={results['univariate']['r2']:.3f}")
    print(results["univariate"]["table"].round(4).to_string())
    print("\n=== SPEC 2: full controls ===")
    print(f"N={results['full_controls']['n']:,}  R2={results['full_controls']['r2']:.3f}")
    print(results["full_controls"]["table"].round(4).to_string())
    print(f"\nsaved -> {OUTPUT}")


if __name__ == "__main__":
    main()
