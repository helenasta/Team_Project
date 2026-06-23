"""CIK -> PERMNO linking. RUNS ON THE WRDS JUPYTERHUB, not in Codespaces.

Why here: WRDS PostgreSQL needs MFA from external hosts, but inside the WRDS
Cloud / JupyterHub the connection needs no per-call 2FA. So we run the single
WRDS-dependent step here, then carry a small CSV back to the repo.

Input  (upload to JupyterHub): wrds_link_input.csv  [cik, accessionNumber, filingDate]
Output (download to data/pulled/): wrds_link_output.csv
        [accessionNumber, cik, filingDate, gvkey, permno]

Linking path (standard CCM route):
    EDGAR cik --(comp.company)--> gvkey --(crsp.ccmxpf_lnkhist)--> permno
respecting each link's validity window [linkdt, linkenddt] against filingDate,
keeping reliable link types (LC/LU) and primary links (P/C), preferring P.
"""

import datetime as dt

import pandas as pd
import wrds

IN_CSV = "wrds_link_input.csv"
OUT_CSV = "wrds_link_output.csv"


def main():
    filings = pd.read_csv(IN_CSV, dtype={"cik": "Int64", "accessionNumber": str})
    filings["filingDate"] = pd.to_datetime(filings["filingDate"])
    print(f"loaded {len(filings):,} filings, {filings['cik'].nunique():,} unique CIK")

    db = wrds.Connection()  # inside WRDS: no MFA prompt

    company = db.raw_sql("""
        SELECT gvkey, cik
        FROM comp.company
        WHERE cik IS NOT NULL
    """)
    company["cik"] = pd.to_numeric(company["cik"], errors="coerce").astype("Int64")
    company = company.dropna(subset=["cik"]).drop_duplicates(["cik", "gvkey"])
    print(f"comp.company: {len(company):,} cik-gvkey pairs")

    link = db.raw_sql("""
        SELECT gvkey, lpermno AS permno, linktype, linkprim, linkdt, linkenddt
        FROM crsp.ccmxpf_lnkhist
        WHERE linktype IN ('LC', 'LU')
          AND linkprim IN ('P', 'C')
          AND lpermno IS NOT NULL
    """)
    link["linkdt"] = pd.to_datetime(link["linkdt"])
    link["linkenddt"] = pd.to_datetime(link["linkenddt"]).fillna(
        pd.Timestamp(dt.date.today())
    )
    print(f"ccm link history: {len(link):,} gvkey-permno links")

    db.close()

    step1 = filings.merge(company, on="cik", how="left")
    matched_gvkey = step1["gvkey"].notna().sum()
    print(f"matched to gvkey: {matched_gvkey:,} / {len(filings):,} "
          f"({matched_gvkey / len(filings):.1%})")

    step2 = step1.merge(link, on="gvkey", how="left")
    valid = step2[
        (step2["filingDate"] >= step2["linkdt"])
        & (step2["filingDate"] <= step2["linkenddt"])
    ].copy()

    valid["prim_rank"] = (valid["linkprim"] == "P").astype(int)
    valid = (valid.sort_values(["accessionNumber", "prim_rank"], ascending=[True, False])
                  .drop_duplicates("accessionNumber", keep="first"))

    out = valid[["accessionNumber", "cik", "filingDate", "gvkey", "permno"]].copy()
    out["permno"] = out["permno"].astype("Int64")
    out.to_csv(OUT_CSV, index=False)

    n_match = len(out)
    print(f"\nFINAL: {n_match:,} / {len(filings):,} filings linked to PERMNO "
          f"({n_match / len(filings):.1%})")
    print(f"wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
