from pathlib import Path
from urllib.parse import urljoin

import duckdb
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://trr266.wiwi.hu-berlin.de/edgar_10k_apr26/"
EDGAR_OUTPUT = Path("data/pulled/edgar_10k_metadata.parquet")


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


def duckdb_list_literal(urls):
    escaped = [url.replace("'", "''") for url in urls]
    return "['" + "','".join(escaped) + "']"


def pull_edgar_metadata(con):
    parquet_urls = list_parquet_files(BASE_URL)
    file_list = duckdb_list_literal(parquet_urls)

    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET enable_http_metadata_cache = true;")

    con.execute(f"""
        CREATE OR REPLACE VIEW edgar_10k AS
        SELECT
            cik, name, tickers, exchanges, entityType,
            TRY_CAST(sic AS BIGINT) AS sic, sicDescription,
            stateOfIncorporation, form, filingDate, reportDate,
            accessionNumber, primaryDocUrl, size,
            TRY_CAST(filing_word_count AS BIGINT) AS filing_word_count,
            download_success, download_error
        FROM parquet_scan({file_list}, union_by_name = true)
    """)

    EDGAR_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    n = con.execute(f"""
        COPY (SELECT * FROM edgar_10k)
        TO '{EDGAR_OUTPUT.as_posix()}'
        (FORMAT 'parquet')
    """).fetchone()[0]
    print(f"  {n:,} rows → {EDGAR_OUTPUT}")


if __name__ == "__main__":
    main()
