"""Trading volume around the 10-K filing date. RUNS ON THE WRDS JUPYTERHUB.

Reproduces You & Zhang (2009) Figure 1, Panel A: average scaled trading volume
over the 21 trading days [-10, +10] centered on the filing date.

Input  (already on WRDS): wrds_link_output.csv [accessionNumber, cik, filingDate, permno]
Output (download to data/pulled/): wrds_volume_event.parquet
        [event_day, mean_scaled_volume, n]

Scaled volume = shares traded / shares outstanding (as in the paper), so large
and small firms are comparable. For each filing we locate the filing trading
day, take the 21-day window around it, and average across all filings by event
day (relative day -10 .. +10).
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import wrds

IN_CSV = "wrds_link_output.csv"
OUT = "wrds_volume_event.parquet"
WIN = 10  # days each side


def main():
    link = pd.read_csv(IN_CSV, dtype={"accessionNumber": str})
    link["filingDate"] = pd.to_datetime(link["filingDate"])
    link["permno"] = link["permno"].astype(int)
    permnos = sorted(link["permno"].unique())
    permno_list = ",".join(str(p) for p in permnos)
    dmin = (link["filingDate"].min() - pd.Timedelta(days=40)).date()
    dmax = (link["filingDate"].max() + pd.Timedelta(days=40)).date()
    print(f"{len(link):,} filings, {len(permnos):,} permnos")

    db = wrds.Connection()
    print("pulling crsp.dsf (vol, shrout) ...")
    dsf = db.raw_sql(f"""
        SELECT permno, date, vol, shrout
        FROM crsp.dsf
        WHERE permno IN ({permno_list})
          AND date BETWEEN '{dmin}' AND '{dmax}'
    """)
    db.close()
    dsf["date"] = pd.to_datetime(dsf["date"])
    dsf["vol"] = pd.to_numeric(dsf["vol"], errors="coerce").astype("float64")
    dsf["shrout"] = pd.to_numeric(dsf["shrout"], errors="coerce").astype("float64")
    # scaled volume: shares traded / shares outstanding (shrout is in 1000s)
    dsf["scaled_vol"] = dsf["vol"] / (dsf["shrout"] * 1000.0)
    dsf = dsf.dropna(subset=["scaled_vol"])
    print(f"  dsf rows: {len(dsf):,}")

    # per-permno sorted date + scaled-vol arrays for fast windowing
    by_permno = {p: (g["date"].values, g["scaled_vol"].values)
                 for p, g in dsf.sort_values(["permno", "date"]).groupby("permno")}

    # accumulate sum and count per event day
    span = 2 * WIN + 1
    sums = np.zeros(span)
    counts = np.zeros(span)

    for r in link.itertuples(index=False):
        pair = by_permno.get(r.permno)
        if pair is None:
            continue
        dates, sv = pair
        start = np.searchsorted(dates, np.datetime64(r.filingDate))
        # need the filing day itself present and a full window
        if start >= len(dates):
            continue
        lo = start - WIN
        hi = start + WIN
        if lo < 0 or hi >= len(dates):
            continue
        window = sv[lo:hi + 1]
        if len(window) == span:
            sums += window
            counts += 1

    ev = pd.DataFrame({
        "event_day": np.arange(-WIN, WIN + 1),
        "mean_scaled_volume": sums / np.where(counts == 0, np.nan, counts),
        "n": counts.astype(int),
    })
    ev.to_parquet(OUT, index=False)
    print(f"\nfilings used per event day (approx): {int(ev['n'].max()):,}")
    print(ev.to_string(index=False))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
