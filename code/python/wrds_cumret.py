"""Cumulative size-adjusted return at 12 monthly checkpoints after the 10-K
filing. RUNS ON THE WRDS JUPYTERHUB. For You & Zhang (2009) Figure 4.

Input  (already on WRDS): wrds_link_output.csv [accessionNumber, cik, filingDate, permno]
Output (download to data/pulled/): wrds_cumret.parquet
        [accessionNumber, permno, m1, m2, ..., m12]
  where mK = cumulative size-adjusted return from BHAR start through month K.

Same construction as wrds_returns.py: daily size-adjusted return = ret - decret
(crsp.ermport1 decile benchmark), delisting return spliced in, BHAR window
starts the first trading day of the month after the 3-day filing window. We
record the running compounded return at the end of each of the 12 months.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import wrds

IN_CSV = "wrds_link_output.csv"
OUT = "wrds_cumret.parquet"
FDR_DAYS = 3
MONTHS = 12


def main():
    link = pd.read_csv(IN_CSV, dtype={"accessionNumber": str})
    link["filingDate"] = pd.to_datetime(link["filingDate"])
    link["permno"] = link["permno"].astype(int)
    permnos = sorted(link["permno"].unique())
    permno_list = ",".join(str(p) for p in permnos)
    dmin = (link["filingDate"].min() - pd.Timedelta(days=10)).date()
    dmax = (link["filingDate"].max() + pd.Timedelta(days=430)).date()
    print(f"{len(link):,} filings, {len(permnos):,} permnos")

    db = wrds.Connection()
    print("pulling crsp.dsf ...")
    dsf = db.raw_sql(f"""
        SELECT permno, date, ret FROM crsp.dsf
        WHERE permno IN ({permno_list}) AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    print("pulling crsp.ermport1 ...")
    erm = db.raw_sql(f"""
        SELECT permno, date, decret FROM crsp.ermport1
        WHERE permno IN ({permno_list}) AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    print("pulling crsp.dsedelist ...")
    dl = db.raw_sql(f"""
        SELECT permno, dlstdt AS date, dlret FROM crsp.dsedelist
        WHERE permno IN ({permno_list}) AND dlret IS NOT NULL
    """)
    db.close()

    dsf["date"] = pd.to_datetime(dsf["date"]); erm["date"] = pd.to_datetime(erm["date"])
    dsf["ret"] = pd.to_numeric(dsf["ret"], errors="coerce")
    erm["decret"] = pd.to_numeric(erm["decret"], errors="coerce")
    daily = dsf.merge(erm, on=["permno", "date"], how="left")
    if len(dl):
        dl["date"] = pd.to_datetime(dl["date"])
        dl["dlret"] = pd.to_numeric(dl["dlret"], errors="coerce")
        daily = daily.merge(dl, on=["permno", "date"], how="left")
        r = daily["ret"].fillna(0.0); d = daily["dlret"]
        daily["ret"] = np.where(d.notna(), (1 + r) * (1 + d) - 1, daily["ret"])
        daily.drop(columns=["dlret"], inplace=True)
    daily = daily.dropna(subset=["ret"]).copy()
    daily["sar"] = daily["ret"] - daily["decret"].fillna(0.0)
    daily.sort_values(["permno", "date"], inplace=True)

    by_permno = {p: (g["date"].values, g["sar"].values)
                 for p, g in daily.groupby("permno")}

    rows = []
    for r in link.itertuples(index=False):
        pair = by_permno.get(r.permno)
        rec = {"accessionNumber": r.accessionNumber, "permno": r.permno}
        for k in range(1, MONTHS + 1):
            rec[f"m{k}"] = np.nan
        if pair is not None:
            dates, sar = pair
            start = np.searchsorted(dates, np.datetime64(r.filingDate))
            if start + FDR_DAYS <= len(dates):
                wend = pd.Timestamp(dates[start + FDR_DAYS - 1])
                bhar_start = wend + pd.offsets.MonthBegin(1)
                for k in range(1, MONTHS + 1):
                    m_end = bhar_start + pd.DateOffset(months=k)
                    mask = (dates >= np.datetime64(bhar_start)) & \
                           (dates < np.datetime64(m_end))
                    w = sar[mask]
                    if len(w) > 0:
                        rec[f"m{k}"] = np.prod(1 + w) - 1
        rows.append(rec)

    out = pd.DataFrame(rows)
    out.to_parquet(OUT, index=False)
    print(f"\nfilings with m12: {out['m12'].notna().sum():,} / {len(out):,}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
