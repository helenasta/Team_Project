"""Prepare the attention-window bridge for the Notre Dame EDGAR log merge.

Runs locally; needs NO log data yet. From the final analysis sample it writes,
for every filing, the identifiers and the calendar window over which the later
log reader will sum non-robot downloads:

    attention window = [filingDate, filingDate + 4]  (5 calendar days, [0,+4])

Why calendar days (not trading days): the ND server logs are calendar-dated and
downloads occur on weekends too; human attention to a filing is not confined to
exchange days. Why [0,+4]: You & Zhang document elevated volume/volatility over
~4 days from the filing date, matching the EDGAR-attention window in Drake,
Roulstone & Thornock (2015).

The accession number is already in dashed SEC form (e.g. 0000893220-03-000441),
which is exactly the format the ND daily files use, so it joins directly.

Output: data/generated/attention_windows.parquet
        [accessionNumber, cik, permno, filingDate, filing_year,
         att_start, att_end]   (att_* are calendar dates, inclusive)
"""

from pathlib import Path
import pandas as pd

PREPARED = Path("data/generated/prepared_data.parquet")
OUT = Path("data/generated/attention_windows.parquet")

WINDOW_DAYS = 4

ND_START = pd.Timestamp("2003-03-01")
ND_END = pd.Timestamp("2015-12-31")
DAMAGED_START = pd.Timestamp("2005-09-23")
DAMAGED_END = pd.Timestamp("2006-05-10")


def main():
    df = pd.read_parquet(PREPARED)
    df["filingDate"] = pd.to_datetime(df["filingDate"])

    out = df[["accessionNumber", "cik", "permno", "filingDate", "filing_year"]].copy()
    out["att_start"] = out["filingDate"]
    out["att_end"] = out["filingDate"] + pd.Timedelta(days=WINDOW_DAYS)

    in_coverage = (out["att_start"] >= ND_START) & (out["att_end"] <= ND_END)
    in_damaged = ~((out["att_end"] < DAMAGED_START) | (out["att_start"] > DAMAGED_END))
    out["log_usable"] = in_coverage & (~in_damaged)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)

    print(f"total filings in final sample:        {len(out):,}")
    print(f"  within ND coverage (2003-03..2015):  {in_coverage.sum():,}")
    print(f"  in damaged period (2005-09..2006-05):{in_damaged.sum():,}")
    print(f"  -> usable for attention measure:     {out['log_usable'].sum():,}")
    print(f"\nattention window = [filingDate, +{WINDOW_DAYS}d] calendar days")
    print(f"saved -> {OUT}")
    print("\nsample rows:")
    print(out.head(3).to_string(index=False))


if __name__ == "__main__":
    main()
