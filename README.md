# RCT 2026 Team Project — Investor Attention and the Post-10-K Drift

This project builds on You & Zhang (2009) and asks:

> **Is the 12-month stock-price drift following a 10-K filing larger for filings
> that receive low investor attention around the filing date?**

We measure the immediate market reaction to a 10-K with the **filing date return
(FDR)**, the subsequent **12-month buy-and-hold abnormal return (BHAR)**, and
investor attention with **non-robot EDGAR downloads** in the filing window
(Notre Dame SRAF server-log data, following Loughran & McDonald 2017 and Drake,
Roulstone & Thornock 2015).

Sample period: **2003 to 2015** for the drift analysis (bounded by the TRR266
10-K data), narrowing to **2003 to 2015** for the attention analysis (the limit
of the Notre Dame log series).

The active branch for this project is **`python`**.

## Repository and data

The code lives in this repository. The data are **not** committed, for two
reasons: the WRDS-derived files contain licensed CRSP/Compustat data, and the
Notre Dame logs are large. The data are provided separately on HU-Box.

### HU-Box data folders

- `data_pulled/` — the contents of `data/pulled/` (TRR266 metadata + the
  WRDS-derived files): https://box.hu-berlin.de/d/687bcc46f54e420d8ce2/
- `nd_logs/` — the Notre Dame EDGAR server logs, one archive per year
  (`nd_logs_2003.tar.gz` … `nd_logs_2015.tar.gz`):
  https://box.hu-berlin.de/d/005fb213d90f46fdae94/
- `output/` — the results bundle `analysis_results.pkl`:
  https://box.hu-berlin.de/d/46161726b7614d4f87f5/

The files in `data_pulled/` contain licensed CRSP/Compustat data.

## How to reproduce

### 1. Clone the repository (branch `python`)

```bash
git clone -b python <repo-url>
cd Team_Project
```

### 2. Create the data folders (if starting from a fresh checkout)

```bash
mkdir -p data/pulled data/external data/generated output
```

### 3. Download the data from HU-Box and place it

- Put every file from the HU-Box `data_pulled/` folder into `data/pulled/`.
- Put the yearly log archives into `data/external/nd_logs/` and extract them:

```bash
cd /workspaces/Team_Project/data/external/nd_logs && for f in nd_logs_*.tar.gz; do tar -xzf "$f"; done && cd /workspaces/Team_Project
```

This should create `data/external/nd_logs/` with yearly subfolders
(`2003/QTR1/f_YYYYMMDD.csv`, …).

### 4. Run the pipeline

```bash
make
```

> **Optional shortcut:** the pipeline recreates `output/analysis_results.pkl`
> itself. If you only want to view the presentation without running the full
> pipeline (which needs the Notre Dame logs), copy `analysis_results.pkl`
> from the HU-Box `output/` folder into `output/` and render the slides directly.

This runs the local phase end to end (prepare data, build the attention windows,
run the analyses, render the presentation to `output/presentation.pdf`).

## Pipeline — two phases

The project runs in two phases because one step requires WRDS, which needs
two-factor authentication and cannot run inside Codespaces.

### Phase 1 — local (automated by `make`)

```text
pull_data.py               TRR266 EDGAR 10-K metadata   -> data/pulled/edgar_10k_metadata.parquet
prep_data.py               clean + merge + screens      -> data/generated/prepared_data.parquet
prep_attention_windows.py  attention windows bridge     -> data/generated/attention_windows.parquet
build_attention.py         count downloads per filing   -> data/pulled/attention_downloads.parquet
run_analysis.py            drift regression             -> output/analysis_results.pkl
analysis_attention.py      attention interaction model  -> output/analysis_results.pkl (appended)
doc/presentation.qmd       reads the results bundle     -> output/presentation.pdf
```

### Phase 2 — WRDS (run once, manually, on the WRDS JupyterHub)

CRSP/Compustat are licensed and reachable only through WRDS with 2FA. We run the
WRDS-dependent scripts on the **WRDS JupyterHub**, where the connection needs no
per-call 2FA, then download the results into `data/pulled/`. The provided
HU-Box `data_pulled/` folder already contains these outputs, so Phase 2 only
needs to be repeated to regenerate them from scratch.

1. Locally, generate the upload inputs:

```bash
make wrds-inputs
```

2. Log in to the WRDS JupyterHub (Duo 2FA once). Upload the input CSVs and the
   WRDS scripts (`wrds_link.py`, `wrds_returns.py`, `wrds_controls.py`,
   `wrds_volume.py`, `wrds_cumret.py`, `wrds_ticker_pull.py`).
3. Run them in the JupyterHub terminal, then download their outputs back into
   `data/pulled/`.

## Data folders

- `data/pulled/` — raw inputs (TRR266 metadata + WRDS-derived files). Not committed.
- `data/external/nd_logs/` — Notre Dame server logs. Not committed.
- `data/generated/` — prepared datasets built locally by `make`. Not committed.
- `output/` — the results bundle, figures, and the rendered presentation.

Reproducibility is **conditional on data access**: the code fully documents which
WRDS tables, fields, and filters are used, and the derived data are provided on
HU-Box for graders with the appropriate access.

## Key variable definitions

- **FDR** — size-adjusted return over the 3 trading days `[0,+2]` from the filing
  date; size adjustment uses CRSP cap-based decile portfolios (`crsp.ermport1`).
- **BHAR_12M** — size-adjusted buy-and-hold return over the 12 months starting the
  month after the filing window; delisting returns spliced in.
- **LOWATT** — non-robot EDGAR downloads in `[filingDate, +4]` calendar days,
  size- and year-adjusted (residual on SIZE per year); `LOWATT=1` below the
  annual median.
- **COMPLEX** — annual median split of `filing_word_count` on the final sample.
- **Controls** — beta, size, book-to-market, momentum.

## Results

- Final drift sample: **23,135** filings; attention sample: **17,213**.
- **Drift exists but is weak:** FDR positive, significant univariately, marginal
  with full controls (t ≈ 1.9), roughly a third of You & Zhang's magnitude
  (consistent with post-publication decay, McLean & Pontiff 2016).
- **Attention does not moderate the drift:** the FDR × LOWATT interaction is
  effectively zero (t ≈ -0.16), and the FDR coefficient is nearly identical in
  the low- and high-attention subsamples. A clean null result.
- **Validation:** a ticker cross-check confirms **93.4%** of a random sample of
  matched filings, supporting the CIK-PERMNO match.

## Validation and robustness

- `ticker_crosscheck.py` — independent CIK-PERMNO check against CRSP tickers.
- `plot_volume.py` — trading volume around the filing (You & Zhang Fig. 1).
- `plot_fig4.py` — cumulative returns by FDR quintile (You & Zhang Fig. 4).
- `plot_coefficients.py` — coefficient plots with confidence intervals.

## References

You, H., & Zhang, X. (2009). Financial reporting complexity and investor
underreaction to 10-K information. *Review of Accounting Studies*, 14, 559–586.
See `doc/references.bib` for the full bibliography.
