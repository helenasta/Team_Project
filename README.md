# RCT 2026 Team Project — Investor Attention and the Post-10-K Drift

This project builds on You & Zhang (2009) and asks:

> **Is the 12-month stock-price drift following a 10-K filing larger for filings
> that receive low investor attention around the filing date?**

We measure the immediate market reaction to a 10-K with the **filing date return
(FDR)**, the subsequent **12-month buy-and-hold abnormal return (BHAR)**, and
investor attention with **non-robot EDGAR downloads** in the filing window
(Notre Dame SRAF server-log data, following Loughran & McDonald 2017 and Drake,
Roulstone & Thornock 2015).

Sample period: **2003–2017** for the drift analysis (bounded by the TRR266 10-K
data and the EDGAR server-log window), narrowing to **2003–2015** for the
attention analysis (the limit of the Notre Dame compressed log series).

## Pipeline — two phases

The project runs in two phases because one step requires WRDS, which needs
two-factor authentication and therefore cannot run inside Codespaces.

### Phase 1 — local (automated by `make`)

```text
pull_data.py              TRR266 EDGAR 10-K metadata  -> data/pulled/edgar_10k_metadata.parquet
prep_data.py              clean + merge + screens     -> data/generated/prepared_data.parquet
prep_attention_windows.py attention windows bridge    -> data/generated/attention_windows.parquet
run_analysis.py           drift regression (Table 3)  -> output/analysis_results.pkl
doc/presentation.qmd      reads the results bundle     -> output/presentation.pdf
```

Run the whole local phase with:

```bash
make
```

### Phase 2 — WRDS (run once, manually, on the WRDS JupyterHub)

CRSP/Compustat are licensed and reachable only through WRDS with 2FA. We run the
WRDS-dependent step on the **WRDS JupyterHub**, where the database connection
needs no per-call 2FA, then download the small results back into `data/pulled/`.

Steps:

1. Locally, generate the upload inputs:
```bash
   make wrds-inputs
```
   This writes `data/pulled/wrds_link_input.csv` and `wrds_reportdate.csv`.
2. Log in to the **WRDS JupyterHub** (Duo 2FA once). Upload those two CSVs and
   the three WRDS scripts: `wrds_link.py`, `wrds_returns.py`, `wrds_controls.py`.
3. In the JupyterHub terminal run, in order:
```bash
   python wrds_link.py        # CIK -> PERMNO link        -> wrds_link_output.csv
   python wrds_returns.py     # FDR + 12-month BHAR        -> wrds_returns.parquet
   python wrds_controls.py    # mktcap, BM, beta, momentum -> wrds_controls.parquet
```
4. Download those three outputs back into `data/pulled/`.

After Phase 2 has been done once, Phase 1 (`make`) runs end to end.

## Data folders

- `data/pulled/` — raw inputs. TRR266 metadata + the licensed WRDS-derived files.
  **Not committed** (license + size); see `.gitignore`.
- `data/generated/` — prepared datasets built from the above. Not committed.
- `output/` — the serialized results bundle and the rendered presentation.

Because CRSP/Compustat are licensed, the WRDS-derived files cannot be shared in
the repository. Reproducibility is therefore **conditional on WRDS access**: the
scripts document exactly which tables, fields, and filters are used, which is the
reproducible part. Anyone with WRDS access can regenerate the pulls via Phase 2.

## Key variable definitions

- **FDR** — size-adjusted return over the 3 trading days `[0,+2]` from the filing
  date; size adjustment uses CRSP cap-based decile portfolios (`crsp.ermport1`).
- **BHAR_12M** — size-adjusted buy-and-hold return over the 12 months starting the
  month after the filing window; delisting returns spliced in.
- **COMPLEX** — annual median split of `filing_word_count` on the final sample.
- **Attention (planned)** — non-robot EDGAR downloads in `[filingDate, +4]`
  calendar days, size-adjusted, annual median split into a `LOWATT` indicator.

## Current status

- Phase 1 and Phase 2 complete; final analysis sample = **23,135** filings.
- Drift (Table 3): FDR coefficient positive; significant univariately, marginal
  (p≈0.06) with full controls — consistent with a weaker post-2005 drift.
- Attention measure: **pending** the Notre Dame log data (access requested). The
  bridge in `attention_windows.parquet` flags **17,213** filings as usable once
  the logs arrive.

## References

You, H., & Zhang, X. (2009). Financial reporting complexity and investor
underreaction to 10-K information. *Review of Accounting Studies*, 14, 559–586.
See `doc/references.bib` for the full bibliography.
