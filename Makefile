# RCT 2026 Team Project pipeline
#
# TWO PHASES:
#  (1) LOCAL phase, automated by `make`: prep -> attention -> analysis ->
#      figures -> presentation.
#  (2) WRDS phase, run ONCE manually on the WRDS JupyterHub (needs 2FA):
#      produces licensed CRSP/Compustat files in data/pulled/. NOT committed;
#      `make` cannot regenerate them. Provided on HU-Box. See README.
#
# `make` assumes the WRDS-derived files and the Notre Dame logs are already
# in place (from HU-Box): data/pulled/wrds_*.parquet and
# data/external/nd_logs/. See README for setup.

all: output/presentation.pdf

# ---- data preparation ----------------------------------------------------
data/pulled/edgar_10k_metadata.parquet: code/python/pull_data.py
	mkdir -p data/pulled
	uv run python code/python/pull_data.py

data/generated/prepared_data.parquet: code/python/prep_data.py data/pulled/edgar_10k_metadata.parquet data/pulled/wrds_returns.parquet data/pulled/wrds_controls.parquet
	mkdir -p data/generated
	uv run python code/python/prep_data.py

data/generated/attention_windows.parquet: code/python/prep_attention_windows.py data/generated/prepared_data.parquet
	uv run python code/python/prep_attention_windows.py

# attention downloads (needs the Notre Dame logs in data/external/nd_logs/)
data/pulled/attention_downloads.parquet: code/python/build_attention.py data/generated/attention_windows.parquet
	uv run python code/python/build_attention.py

# ---- analysis ------------------------------------------------------------
# run_analysis writes the bundle; analysis_attention appends to it.
output/analysis_results.pkl: code/python/run_analysis.py code/python/analysis_attention.py data/generated/prepared_data.parquet data/pulled/attention_downloads.parquet
	mkdir -p output
	uv run python code/python/run_analysis.py
	uv run python code/python/analysis_attention.py

# ---- figures -------------------------------------------------------------
# ticker_crosscheck also appends its result to the bundle; plots read the bundle.
figures: output/analysis_results.pkl
	-uv run python code/python/ticker_crosscheck.py
	-uv run python code/python/plot_volume.py
	-uv run python code/python/plot_coefficients.py
	-uv run python code/python/plot_ticker_check.py
	-uv run python code/python/plot_att_size_corr.py

# ---- presentation --------------------------------------------------------
output/presentation.pdf: doc/presentation.qmd output/analysis_results.pkl data/generated/attention_windows.parquet figures
	cd doc && uv run quarto render presentation.qmd --output presentation.pdf
	rm -f doc/presentation.tex doc/presentation.log doc/presentation.aux doc/presentation.out doc/presentation.knit.md
	rm -rf output/presentation_files

# ---- WRDS phase (manual, on JupyterHub) ----------------------------------
wrds-inputs: code/python/export_link_input.py code/python/export_reportdate.py data/generated/prepared_data.parquet
	uv run python code/python/export_link_input.py
	uv run python code/python/export_reportdate.py
	@echo "Upload the CSVs to WRDS JupyterHub, run the wrds_*.py scripts, download outputs to data/pulled/. See README."

clean:
	rm -rf data/generated output .quarto doc/.quarto
	rm -f doc/*.tex doc/*.log doc/*.aux doc/*.out doc/*.knit.md

.PHONY: all figures wrds-inputs clean
