"""Prepare the analysis-ready 10-K sample (final version).

Merges four building blocks on accessionNumber:
  data/pulled/edgar_10k_metadata.parquet   filing metadata + filing_word_count
  data/pulled/wrds_returns.parquet          fdr, bhar_12m
  data/pulled/wrds_controls.parquet         mktcap, size, bm, mom, beta

Then applies the You & Zhang (2009) economic screens and finalises variables:
  1. filing-side cleaning (dedup, late filers, one-per-firm-year, word floor)
  2. require usable fdr + bhar_12m
  3. market-cap screen: mktcap >= $200m
  4. recompute COMPLEX as the ANNUAL median split of filing_word_count ON THE
     FINAL sample
  5. winsorize fdr, bhar_12m, bm, mom, beta at 1%/99%

Output: data/generated/prepared_data.parquet  (analysis-ready, one row per filing)
        data/generated/annual_summary.parquet
"""

from pathlib import Path
import duckdb
import pandas as pd

PULLED = Path("data/pulled")
META = PULLED / "edgar_10k_metadata.parquet"
RETURNS = PULLED / "wrds_returns.parquet"
CONTROLS = PULLED / "wrds_controls.parquet"

PREPARED_OUT = Path("data/generated/prepared_data.parquet")
ANNUAL_OUT = Path("data/generated/annual_summary.parquet")

MIN_WORD_COUNT = 1000
LATE_FILER_DAYS = 120
MIN_MKTCAP = 200.0
WINSOR = 0.01


def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def winsorize(s, p):
    lo, hi = s.quantile(p), s.quantile(1 - p)
    return s.clip(lo, hi)


def main():
    con = duckdb.connect()
    Path("data/generated").mkdir(parents=True, exist_ok=True)
    funnel = []

    funnel.append(("0. raw filing rows", scalar(con, f"SELECT COUNT(*) FROM '{META.as_posix()}'")))

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE clean AS
        WITH dedup AS (
            SELECT * EXCLUDE (rn) FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY accessionNumber
                          ORDER BY filing_word_count DESC) rn
                FROM '{META.as_posix()}'
            ) WHERE rn = 1
        ), lagged AS (
            SELECT *,
                DATE_DIFF('day', CAST(reportDate AS DATE), CAST(filingDate AS DATE)) AS report_lag,
                CAST(SUBSTR(filingDate,1,4) AS INTEGER) AS filing_year
            FROM dedup
        ), no_late AS (
            SELECT * FROM lagged WHERE report_lag IS NOT NULL AND report_lag <= {LATE_FILER_DAYS}
        ), one_py AS (
            SELECT * EXCLUDE (rn) FROM (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY cik, reportDate
                          ORDER BY filingDate ASC, accessionNumber ASC) rn
                FROM no_late
            ) WHERE rn = 1
        )
        SELECT * FROM one_py WHERE filing_word_count >= {MIN_WORD_COUNT}
    """)
    funnel.append(("1. after filing cleaning", scalar(con, "SELECT COUNT(*) FROM clean")))

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE merged AS
        SELECT c.*,
               r.permno, r.fdr, r.bhar_12m, r.has_fdr, r.has_bhar,
               k.mktcap, k.size, k.bm, k.mom, k.beta
        FROM clean c
        LEFT JOIN '{RETURNS.as_posix()}'  r USING (accessionNumber)
        LEFT JOIN '{CONTROLS.as_posix()}' k USING (accessionNumber)
    """)

    con.execute("""
        CREATE OR REPLACE TEMP TABLE with_rets AS
        SELECT * FROM merged WHERE has_fdr AND has_bhar
                              AND fdr IS NOT NULL AND bhar_12m IS NOT NULL
    """)
    funnel.append(("2. with usable fdr + bhar", scalar(con, "SELECT COUNT(*) FROM with_rets")))

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE screened AS
        SELECT * FROM with_rets WHERE mktcap IS NOT NULL AND mktcap >= {MIN_MKTCAP}
    """)
    funnel.append((f"3. mktcap >= ${int(MIN_MKTCAP)}m", scalar(con, "SELECT COUNT(*) FROM screened")))

    df = con.execute("SELECT * FROM screened").fetchdf()
    con.close()

    df["wc_year_median"] = df.groupby("filing_year")["filing_word_count"].transform("median")
    df["complex"] = (df["filing_word_count"] > df["wc_year_median"]).astype(int)

    for c in ["fdr", "bhar_12m", "bm", "mom", "beta"]:
        df[c] = winsorize(df[c], WINSOR)

    df = df.sort_values(["filing_year", "cik"]).reset_index(drop=True)
    df.to_parquet(PREPARED_OUT, index=False)

    annual = (df.groupby("filing_year")
                .agg(n_filings=("accessionNumber", "size"),
                     n_unique_cik=("cik", "nunique"),
                     median_word_count=("filing_word_count", "median"),
                     n_high_complexity=("complex", "sum"),
                     median_mktcap=("mktcap", "median"))
                .reset_index())
    annual.to_parquet(ANNUAL_OUT, index=False)

    print("=== SAMPLE SELECTION FUNNEL ===")
    prev = None
    for label, n in funnel:
        delta = "" if prev is None else f"   (-{prev - n:,})"
        print(f"  {label:<32} {n:>8,}{delta}")
        prev = n
    print(f"\n  FINAL analysis sample: {len(df):,}")
    print(f"  prepared -> {PREPARED_OUT}")

    print("\n=== ANNUAL SUMMARY ===")
    print(annual.to_string(index=False))

    print("\n=== VARIABLE COVERAGE (final sample) ===")
    for c in ["fdr", "bhar_12m", "complex", "size", "bm", "mom", "beta"]:
        print(f"  {c:9s}: {df[c].notna().sum():,} / {len(df):,}")


if __name__ == "__main__":
    main()
