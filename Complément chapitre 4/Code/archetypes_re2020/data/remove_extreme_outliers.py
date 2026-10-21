import polars as pl
from tqdm import tqdm

from archetypes_re2020.data.source import INPUT_PATHS, OUTPUT_PATHS

COL_STAT = "ic_composant"

def outliers(df,value_col,prefix_new_cols = None) :
    """
    Add mild and extreme outliers columns to a dataframe from stats 
    on value_col

    Args:
        df (pl.DataFrame): Polars dataframe on which columns will be added
        value_col (string): name of the column to do stats on 

    Returns:
        df (pl.DataFrame): return the dataframe with outliers boolean 
        added. Modification in place as well.
    """
    q1 = df.quantile(0.25, "nearest")[value_col][0]
    q3 = df.quantile(0.75, "nearest")[value_col][0]
    iqr = q3 - q1
    low_mild = q1-1.5*iqr
    low_extreme = q1-3*iqr
    high_mild = q3+1.5*iqr
    high_extreme = q3+3*iqr

    if prefix_new_cols is None : 
        prefix_new_cols = value_col

    mild_outliers = f"{prefix_new_cols}_mild_outliers"
    extreme_outliers = f"{prefix_new_cols}_extreme_outliers"

    df = df.with_columns(
        (
            (
            (pl.col(value_col) < low_mild) 
            & (pl.col(value_col) >= low_extreme)
            ) | (
            (pl.col(value_col) > high_mild )
            & (pl.col(value_col) <= high_extreme)
            )
            ).alias(mild_outliers)
    )
    df = df.with_columns(
        (
            (pl.col(value_col)<low_extreme)
            | (pl.col(value_col)>high_extreme)
        ).alias(extreme_outliers)
    )

    return df

def remove_outliers_and_save() :
    df_buildings = pl.read_csv(
    source=INPUT_PATHS["BUILDINGS"], ignore_errors=True
    )
    to_export = outliers(df_buildings,COL_STAT).filter(
        pl.col("extreme_outliers") == False
        )
    to_export.write_csv(OUTPUT_PATHS["BUILDINGS_WO_EXTREME_OUTLIER"])


if __name__ == "__main__":
    remove_outliers_and_save()
    print(f"{INPUT_PATHS["BUILDINGS"]} copied in \
        {OUTPUT_PATHS["BUILDINGS_WO_EXTREME_OUTLIER"]} \
            without extreme outliers on {COL_STAT}.")