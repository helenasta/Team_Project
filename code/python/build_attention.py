"""Build the investor-attention measure from Notre Dame EDGAR server logs.

Input:
  data/external/nd_logs/**/f_YYYYMMDD.csv   daily non-robot download files
        columns: date, cik, accession, nr_total, htm, txt, xbrl, other, form, filing_date
  data/generated/attention_windows.parquet  per-filing [att_start, att_end] window

Logic:
  For each daily file, the file's calendar date is parsed from its name. We keep
  only rows whose accession is in our sample AND whose day falls within that
  filing's attention window [filingDate, filingDate+4]. Downloads are then summed
  per filing over its window, giving:
        att_nr_total : all non-robot downloads in the window
        att_htm      : non-robot downloads of the human-readable web form (htm)

Robot filtering is already done by Notre Dame (Loughran & McDonald 2017): web
crawlers, index requests, server codes >=300, and >=50 downloads/IP/day are
excluded upstream, so these counts are non-robot by construction.

Output: data/pulled/attention_downloads.parquet
        [accessionNumber, att_nr_total, att_htm, att_days_with_dl]

Run on a single quarter first (point NDLOG_DIR at it) to validate, then over all.
"""

from pathlib import Path
import sys
import pandas as pd

NDLOG_DIR = Path("data/external/nd_logs")
WINDOWS = Path("data/generated/attention_windows.parquet")
OUT = Path("data/pulled/attention_downloads.parquet")

USECOLS = ["date", "accession", "nr_total", "htm"]


def main():
    win = pd.read_parquet(WINDOWS)
    win["att_start"] = pd.to_datetime(win["att_start"])
    win["att_end"] = pd.to_datetime(win["att_end"])
    sample_acc = set(win["accessionNumber"])
    wmap = win.set_index("accessionNumber")[["att_start", "att_end"]]
    print(f"sample filings with windows: {len(win):,}")

    files = sorted(NDLOG_DIR.rglob("f_*.csv"))
    if not files:
        sys.exit(f"No f_*.csv files found under {NDLOG_DIR}")
    print(f"daily log files found: {len(files):,}")

    acc = {}
    n_kept_rows = 0

    for i, fp in enumerate(files, 1):
        try:
            fday = pd.Timestamp(fp.stem.split("_")[1])
        except Exception:
            continue
        try:
            df = pd.read_csv(fp, usecols=USECOLS, dtype={"accession": str})
        except Exception:
            continue
        if df.empty:
            continue

        df = df[df["accession"].isin(sample_acc)]
        if df.empty:
            continue

        w = wmap.reindex(df["accession"].values)
        in_window = (fday >= w["att_start"].values) & (fday <= w["att_end"].values)
        df = df[in_window]
        if df.empty:
            continue

        n_kept_rows += len(df)
        for r in df.itertuples(index=False):
            a = r.accession
            cur = acc.get(a)
            nt = int(r.nr_total) if pd.notna(r.nr_total) else 0
            ht = int(r.htm) if pd.notna(r.htm) else 0
            if cur is None:
                acc[a] = [nt, ht, 1]
            else:
                cur[0] += nt
                cur[1] += ht
                cur[2] += 1

        if i % 100 == 0 or i == len(files):
            print(f"  ...{i}/{len(files)} files, "
                  f"{len(acc):,} filings matched, {n_kept_rows:,} rows kept",
                  flush=True)

    out = pd.DataFrame(
        [(a, v[0], v[1], v[2]) for a, v in acc.items()],
        columns=["accessionNumber", "att_nr_total", "att_htm", "att_days_with_dl"],
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)

    print(f"\nfilings with >=1 in-window download: {len(out):,}")
    if len(out):
        print("\nattention download distribution (nr_total):")
        print(out["att_nr_total"].describe(
            percentiles=[.05, .25, .5, .75, .95]).to_string())
        print("\nattention download distribution (htm):")
        print(out["att_htm"].describe(
            percentiles=[.05, .25, .5, .75, .95]).to_string())
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
