"""Pull CRSP ticker history for the sampled permnos. RUNS ON WRDS JUPYTERHUB.

For each permno we get all tickers and their validity windows from
crsp.stocknames, so the local check can compare the filing-time ticker against
the CRSP ticker that was valid at the filing date.

Input  (upload): ticker_check_input.csv [accessionNumber, permno, filingDate, tickers]
Output (download to data/pulled/): crsp_tickers.csv [permno, ticker, namedt, nameenddt, comnam]
"""
import warnings
warnings.filterwarnings("ignore")
import pandas as pd
import wrds

link = pd.read_csv("ticker_check_input.csv")
permnos = sorted(link["permno"].dropna().astype(int).unique())
permno_list = ",".join(str(p) for p in permnos)

db = wrds.Connection()
sn = db.raw_sql(f"""
    SELECT permno, ticker, namedt, nameenddt, comnam
    FROM crsp.stocknames
    WHERE permno IN ({permno_list})
""")
db.close()

sn.to_csv("crsp_tickers.csv", index=False)
print(f"{len(sn):,} ticker records for {len(permnos):,} permnos -> crsp_tickers.csv")
print(sn.head(5).to_string(index=False))
