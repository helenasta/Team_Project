"""FDR + 12-month BHAR construction. RUNS ON THE WRDS JUPYTERHUB.

Input  (already on WRDS): wrds_link_output.csv  [accessionNumber, cik, filingDate, permno]
Output (download to data/pulled/): wrds_returns.parquet
        [accessionNumber, permno, filingDate, fdr, bhar_12m, n_days_bhar, has_fdr, has_bhar]

Method (You & Zhang 2009, faithful):
- size adjustment uses CRSP cap-based decile portfolios (crsp.ermport1), which
  gives each permno-day its decile (capn) and that decile's return (decret).
  size-adjusted daily return = ret - decret.
- FDR = compounded size-adjusted return over the 3 trading days [0, +2] starting
  on the filing date (or the first trading day on/after it).
- BHAR_12M = compounded size-adjusted return over the 12 months starting on the
  first trading day of the calendar month AFTER the 3-day filing window, so the
  FDR and BHAR windows never overlap.
- delisting returns (crsp.dsedelist) are spliced in so firms that disappear
  during the holding year contribute their true terminal return (no upward bias).
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import wrds

IN_CSV = "wrds_link_output.csv"
OUT_PARQUET = "wrds_returns.parquet"

FDR_DAYS = 3
BHAR_MONTHS = 12


def main():
    link = pd.read_csv(IN_CSV, dtype={"accessionNumber": str})
    link["filingDate"] = pd.to_datetime(link["filingDate"])
    link["permno"] = link["permno"].astype(int)
    permnos = sorted(link["permno"].unique())
    dmin = (link["filingDate"].min() - pd.Timedelta(days=10)).date()
    dmax = (link["filingDate"].max() + pd.Timedelta(days=420)).date()
    print(f"{len(link):,} filings, {len(permnos):,} permnos, "
          f"return window {dmin} .. {dmax}")

    db = wrds.Connection()

    permno_list = ",".join(str(p) for p in permnos)
    print("pulling crsp.dsf ...")
    dsf = db.raw_sql(f"""
        SELECT permno, date, ret
        FROM crsp.dsf
        WHERE permno IN ({permno_list})
          AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    print(f"  dsf rows: {len(dsf):,}")

    print("pulling crsp.ermport1 (decile benchmark) ...")
    erm = db.raw_sql(f"""
        SELECT permno, date, decret
        FROM crsp.ermport1
        WHERE permno IN ({permno_list})
          AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    print(f"  ermport1 rows: {len(erm):,}")

    print("pulling crsp.dsedelist (delisting returns) ...")
    dl = db.raw_sql(f"""
        SELECT permno, dlstdt AS date, dlret
        FROM crsp.dsedelist
        WHERE permno IN ({permno_list})
          AND dlret IS NOT NULL
    """)
    print(f"  delist rows: {len(dl):,}")
    db.close()

    dsf["date"] = pd.to_datetime(dsf["date"])
    erm["date"] = pd.to_datetime(erm["date"])
    dsf["ret"] = pd.to_numeric(dsf["ret"], errors="coerce")
    erm["decret"] = pd.to_numeric(erm["decret"], errors="coerce")

    daily = dsf.merge(erm, on=["permno", "date"], how="left")

    if len(dl):
        dl["date"] = pd.to_datetime(dl["date"])
        dl["dlret"] = pd.to_numeric(dl["dlret"], errors="coerce")
        daily = daily.merge(dl, on=["permno", "date"], how="left")
        r = daily["ret"].fillna(0.0)
        d = daily["dlret"]
        daily["ret"] = np.where(d.notna(), (1 + r) * (1 + d) - 1, daily["ret"])
        daily.drop(columns=["dlret"], inplace=True)

    daily = daily.dropna(subset=["ret"]).copy()
    daily["sar"] = daily["ret"] - daily["decret"].fillna(0.0)
    daily.sort_values(["permno", "date"], inplace=True)

    by_permno = {p: g for p, g in daily.groupby("permno")}

    records = []
    for row in link.itertuples(index=False):
        g = by_permno.get(row.permno)
        rec = {"accessionNumber": row.accessionNumber, "permno": row.permno,
               "filingDate": row.filingDate, "fdr": np.nan, "bhar_12m": np.nan,
               "n_days_bhar": 0, "has_fdr": False, "has_bhar": False}
        if g is not None:
            dates = g["date"].values
            sar = g["sar"].values

            start = np.searchsorted(dates, np.datetime64(row.filingDate))
            if start + FDR_DAYS <= len(dates):
                w = sar[start:start + FDR_DAYS]
                rec["fdr"] = np.prod(1 + w) - 1
                rec["has_fdr"] = True

            window_end_date = (dates[start + FDR_DAYS - 1]
                               if start + FDR_DAYS <= len(dates) else None)
            if window_end_date is not None:
                wend = pd.Timestamp(window_end_date)
                bhar_start_month = (wend + pd.offsets.MonthBegin(1))
                bhar_end = bhar_start_month + pd.DateOffset(months=BHAR_MONTHS)
                mask = (dates >= np.datetime64(bhar_start_month)) & \
                       (dates < np.datetime64(bhar_end))
                wb = sar[mask]
                if len(wb) > 0:
                    rec["bhar_12m"] = np.prod(1 + wb) - 1
                    rec["n_days_bhar"] = int(len(wb))
                    rec["has_bhar"] = True
        records.append(rec)

    out = pd.DataFrame.from_records(records)
    out.to_parquet(OUT_PARQUET, index=False)

    nf = out["has_fdr"].sum()
    nb = out["has_bhar"].sum()
    print(f"\nFDR computed:  {nf:,} / {len(out):,} ({nf/len(out):.1%})")
    print(f"BHAR computed: {nb:,} / {len(out):,} ({nb/len(out):.1%})")
    print(f"median trading days in BHAR window: "
          f"{int(out.loc[out['has_bhar'],'n_days_bhar'].median())}")
    print("\nFDR distribution:")
    print(out["fdr"].describe(percentiles=[.05,.25,.5,.75,.95]).to_string())
    print("\nBHAR_12M distribution:")
    print(out["bhar_12m"].describe(percentiles=[.05,.25,.5,.75,.95]).to_string())
    print(f"\nwrote {OUT_PARQUET}")


if __name__ == "__main__":
    main()
PYEOFcat > code/python/wrds_returns.py << 'PYEOF'
"""FDR + 12-month BHAR construction. RUNS ON THE WRDS JUPYTERHUB.

Input  (already on WRDS): wrds_link_output.csv  [accessionNumber, cik, filingDate, permno]
Output (download to data/pulled/): wrds_returns.parquet
        [accessionNumber, permno, filingDate, fdr, bhar_12m, n_days_bhar, has_fdr, has_bhar]

Method (You & Zhang 2009, faithful):
- size adjustment uses CRSP cap-based decile portfolios (crsp.ermport1), which
  gives each permno-day its decile (capn) and that decile's return (decret).
  size-adjusted daily return = ret - decret.
- FDR = compounded size-adjusted return over the 3 trading days [0, +2] starting
  on the filing date (or the first trading day on/after it).
- BHAR_12M = compounded size-adjusted return over the 12 months starting on the
  first trading day of the calendar month AFTER the 3-day filing window, so the
  FDR and BHAR windows never overlap.
- delisting returns (crsp.dsedelist) are spliced in so firms that disappear
  during the holding year contribute their true terminal return (no upward bias).
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import wrds

IN_CSV = "wrds_link_output.csv"
OUT_PARQUET = "wrds_returns.parquet"

FDR_DAYS = 3
BHAR_MONTHS = 12


def main():
    link = pd.read_csv(IN_CSV, dtype={"accessionNumber": str})
    link["filingDate"] = pd.to_datetime(link["filingDate"])
    link["permno"] = link["permno"].astype(int)
    permnos = sorted(link["permno"].unique())
    dmin = (link["filingDate"].min() - pd.Timedelta(days=10)).date()
    dmax = (link["filingDate"].max() + pd.Timedelta(days=420)).date()
    print(f"{len(link):,} filings, {len(permnos):,} permnos, "
          f"return window {dmin} .. {dmax}")

    db = wrds.Connection()

    permno_list = ",".join(str(p) for p in permnos)
    print("pulling crsp.dsf ...")
    dsf = db.raw_sql(f"""
        SELECT permno, date, ret
        FROM crsp.dsf
        WHERE permno IN ({permno_list})
          AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    print(f"  dsf rows: {len(dsf):,}")

    print("pulling crsp.ermport1 (decile benchmark) ...")
    erm = db.raw_sql(f"""
        SELECT permno, date, decret
        FROM crsp.ermport1
        WHERE permno IN ({permno_list})
          AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    print(f"  ermport1 rows: {len(erm):,}")

    print("pulling crsp.dsedelist (delisting returns) ...")
    dl = db.raw_sql(f"""
        SELECT permno, dlstdt AS date, dlret
        FROM crsp.dsedelist
        WHERE permno IN ({permno_list})
          AND dlret IS NOT NULL
    """)
    print(f"  delist rows: {len(dl):,}")
    db.close()

    dsf["date"] = pd.to_datetime(dsf["date"])
    erm["date"] = pd.to_datetime(erm["date"])
    dsf["ret"] = pd.to_numeric(dsf["ret"], errors="coerce")
    erm["decret"] = pd.to_numeric(erm["decret"], errors="coerce")

    daily = dsf.merge(erm, on=["permno", "date"], how="left")

    if len(dl):
        dl["date"] = pd.to_datetime(dl["date"])
        dl["dlret"] = pd.to_numeric(dl["dlret"], errors="coerce")
        daily = daily.merge(dl, on=["permno", "date"], how="left")
        r = daily["ret"].fillna(0.0)
        d = daily["dlret"]
        daily["ret"] = np.where(d.notna(), (1 + r) * (1 + d) - 1, daily["ret"])
        daily.drop(columns=["dlret"], inplace=True)

    daily = daily.dropna(subset=["ret"]).copy()
    daily["sar"] = daily["ret"] - daily["decret"].fillna(0.0)
    daily.sort_values(["permno", "date"], inplace=True)

    by_permno = {p: g for p, g in daily.groupby("permno")}

    records = []
    for row in link.itertuples(index=False):
        g = by_permno.get(row.permno)
        rec = {"accessionNumber": row.accessionNumber, "permno": row.permno,
               "filingDate": row.filingDate, "fdr": np.nan, "bhar_12m": np.nan,
               "n_days_bhar": 0, "has_fdr": False, "has_bhar": False}
        if g is not None:
            dates = g["date"].values
            sar = g["sar"].values

            start = np.searchsorted(dates, np.datetime64(row.filingDate))
            if start + FDR_DAYS <= len(dates):
                w = sar[start:start + FDR_DAYS]
                rec["fdr"] = np.prod(1 + w) - 1
                rec["has_fdr"] = True

            window_end_date = (dates[start + FDR_DAYS - 1]
                               if start + FDR_DAYS <= len(dates) else None)
            if window_end_date is not None:
                wend = pd.Timestamp(window_end_date)
                bhar_start_month = (wend + pd.offsets.MonthBegin(1))
                bhar_end = bhar_start_month + pd.DateOffset(months=BHAR_MONTHS)
                mask = (dates >= np.datetime64(bhar_start_month)) & \
                       (dates < np.datetime64(bhar_end))
                wb = sar[mask]
                if len(wb) > 0:
                    rec["bhar_12m"] = np.prod(1 + wb) - 1
                    rec["n_days_bhar"] = int(len(wb))
                    rec["has_bhar"] = True
        records.append(rec)

    out = pd.DataFrame.from_records(records)
    out.to_parquet(OUT_PARQUET, index=False)

    nf = out["has_fdr"].sum()
    nb = out["has_bhar"].sum()
    print(f"\nFDR computed:  {nf:,} / {len(out):,} ({nf/len(out):.1%})")
    print(f"BHAR computed: {nb:,} / {len(out):,} ({nb/len(out):.1%})")
    print(f"median trading days in BHAR window: "
          f"{int(out.loc[out['has_bhar'],'n_days_bhar'].median())}")
    print("\nFDR distribution:")
    print(out["fdr"].describe(percentiles=[.05,.25,.5,.75,.95]).to_string())
    print("\nBHAR_12M distribution:")
    print(out["bhar_12m"].describe(percentiles=[.05,.25,.5,.75,.95]).to_string())
    print(f"\nwrote {OUT_PARQUET}")


if __name__ == "__main__":
    main()
