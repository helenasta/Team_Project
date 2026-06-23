"""Export a minimal CIK/date list for the WRDS-side CIK->PERMNO linking.

Reads the prepared filing sample and writes a small CSV containing only the
fields needed to resolve PERMNO on WRDS: cik, accessionNumber, filingDate.
This file is uploaded to the WRDS JupyterHub; the linking runs there.
"""

from pathlib import Path
import duckdb

PREPARED = Path("data/generated/prepared_data.parquet")
OUT = Path("data/pulled/wrds_link_input.csv")

con = duckdb.connect()
OUT.parent.mkdir(parents=True, exist_ok=True)
con.execute(f"""
    COPY (
        SELECT DISTINCT
            cik,
            accessionNumber,
            filingDate
        FROM '{PREPARED.as_posix()}'
        WHERE cik IS NOT NULL
        ORDER BY cik, filingDate
    )
    TO '{OUT.as_posix()}' (FORMAT 'csv', HEADER true)
""")
n = con.execute(f"SELECT COUNT(*) FROM '{OUT.as_posix()}'").fetchone()[0]
size_mb = OUT.stat().st_size / 1024**2
print(f"{n:,} rows -> {OUT}  ({size_mb:.1f} MB)")
con.close()
