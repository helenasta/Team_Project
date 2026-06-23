# RCT 2026 Team Project pipeline
#
# TWO PHASES:
#  (1) LOCAL phase, automated by `make`: TRR266 pull -> prep -> attention
#      windows -> analysis -> presentation.
#  (2) WRDS phase, run ONCE manually on the WRDS JupyterHub (needs 2FA):
#      produces licensed CRSP/Compustat files in data/pulled/. NOT committed;
#      `make` cannot regenerate them. See README.

all: output/presentation.pdf

data/pulled/edgar_10k_metadata.parquet: code/python/pull_data.py
	mkdir -p data/pulled
	uv run python code/python/pull_data.py

data/generated/prepared_data.parquet: code/python/prep_data.py data/pulled/edgar_10k_metadata.parquet data/pulled/wrds_returns.parquet data/pulled/wrds_controls.parquet
	mkdir -p data/generated
	uv run python code/python/prep_data.py

data/generated/attention_windows.parquet: code/python/prep_attention_windows.py data/generated/prepared_data.parquet
	uv run python code/python/prep_attention_windows.py

output/analysis_results.pkl: code/python/run_analysis.py data/generated/prepared_data.parquet
	mkdir -p output
	uv run python code/python/run_analysis.py

output/presentation.pdf: doc/presentation.qmd output/analysis_results.pkl data/generated/attention_windows.parquet
	cd doc && uv run quarto render presentation.qmd --output presentation.pdf
	rm -f doc/presentation.tex doc/presentation.log doc/presentation.aux doc/presentation.out doc/presentation.knit.md
	rm -rf output/presentation_files

wrds-inputs: code/python/export_link_input.py code/python/export_reportdate.py data/generated/prepared_data.parquet
	uv run python code/python/export_link_input.py
	uv run python code/python/export_reportdate.py
	@echo "Upload the two CSVs to WRDS JupyterHub, run wrds_link/returns/controls.py, download outputs to data/pulled/. See README."

clean:
	rm -rf data/generated output .quarto doc/.quarto
	rm -f doc/*.tex doc/*.log doc/*.aux doc/*.out doc/*.knit.md

.PHONY: all wrds-inputs clean
