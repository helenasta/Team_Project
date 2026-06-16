# RCT Summer 2026: Template for the Team Project

This repository is the **Python version of a barebones project template**. It is meant to be small enough to understand quickly, but structured enough to grow into a real project.

The main idea is simple:

- data are pulled into `data/pulled/`
- data are prepared into `data/generated/`
- analysis writes a serialized results bundle to `output/`
- the presentation slide deck in `doc/` reads those saved results

The example replicates the 10-K word count trend from Dyer, Lang & Stice-Lawrence (2017) using EDGAR filing metadata, and extends their sample to 2023.

## What You Are Looking At

This repository gives you a minimal project skeleton with four visible stages:

1. `code/python/pull_data.py`
2. `code/python/prep_data.py`
3. `code/python/run_analysis.py`
4. `doc/presentation.qmd`

The workflow is organized like a real empirical project. If you later look at `trr266/treat`, you will see the same broad movement in a richer and more elaborate form.

## Project Structure

```text
.devcontainer/
.python-version
README.md
Makefile
pyproject.toml
uv.lock
code/python/pull_data.py
code/python/prep_data.py
code/python/run_analysis.py
data/
  external/
  pulled/
  generated/
  data_readme.md
doc/
  presentation.qmd
  references.bib
info/
  edgar_10k_intro.qmd
output/
```

## How The Workflow Moves

The workflow is intentionally explicit:

1. `pull_data.py` fetches EDGAR 10-K filing metadata from the TRR266 server via DuckDB over HTTPS and writes `data/pulled/edgar_10k_metadata.parquet`
2. `prep_data.py` deduplicates, filters, and feature-engineers the raw metadata into `data/generated/prepared_data.parquet` and `data/generated/annual_summary.parquet`
3. `run_analysis.py` reads the prepared data and writes a serialized `.pkl` results bundle to `output/`
4. `doc/presentation.qmd` reads that `.pkl` bundle and renders the beamer slide deck

The presentation does **not** rerun the full analysis pipeline internally. It uses prepared results from `output/`.

## The `data/` Folder

The `data/` folder keeps the same conceptual separation used in `treat`:

- `data/external/`: files that come from outside the repository and are kept as source material
- `data/pulled/`: raw data written by a pull step
- `data/generated/`: prepared datasets created from raw or external inputs

## The `info/` Folder

`info/edgar_10k_intro.qmd` is a standalone tutorial that shows how to access and query the EDGAR 10-K dataset directly. It is not part of the analysis pipeline but provides a helpful reference for understanding the data source.

## References

The presentation cites Dyer, Lang & Stice-Lawrence (2017) and uses `doc/references.bib` for the bibliography.

## Recommended Setup Paths

There are three ways to work with this repo:

1. **GitHub Codespaces**
   This is the recommended path.
2. **Local VS Code + Docker Dev Containers**
   This is the recommended local path.
3. **Fully local install**
   This is possible, but not recommended.

### 1. GitHub Codespaces

1. Use this template on GitHub to create your own repository.
2. Open your repository in Codespaces.
3. Wait for the devcontainer to finish building.
4. Wait for the post-create step to finish running `uv sync`.
5. In the Codespaces terminal, run:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
gh auth login
make
```

The repository-local virtual environment lives at `.venv/`. Codespaces should detect it automatically and use it as the Python interpreter. The interpreter itself is managed by `uv`, which downloads the Python version pinned in `.python-version`.

### 2. Local VS Code + Docker Dev Containers

1. Install Docker.
2. Install VS Code plus the Dev Containers extension.
3. Open the repository in VS Code.
4. Run `Dev Containers: Reopen in Container` from the Command Palette.
5. Wait for the devcontainer build and the post-create `uv sync` step to finish.
6. In the integrated terminal inside the container, run:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
gh auth login
make
```

The devcontainer keeps the project virtual environment in `.venv/` and configures VS Code to use it automatically. `uv` also manages the Python interpreter for that environment, so the container image does not need to ship the project Python version directly.

### 3. Fully Local Install

You can also run the project outside containers, but this is **not recommended** unless you are comfortable managing the stack yourself:

- `uv`
- Quarto
- a LaTeX installation capable of rendering PDFs
- Git and optionally GitHub CLI

If you choose this route, run:

```bash
uv sync
source .venv/bin/activate
make
```

## Main Project Command

Run the whole project from the repository root with:

```bash
make
```

The Makefile runs the full pipeline in order:

1. `code/python/pull_data.py`
2. `code/python/prep_data.py`
3. `code/python/run_analysis.py`
4. `doc/presentation.qmd`

## Container Notes

Both Codespaces and the local devcontainer path provide:

- `uv`
- `git`
- `gh`
- Quarto
- TinyTeX

In both container paths, `uv` downloads and manages the Python interpreter pinned for the project. This keeps the working environment consistent across students without baking the project Python version into the base image.

## AI Prompts for Common Tasks

Two ready-made prompts are included to help you work with the project configuration using an LLM assistant.

- **`makefile_prompt.md`** — use this if you want to understand how the `Makefile` works or need help adapting it to your own pipeline.
- **`docker_devcontainer_prompt.md`** — use this if you run into errors with the `.devcontainer/` setup or want to understand how the `Dockerfile` and `devcontainer.json` interact.

In each file, replace the text inside the `{{ }}` blocks with your own input, then paste the whole prompt into an LLM of your choice.
