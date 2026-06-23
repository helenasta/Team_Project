"""Control variables: market cap, book-to-market, momentum, beta.
RUNS ON THE WRDS JUPYTERHUB.

Input  (already on WRDS): wrds_link_output.csv [accessionNumber, cik, filingDate, permno]
                          wrds_reportdate.csv  [accessionNumber, reportDate]
Output (download to data/pulled/): wrds_controls.parquet
        [accessionNumber, permno, mktcap, size, bm, mom, beta]
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import wrds

IN_CSV = "wrds_link_output.csv"
REPORTDATE_CSV = "wrds_reportdate.csv"
OUT_PARQUET = "wrds_controls.parquet"


def ok_pos(x):
    """True only if x is a real, finite, positive number (handles pd.NA)."""
    if x is None or x is pd.NA:
        return False
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return False
    return np.isfinite(xf) and xf > 0


def main():
    link = pd.read_csv(IN_CSV, dtype={"accessionNumber": str})
    link["filingDate"] = pd.to_datetime(link["filingDate"])
    link["permno"] = link["permno"].astype(int)

    rd = pd.read_csv(REPORTDATE_CSV, dtype={"accessionNumber": str})
    rd["reportDate"] = pd.to_datetime(rd["reportDate"])
    link = link.merge(rd, on="accessionNumber", how="left")
    print(f"{len(link):,} filings, {link['permno'].nunique():,} permnos")

    permnos = sorted(link["permno"].unique())
    permno_list = ",".join(str(p) for p in permnos)
    dmin = (link["filingDate"].min() - pd.Timedelta(days=4 * 365)).date()
    dmax = (link["filingDate"].max() + pd.Timedelta(days=10)).date()

    db = wrds.Connection()

    print("pulling crsp.msf ...")
    msf = db.raw_sql(f"""
        SELECT permno, date, ret, prc, shrout
        FROM crsp.msf
        WHERE permno IN ({permno_list})
          AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    msf["date"] = pd.to_datetime(msf["date"])
    # force plain float so no nullable-NA leaks into arithmetic
    for c in ["ret", "prc", "shrout"]:
        msf[c] = pd.to_numeric(msf[c], errors="coerce").astype("float64")
    msf["ym"] = msf["date"].dt.to_period("M")
    msf["mktcap_m"] = msf["prc"].abs() * msf["shrout"] / 1000.0
    print(f"  msf rows: {len(msf):,}")

    print("pulling crsp.msi ...")
    msi = db.raw_sql(f"""
        SELECT date, vwretd FROM crsp.msi
        WHERE date BETWEEN '{dmin}' AND '{dmax}'
    """)
    msi["date"] = pd.to_datetime(msi["date"])
    msi["vwretd"] = pd.to_numeric(msi["vwretd"], errors="coerce").astype("float64")
    msi["ym"] = msi["date"].dt.to_period("M")
    mkt = msi[["ym", "vwretd"]]

    print("pulling comp.funda ...")
    funda = db.raw_sql(f"""
        SELECT gvkey, datadate, ceq
        FROM comp.funda
        WHERE indfmt='INDL' AND datafmt='STD' AND popsrc='D' AND consol='C'
          AND datadate BETWEEN '{dmin}' AND '{dmax}'
          AND ceq IS NOT NULL
    """)
    funda["datadate"] = pd.to_datetime(funda["datadate"])
    funda["ceq"] = pd.to_numeric(funda["ceq"], errors="coerce").astype("float64")

    ccm = db.raw_sql("""
        SELECT gvkey, lpermno AS permno, linkdt, linkenddt
        FROM crsp.ccmxpf_lnkhist
        WHERE lpermno IS NOT NULL AND linktype IN ('LC','LU','LS')
          AND linkprim IN ('P','C')
    """)
    ccm["linkdt"] = pd.to_datetime(ccm["linkdt"])
    ccm["linkenddt"] = pd.to_datetime(ccm["linkenddt"]).fillna(pd.Timestamp("2099-12-31"))
    db.close()

    fl = funda.merge(ccm, on="gvkey", how="inner")
    fl = fl[(fl["datadate"] >= fl["linkdt"]) & (fl["datadate"] <= fl["linkenddt"])]
    fl["ym"] = fl["datadate"].dt.to_period("M")
    book = fl[["permno", "ym", "ceq"]].drop_duplicates(["permno", "ym"])
    book_idx = book.set_index(["permno", "ym"])["ceq"].sort_index()
    mkt_idx = mkt.set_index("ym")["vwretd"].sort_index()

    ret_by_permno = {p: g.set_index("ym")["ret"].sort_index()
                     for p, g in msf.groupby("permno")}
    cap_by_permno = {p: g.set_index("ym")["mktcap_m"].sort_index()
                     for p, g in msf.groupby("permno")}

    recs = []
    for r in link.itertuples(index=False):
        permno = r.permno
        fil_ym = pd.Period(r.filingDate, freq="M")
        rep_ym = pd.Period(r.reportDate, freq="M") if pd.notna(r.reportDate) else None
        rec = {"accessionNumber": r.accessionNumber, "permno": permno,
               "mktcap": np.nan, "size": np.nan, "bm": np.nan,
               "mom": np.nan, "beta": np.nan}

        caps = cap_by_permno.get(permno)
        rets = ret_by_permno.get(permno)

        if caps is not None and rep_ym is not None and rep_ym in caps.index:
            mc = caps.loc[rep_ym]
            if ok_pos(mc):
                mc = float(mc)
                rec["mktcap"] = mc
                rec["size"] = np.log(mc)
                be = book_idx.get((permno, rep_ym), np.nan)
                if ok_pos(be):
                    rec["bm"] = float(be) / mc

        if rets is not None:
            window = [fil_ym - k for k in range(0, 6)]
            rr = rets.reindex(window).dropna()
            if len(rr) >= 5:
                rec["mom"] = float(np.prod(1 + rr.values) - 1)

        if rets is not None:
            win = [fil_ym - k for k in range(1, 37)]
            firm = rets.reindex(win).dropna()
            if len(firm) >= 18:
                mkt_w = mkt_idx.reindex(firm.index).dropna()
                common = firm.index.intersection(mkt_w.index)
                if len(common) >= 18:
                    fy = firm.loc[common].values.astype("float64")
                    mx = mkt_w.loc[common].values.astype("float64")
                    b1, _ = np.polyfit(mx, fy, 1)
                    rec["beta"] = float(b1)
        recs.append(rec)

    out = pd.DataFrame.from_records(recs)
    out.to_parquet(OUT_PARQUET, index=False)

    print("\ncoverage (non-null):")
    for c in ["mktcap", "bm", "mom", "beta"]:
        print(f"  {c:7s}: {out[c].notna().sum():,} / {len(out):,} "
              f"({out[c].notna().mean():.1%})")
    print(f"\nfilings with mktcap >= $200m: {(out['mktcap'] >= 200).sum():,}")
    print(f"\nwrote {OUT_PARQUET}")


if __name__ == "__main__":
    main()
