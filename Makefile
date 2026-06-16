all: output/presentation.pdf

data/pulled/edgar_10k_metadata.parquet: code/python/pull_data.py
	mkdir -p data/pulled
	uv run python code/python/pull_data.py

data/generated/prepared_data.parquet: code/python/prep_data.py data/pulled/edgar_10k_metadata.parquet
	mkdir -p data/generated
	uv run python code/python/prep_data.py

output/results.pkl: code/python/run_analysis.py data/generated/prepared_data.parquet
	mkdir -p output
	uv run python code/python/run_analysis.py

output/presentation.pdf: doc/presentation.qmd output/results.pkl
	cd doc && uv run quarto render presentation.qmd --output presentation.pdf
	rm -f doc/presentation.tex doc/presentation.log doc/presentation.aux doc/presentation.out doc/presentation.knit.md
	rm -rf output/presentation_files

clean:
	rm -rf data/pulled data/generated output .quarto doc/.quarto
	rm -f doc/*.tex doc/*.log doc/*.aux doc/*.out doc/*.knit.md
