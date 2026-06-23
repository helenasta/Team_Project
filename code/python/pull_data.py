"""Pull EDGAR 10-K filing metadata from the TRR266 server.

The dataset is exposed as ~1,800 remote parquet files over plain HTTPS.
Scanning all of them in a single query is unreliable: DuckDB issues an HTTP
request per file and a single slow response aborts the whole query (HTTP
timeout). We therefore pull file-by-file, filter each file down to our sample
in SQL, and concatenate the small results in memory before writing once.

Sample restriction (fixed for this project):
- filing date 2003-2017, bound by the continuous EDGAR server-log window
- 10-K form types only (10-K, 10-K405, 10-KSB, 10-KSB405); amendments (10-K/A)
  and transition reports are thereby excluded, following You & Zhang (2009)
- heavy text columns (filing_raw_html, filing_markdown) are NOT pulled;
  filing_word_count is kept as the disclosure-length / complexity proxy
"""

from pathlib import Path
from urllib.parse import urljoin
import time

import duckdb
import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://trr266.wiwi.hu-berlin.de/edgar_10k_apr26/"
EDGAR_OUTPUT = Path("data/pulled/edgar_10k_metadata.parquet")

# --- sample definition -------------------------------------------------------
START_DATE = "2003-01-01"
END_DATE = "2017-12-31"
FORM_TYPES = ("10-K", "10-K405", "10-KSB", "10-KSB405")

# --- HTTP robustness ---------------------------------------------------------
HTTP_TIMEOUT_MS = 120_000   # 120s per request
HTTP_RETRIES = 5
PROGRESS_EVERY = 100


def main():
    con = duckdb.connect()
    pull_edgar_metadata(con)
    con.close()


def list_parquet_files(base_url):
    response = requests.get(base_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    return sorted(
        urljoin(base_url, a["href"])
        for a in soup.find_all("a")
        if a.get("href", "").lower().endswith(".parquet")
    )


def configure_http(con):
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET enable_http_metadata_cache = true;")
    con.execute(f"SET http_timeout = {HTTP_TIMEOUT_MS};")
    con.execute(f"SET http_retries = {HTTP_RETRIES};")


def file_query(url):
    """Metadata-only SELECT for a single remote parquet file, pre-filtered
    to the project sample. Text columns are deliberately excluded."""
    form_list = ", ".join(f"'{f}'" for f in FORM_TYPES)
    return f"""
        SELECT
            TRY_CAST(cik AS BIGINT) AS cik,
            name,
            tickers,
            exchanges,
            entityType,
            TRY_CAST(sic AS BIGINT) AS sic,
            sicDescription,
            stateOfIncorporation,
            form,
            filingDate,
            reportDate,
            accessionNumber,
            primaryDocUrl,
            size,
            TRY_CAST(filing_word_count AS BIGINT) AS filing_word_count,
            download_success,
            download_error
        FROM parquet_scan(['{url}'], union_by_name = true)
        WHERE filingDate >= '{START_DATE}'
          AND filingDate <= '{END_DATE}'
          AND form IN ({form_list})
    """


def pull_edgar_metadata(con):
    configure_http(con)
    urls = list_parquet_files(BASE_URL)
    print(f"  found {len(urls)} remote parquet files", flush=True)

    parts = []
    failed = []
    t0 = time.perf_counter()
    for i, url in enumerate(urls, 1):
        try:
            parts.append(con.execute(file_query(url)).fetchdf())
        except Exception as e:  # noqa: BLE001 - skip a flaky file, report later
            failed.append((url, str(e)[:80]))
        if i % PROGRESS_EVERY == 0 or i == len(urls):
            kept = sum(len(p) for p in parts)
            print(f"  ...{i}/{len(urls)} files "
                  f"[{time.perf_counter() - t0:.0f}s, "
                  f"{kept:,} rows kept, {len(failed)} failed]", flush=True)

    if failed:
        print(f"  WARNING: {len(failed)} files failed after retries:", flush=True)
        for u, msg in failed[:10]:
            print(f"    {u.split('/')[-1]}: {msg}", flush=True)

    combined = pd.concat(parts, ignore_index=True)

    EDGAR_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    con.register("combined", combined)
    con.execute(f"""
        COPY (SELECT * FROM combined)
        TO '{EDGAR_OUTPUT.as_posix()}' (FORMAT 'parquet')
    """)
    print(f"  {len(combined):,} rows -> {EDGAR_OUTPUT}", flush=True)

    breakdown = con.execute("""
        SELECT form, SUBSTR(filingDate, 1, 4) AS yr, COUNT(*) AS n
        FROM combined
        GROUP BY form, yr
        ORDER BY yr, form
    """).fetchdf()
    print("\n  filings by form type and year:", flush=True)
    print(breakdown.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
