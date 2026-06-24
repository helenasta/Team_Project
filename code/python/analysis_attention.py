"""CORE RESULT: is the post-10-K drift larger for low-attention filings?

Interaction model BHAR ~ FDR*LOWATT (+ FDR*SIZE control) plus split-sample.
Attention = size/year-adjusted abnormal EDGAR downloads; LOWATT = below annual
median. fdr:lowatt > 0 is the hypothesis. Year/industry fixed effects are added
as explicit dummy columns (not patsy C()) so the cluster vector cannot desync.
"""

from pathlib import Path
import pickle
import numpy as np
import pandas as pd
import statsmodels.api as sm

PREPARED = Path("data/generated/prepared_data.parquet")
ATT = Path("data/pulled/attention_downloads.parquet")
WINDOWS = Path("data/generated/attention_windows.parquet")
BUNDLE = Path("output/analysis_results.pkl")

ATT_VAR = "att_nr_total"


def fit_clustered(d, y, xcols, fe_cols):
    """OLS with explicit dummies + cluster-by-year, on a clean aligned frame."""
    parts = [d[xcols].astype("float64")]
    for fe in fe_cols:
        dummies = pd.get_dummies(d[fe], prefix=fe, drop_first=True).astype("float64")
        parts.append(dummies)
    X = pd.concat(parts, axis=1)
    X = sm.add_constant(X)
    yv = d[y].astype("float64")
    groups = d["cluster_year"].to_numpy()
    model = sm.OLS(yv.to_numpy(), X.to_numpy()).fit(
        cov_type="cluster", cov_kwds={"groups": groups})
    # map coef names back
    names = ["const"] + list(X.columns[1:])
    coefs = dict(zip(names, model.params))
    ts = dict(zip(names, model.tvalues))
    ps = dict(zip(names, model.pvalues))
    return model, coefs, ts, ps, names


def tidy(coefs, ts, ps, keep):
    rows = [{"var": v, "coef": coefs[v], "t": ts[v], "p": ps[v]}
            for v in keep if v in coefs]
    return pd.DataFrame(rows).set_index("var")


def main():
    df = pd.read_parquet(PREPARED)
    att = pd.read_parquet(ATT)
    win = pd.read_parquet(WINDOWS)[["accessionNumber", "log_usable"]]

    df = df.merge(win, on="accessionNumber", how="inner")
    df = df[df["log_usable"]].copy()
    df = df.merge(att, on="accessionNumber", how="left")
    df["att_nr_total"] = df["att_nr_total"].fillna(0)

    import statsmodels.formula.api as smf
    df["log_att"] = np.log1p(df[ATT_VAR])
    df = df.dropna(subset=["size", "fdr", "bhar_12m"]).copy()
    df["abn_att"] = np.nan
    for y, g in df.groupby("filing_year"):
        if len(g) < 50:
            continue
        m = smf.ols("log_att ~ size", data=g).fit()
        df.loc[g.index, "abn_att"] = m.resid
    df = df.dropna(subset=["abn_att"]).copy()

    df["lowatt"] = 0
    for y, g in df.groupby("filing_year"):
        med = g["abn_att"].median()
        df.loc[g.index[g["abn_att"] <= med], "lowatt"] = 1
    print(f"LOWATT=1: {df['lowatt'].sum():,} / {len(df):,}")

    df["sic2"] = (df["sic"].astype("float").floordiv(100))
    df["cluster_year"] = df["filing_year"].astype(int)
    for c in ["fdr", "bhar_12m", "size", "bm", "mom", "beta"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    df = df.dropna(subset=["sic2"]).copy()
    df["sic2"] = df["sic2"].astype(int)

    # interaction terms as explicit columns
    df["fdr_lowatt"] = df["fdr"] * df["lowatt"]
    df["fdr_size"] = df["fdr"] * df["size"]

    MODEL_VARS = ["bhar_12m", "fdr", "lowatt", "fdr_lowatt", "fdr_size",
                  "beta", "size", "bm", "mom"]
    d = df.dropna(subset=MODEL_VARS).copy().reset_index(drop=True)
    print(f"complete-case sample: {len(d):,}")

    results = {}

    _, c, t, p, _ = fit_clustered(
        d, "bhar_12m",
        ["fdr", "lowatt", "fdr_lowatt", "fdr_size", "beta", "size", "bm", "mom"],
        ["filing_year", "sic2"])
    results["interaction"] = {
        "n": len(d),
        "table": tidy(c, t, p, ["fdr", "lowatt", "fdr_lowatt", "fdr_size",
                                "beta", "size", "bm", "mom"]),
    }

    for grp, name in [(1, "low_attention"), (0, "high_attention")]:
        sub = d[d["lowatt"] == grp].copy().reset_index(drop=True)
        _, c2, t2, p2, _ = fit_clustered(
            sub, "bhar_12m", ["fdr", "beta", "size", "bm", "mom"],
            ["filing_year", "sic2"])
        results[name] = {"n": len(sub), "table": tidy(c2, t2, p2, ["fdr"])}

    existing = {}
    if BUNDLE.exists():
        with open(BUNDLE, "rb") as f:
            existing = pickle.load(f)
    existing["attention"] = results
    with open(BUNDLE, "wb") as f:
        pickle.dump(existing, f)

    print("\n=== INTERACTION MODEL (BHAR ~ FDR x LOWATT) ===")
    print(f"N={results['interaction']['n']:,}")
    print(results["interaction"]["table"].round(4).to_string())
    print("\n  --> hypothesis = 'fdr_lowatt' coefficient (expect > 0)")

    print("\n=== SPLIT SAMPLE: FDR coefficient by attention group ===")
    lo, hi = results["low_attention"], results["high_attention"]
    print(f"LOW  (N={lo['n']:,}): fdr = {lo['table'].loc['fdr','coef']:.3f} "
          f"(t={lo['table'].loc['fdr','t']:.2f}, p={lo['table'].loc['fdr','p']:.4f})")
    print(f"HIGH (N={hi['n']:,}): fdr = {hi['table'].loc['fdr','coef']:.3f} "
          f"(t={hi['table'].loc['fdr','t']:.2f}, p={hi['table'].loc['fdr','p']:.4f})")
    print(f"\nsaved -> {BUNDLE}")


if __name__ == "__main__":
    main()
