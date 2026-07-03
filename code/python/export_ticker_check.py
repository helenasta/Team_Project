"""Export a random sample of matched filings with their filing-time tickers,
for the ticker cross-check validation. Local, no WRDS.
"""
from pathlib import Path
import pandas as pd

META = Path("data/pulled/edgar_10k_metadata.parquet")
LINK = Path("data/pulled/wrds_link_output.csv")
OUT = Path("data/pulled/ticker_check_input.csv")
N = 1000
SEED = 42

meta = pd.read_parquet(META)[["accessionNumber", "tickers"]]
link = pd.read_csv(LINK, dtype={"accessionNumber": str})

df = link.merge(meta, on="accessionNumber", how="inner")
df = df[df["tickers"].notna() & (df["tickers"].astype(str).str.len() > 0)]
sample = df.sample(n=min(N, len(df)), random_state=SEED)

sample[["accessionNumber", "permno", "filingDate", "tickers"]].to_csv(OUT, index=False)
print(f"{len(sample):,} filings -> {OUT}")
print(sample[["permno", "filingDate", "tickers"]].head(5).to_string(index=False))
