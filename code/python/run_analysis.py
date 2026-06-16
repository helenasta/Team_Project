import pickle
from pathlib import Path

import pandas as pd
from great_tables import GT
from plotnine import (
    aes,
    element_blank,
    element_text,
    geom_line,
    geom_point,
    ggplot,
    labs,
    scale_x_continuous,
    theme,
    theme_minimal,
)


def main():
    Path("output").mkdir(parents=True, exist_ok=True)

    data = pd.read_parquet("data/generated/prepared_data.parquet")
    annual = pd.read_parquet("data/generated/annual_summary.parquet")

    annual_table = prepare_annual_table(annual)

    first_year = int(annual["filing_year"].min())
    last_year = int(annual["filing_year"].max())
    highlights = {
        "sample_size": int(len(data)),
        "year_range": f"{first_year}–{last_year}",
        "n_firms": int(data["cik_int"].nunique()),
        "median_words_first": int(
            annual.loc[annual["filing_year"] == first_year, "median_words"].iloc[0]
        ),
        "median_words_last": int(
            annual.loc[annual["filing_year"] == last_year, "median_words"].iloc[0]
        ),
    }

    results = {
        "annual_table": annual_table,
        "annual_data": annual,
        "highlights": highlights,
    }

    with Path("output/results.pkl").open("wb") as f:
        pickle.dump(results, f)


def make_length_figure(annual_data):
    return (
        ggplot(annual_data, aes(x="filing_year", y="median_words"))
        + geom_line(size=0.8, color="#1b6ca8")
        + geom_point(size=1.8, color="#1b6ca8")
        + scale_x_continuous(breaks=[1995, 2000, 2005, 2010, 2015, 2020])
        + labs(
            x="Filing year",
            y="Median word count",
        )
        + theme_minimal(base_size=11)
        + theme(
            panel_grid_minor=element_blank(),
            axis_text_x=element_text(rotation=45, hjust=1),
        )
    )


def prepare_annual_table(annual_data):
    df = annual_data.copy()
    df["filing_year"] = df["filing_year"].astype(int)
    df["n_filings"] = df["n_filings"].apply(lambda x: f"{int(x):,}")
    df["n_firms"] = df["n_firms"].apply(lambda x: f"{int(x):,}")
    df["median_words"] = df["median_words"].apply(lambda x: f"{int(x):,}")
    df["mean_words"] = df["mean_words"].apply(lambda x: f"{int(x):,}")
    return (
        GT(df)
        .cols_label(
            filing_year="Year",
            n_filings="Filings",
            n_firms="Firms",
            median_words="Median words",
            mean_words="Mean words",
        )
        .cols_align(align="right", columns=["n_filings", "n_firms", "median_words", "mean_words"])
        .tab_options(table_font_size="12pt", data_row_padding="2.5pt")
    )


if __name__ == "__main__":
    main()
