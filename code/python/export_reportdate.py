"""Export accessionNumber -> reportDate for the WRDS controls pull."""
from pathlib import Path
import duckdb

con = duckdb.connect()
con.execute("""
    COPY (
        SELECT DISTINCT accessionNumber, reportDate
        FROM 'data/generated/prepared_data.parquet'
        WHERE reportDate IS NOT NULL
    )
    TO 'data/pulled/wrds_reportdate.csv' (FORMAT 'csv', HEADER true)
""")
n = con.execute("SELECT COUNT(*) FROM 'data/pulled/wrds_reportdate.csv'").fetchone()[0]
print(f"{n:,} rows -> data/pulled/wrds_reportdate.csv")
con.close()
