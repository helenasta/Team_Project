"""Ticker cross-check: validate the CIK->PERMNO match by comparing the
filing-time ticker (TRR266) against the CRSP ticker valid at the filing date.

Inputs (local): data/pulled/ticker_check_input.csv  [accessionNumber, permno, filingDate, tickers]
                data/pulled/crsp_tickers.csv         [permno, ticker, namedt, nameenddt, comnam]

Categories per filing:
  exact      filing ticker == CRSP ticker valid at the filing date
  other_time filing ticker matches some CRSP ticker of that permno, other window
  mismatch   filing ticker matches no CRSP ticker of that permno
  no_crsp    permno has no CRSP ticker record at all
"""
from pathlib import Path
import pandas as pd

SAMP = Path("data/pulled/ticker_check_input.csv")
CRSP = Path("data/pulled/crsp_tickers.csv")


def norm(t):
    if pd.isna(t):
        return set()
    s = str(t).upper()
    for ch in "[]'\" ":
        s = s.replace(ch, "")
    # split on pipe, comma, semicolon
    parts = s.replace("|", ",").replace(";", ",").split(",")
    out = set()
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.add(p)
        # also add the base ticker without a preferred-share suffix (CODI-PA -> CODI)
        if "-" in p:
            out.add(p.split("-")[0])
    return out


def main():
    samp = pd.read_csv(SAMP, dtype={"permno": "Int64"})
    samp["filingDate"] = pd.to_datetime(samp["filingDate"])
    crsp = pd.read_csv(CRSP, dtype={"permno": "Int64"})
    crsp["namedt"] = pd.to_datetime(crsp["namedt"])
    crsp["nameenddt"] = pd.to_datetime(crsp["nameenddt"])
    crsp["ticker"] = crsp["ticker"].astype(str).str.upper().str.strip()

    # group CRSP tickers by permno for fast lookup
    all_by_permno = crsp.groupby("permno")["ticker"].apply(set).to_dict()

    cats = []
    for r in samp.itertuples(index=False):
        ft = norm(r.tickers)
        recs = crsp[crsp["permno"] == r.permno]
        if recs.empty:
            cats.append("no_crsp"); continue
        # CRSP tickers valid at the filing date
        valid = recs[(recs["namedt"] <= r.filingDate) &
                     (recs["nameenddt"] >= r.filingDate)]
        valid_tk = set(valid["ticker"])
        all_tk = all_by_permno.get(r.permno, set())
        if ft & valid_tk:
            cats.append("exact")
        elif ft & all_tk:
            cats.append("other_time")
        else:
            cats.append("mismatch")

    samp["category"] = cats
    n = len(samp)
    counts = samp["category"].value_counts()
    print("=== TICKER CROSS-CHECK ===")
    for c in ["exact", "other_time", "mismatch", "no_crsp"]:
        k = int(counts.get(c, 0))
        print(f"  {c:11s}: {k:5d}  ({k/n:5.1%})")
    good = int(counts.get("exact", 0) + counts.get("other_time", 0))
    print(f"\n  match (exact + other_time): {good:5d}  ({good/n:.1%})")

    print("\n  sample mismatches (inspect for real errors):")
    mm = samp[samp["category"] == "mismatch"].head(8)
    for r in mm.itertuples(index=False):
        crsp_tk = sorted(all_by_permno.get(r.permno, set()))
        print(f"    permno {r.permno}  filing={r.tickers}  crsp={crsp_tk}")


if __name__ == "__main__":
    main()
