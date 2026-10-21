import numpy as np
import polars as pl
from scipy import stats
import warnings
import questionary
from tqdm import tqdm

from archetypes_re2020.config import PROCESSED_DATA_DIR

from archetypes_re2020.utils.utils import *

import warnings
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import archetypes_re2020.data.source as source
from archetypes_re2020.buildings.add_consumptions import CONSUMPTIONS_TO_ADD, WATER_CONSUMPTIONS_RATIOS
from archetypes_re2020.config import RAW_DATA_DIR, PROCESSED_DATA_DIR

from datetime import datetime


# Constantes
DEFAULT_QUANTILE = "1.0"
INPUT_FILE = source.OUTPUT_PATHS["AUGMENTED_QUANTITIES"]
OUTPUT_FILENAME_PATTERN = "{year}-{month}-{day}-{hour}h{minute}_intensites_matieres_RE2020"
LOGNORM_FIELDS = ["shape", "loc", "scale"]
PER = 50


def get_lognorm(
    values: Sequence[Union[int, float, None]],
    quantile: float = 1.0,
) -> Optional[List[float]]:
    """
    Fit a lognormal distribution to the lower ``quantile`` of 
    positive, finite data.

    Args:
        values : An iterable containing floats or int or None 
        quantile : Quantile (between 0 and 1) used to truncate the data 
            before fitting.``1.0`` (default) fits the whole filtered sample.

    Returns:
        list of three floats ``[shape, loc, scale]`` if fitting succeeds,
        otherwise ``None``. A ``RuntimeWarning`` is emitted when the filtered 
        list is empty.
    """
    arr = np.asarray(values, dtype=float)
    # Keep only finite, positive numbers (NaNs / infs become False)
    mask = np.isfinite(arr) & (arr > 0)
    filtered = arr[mask]

    if filtered.size == 0:
        warnings.warn("Empty list. Skipping fit.", RuntimeWarning)
        return None

    # Truncate to the requested quantile
    q_val = np.quantile(filtered, quantile)
    truncated = filtered[filtered <= q_val]

    # Fit log‑normal with fixed location = 0
    shape, loc, scale = stats.lognorm.fit(truncated, floc=0)
    return [shape, loc, scale]


def get_nb_bat(df: pl.DataFrame, usage: str) -> int:
    """
    Count distinct building identifiers for a given usage label.

    Args:
        df : Polars ``DataFrame`` that contains at least the columns
            ``usage_principal_1_txt``, ``projet_id`` and ``batiment_index``.
        usage : The usage string to filter on (exact match).

    Returns:
        int : Number of unique ``(projet_id, batiment_index)`` pairs where
            ``usage_principal_1_txt`` equals ``usage``.

    """
    return (
        df.filter(
        (pl.col("usage_principal_1_txt") == usage)
        ).n_unique(subset=["projet_id", "batiment_index"])
    )

def get_target_lengths(df: pl.DataFrame, usages: pl.Series) -> dict[str, int]:
    """Computes the target number of buildings per usage."""
    return {u: get_nb_bat(df, u) for u in usages}

def aggregate_material_intensities(
    df: pl.DataFrame, target_len_map: dict[str, int]
    ) -> pl.DataFrame:
    """
    Aggregates material intensities and add a column with the 
    target building count.

    Args:
        df (pl.DataFrame): Polars dataframe with material intensities
        
        target_len_map (dict[str, int]): dict with usages as keys and
            number of buildings per usage as values.

    Returns:
        pl.DataFrame: Polars dataframe aggregated by product and usage
    """
    return (
        df.group_by(["usage_principal_1_txt", "nomenclatures_UF_dve"])
        .agg(pl.col("quant_surf"))
        .with_columns(
            pl.col("usage_principal_1_txt")
            .replace(target_len_map, return_dtype=pl.Int32)
            .alias("target_len")
        )
        .drop_nulls()
    )

def aggregate_consumptions_intensities(
    df: pl.DataFrame, target_len_map: dict[str, int]
    ) -> pl.DataFrame:
    """Aggregates consumptions intensities and add a column with the 
    target building count.

    Args:
        df (pl.DataFrame): Dataframe with every buidings and their consumptions
        target_len_map (dict[str, int]): dict with usages as keys and
            number of buildings per usage as values.

    Returns:
        pl.DataFrame: _description_
    """
    df = df.with_columns(
        cons_eau_tout=(
            pl.col("nb_occupant")
            * pl.col("usage_principal_1_txt").replace_strict(WATER_CONSUMPTIONS_RATIOS)
            / pl.col("sref")
        )
    ).with_columns(
        [pl.col(c)*PER for c in ["cons_eau_tout", *CONSUMPTIONS_TO_ADD]]
        )

    return (
        df.group_by(["usage_principal_1_txt"])
        .agg([pl.col(c) for c in ["cons_eau_tout",*CONSUMPTIONS_TO_ADD]])
        .with_columns(
        # On enlève les 0 des listes pour le calcul du param de Bernoulli
        [pl.col(c).list.filter(pl.element() != 0) for c in ["cons_eau_tout", *CONSUMPTIONS_TO_ADD]]
        )
        .with_columns(
            pl.col("usage_principal_1_txt")
            .replace(target_len_map, return_dtype=pl.Int32)
            .alias("target_len")
        )
        .drop_nulls()
    )

def unpivot_df_building(df : pl.DataFrame) :

    return df.unpivot(
        on=["cons_eau_tout",*CONSUMPTIONS_TO_ADD],
        index= ["usage_principal_1_txt","target_len"],
        variable_name="produit",
        value_name= "quant_surf"
    ).filter(
        #On enlève les lignes où la liste est vide
        pl.col("quant_surf").list.len() > 0
    )


def compute_bernoulli_parameter(df: pl.DataFrame) -> pl.DataFrame:
    """
    Computes the Bernoulli parameter.
    Le paramètre de Bernoulli représente la probabilité qu'un produit 
    soit présent dans un bâtiment d'un usage donné
    """
    return df.with_columns([
        # Native Polars optimization: Calculate Bernoulli without Python lambda
        pl.min_horizontal(
            pl.col("quant_surf").list.len() / pl.col("target_len"), 
            1.0
        ).alias("param_bernoulli")
    ])

def fit_lognormal_distribution(df: pl.DataFrame, quantile: float) -> pl.DataFrame:
    """
    Ajuste une distribution lognormale aux données d'intensité matière.

    Args:
        df (pl.DataFrame): DataFrame avec colonne 'quant_surf' contenant les listes d'intensités.
        quantile (float): Quantile à utiliser pour l'ajustement (entre 0 et 1).

    Returns:
        pl.DataFrame: DataFrame avec colonnes shape, loc, scale de la distribution lognormale.
    """
    return df.with_columns(
        pl.col("quant_surf").map_elements(
            lambda x: get_lognorm(x, quantile) or [float("nan")] * 3,
            return_dtype=pl.List(pl.Float64)
        ).alias("param_lognorm")
    )

def unnest_lognormal_parameters(df: pl.DataFrame) -> pl.DataFrame:
    """
    Crée des colonnes séparées pour les paramètres de la distribution
    lognormale. 

    Args:
        df (pl.DataFrame): DataFrame avec colonne 'param_lognorm' 
            contenant [shape, loc, scale].

    Returns:
        pl.DataFrame: DataFrame avec colonnes shape, loc, scale.
    """
    return (
        df.with_columns(
            pl.col("param_lognorm").list.to_struct(fields=LOGNORM_FIELDS)
        )
        .unnest("param_lognorm")
        .rename({
            "usage_principal_1_txt": "usage",
            "nomenclatures_UF_dve": "produit"
        })
    )

def unnest_lognormal_parameters_consumptions(df: pl.DataFrame) -> pl.DataFrame:
    """
    Crée des colonnes séparées pour les paramètres de la distribution
    lognormale. 

    Args:
        df (pl.DataFrame): DataFrame avec colonne 'param_lognorm' 
            contenant [shape, loc, scale].

    Returns:
        pl.DataFrame: DataFrame avec colonnes shape, loc, scale.
    """
    return (
        df.with_columns(
            pl.col("param_lognorm").list.to_struct(fields=LOGNORM_FIELDS)
        )
        .unnest("param_lognorm")
        .rename({
            "usage_principal_1_txt": "usage",
        })
    )

def prepare_and_fit_distributions(df: pl.DataFrame, target_len_map: dict[str, int], quantile: float) -> pl.DataFrame:
    """
    Pipeline complet de préparation et d'ajustement des distributions.

    Args:
        df (pl.DataFrame): DataFrame source avec intensités matières.
        target_len_map (dict[str, int]): Dictionnaire des nombres cibles de bâtiments par usage.
        quantile (float): Quantile pour l'ajustement lognormal.

    Returns:
        pl.DataFrame: DataFrame final avec paramètres Bernoulli et lognormaux.
    """
    return (
        df
        .pipe(aggregate_material_intensities, target_len_map)
        .pipe(compute_bernoulli_parameter)
        .pipe(fit_lognormal_distribution, quantile)
        .pipe(unnest_lognormal_parameters)
    )

def prepare_and_fit_distributions_consumptions(df: pl.DataFrame, target_len_map: dict[str, int], quantile: float) -> pl.DataFrame:
    """
    Pipeline complet de préparation et d'ajustement des distributions.

    Args:
        df (pl.DataFrame): DataFrame source avec intensités matières.
        target_len_map (dict[str, int]): Dictionnaire des nombres cibles de bâtiments par usage.
        quantile (float): Quantile pour l'ajustement lognormal.

    Returns:
        pl.DataFrame: DataFrame final avec paramètres Bernoulli et lognormaux.
    """
    return (
        df
        .pipe(aggregate_consumptions_intensities, target_len_map)
        .pipe(unpivot_df_building)
        .pipe(compute_bernoulli_parameter)
        .pipe(fit_lognormal_distribution, quantile)
        .pipe(unnest_lognormal_parameters_consumptions)
    )


def ask_quantile_value() -> float:
    """
    Demande à l'utilisateur le quantile à utiliser pour l'ajustement.

    Returns:
        float: Valeur du quantile entre 0 et 1.
    """
    return float(questionary.text(
        "Quel quantile de la partie non-nulle de l'échantillon faut-il fitter ?",
        default=DEFAULT_QUANTILE
    ).ask())


def generate_output_filename() -> str:
    """
    Génère le nom du fichier de sortie avec horodatage.

    Returns:
        str: Chemin complet du fichier de sortie.
    """
    now = datetime.today()
    filename = OUTPUT_FILENAME_PATTERN.format(
        year=now.year,
        month=now.month,
        day=now.day,
        hour=now.hour,
        minute=now.minute
    )
    return f"{PROCESSED_DATA_DIR}/{filename}.xlsx"


def export_to_excel(df: pl.DataFrame, filepath: str):
    """
    Exporte le DataFrame au format Excel.

    Args:
        df (pl.DataFrame): DataFrame à exporter.
        filepath (str): Chemin du fichier de sortie.
    """
    df.write_excel(filepath)
    print(f"Données exportées vers : {filepath}")

def generate_usages_list(df: pl.DataFrame) :
    """
    Create a list of all buildings uses contained in the dataframe.

    Args:
        df (pl.DataFrame): Polars dataframe with a "usage_principal_1_txt"
            column.

    Returns:
        list: list of usages.
    """
    return(
        df.select(
            pl.col("usage_principal_1_txt").unique()
            ).drop_nulls()["usage_principal_1_txt"]
    ) 


def main(df_modif: pl.DataFrame, usages: pl.Series):
    """
    Pipeline principal d'ajustement des distributions et d'export.

    Args:
        df_modif (pl.DataFrame): DataFrame prétraité avec intensités matières.
        usages (pl.Series): Liste des usages de bâtiments à analyser.
    """
    # Calcul des longueurs cibles par usage
    print("Calcul du nombre de bâtiments par usage...")
    target_lengths = get_target_lengths(df_modif, usages)
    
    # Demande du quantile
    user_quantile = ask_quantile_value()
    
    # Préparation et ajustement des distributions
    print("Ajustement des distributions...")
    df_distributions = prepare_and_fit_distributions(
        df_modif,
        target_lengths,
        user_quantile
    )
    
    # Export
    output_path = generate_output_filename()
    export_to_excel(df_distributions, output_path)
    
    return df_distributions

def main_consumptions(df_buildings: pl.DataFrame, usages : pl.Series):
    print("Calcul du nombre de bâtiments par usage...")
    target_lengths = get_target_lengths(df_buildings, usages)

    # Demande du quantile
    user_quantile = ask_quantile_value()

    print("Ajustement des distributions...")
    df_distributions = prepare_and_fit_distributions_consumptions(
        df_buildings,
        target_lengths,
        user_quantile
    )
    now = datetime.today()
    output_path = PROCESSED_DATA_DIR / f"{now.year}-{now.month}-{now.day}-{now.hour}h{now.minute}_intensites_consos_RE2020.xlsx"
    df_distributions.write_excel(output_path)


if __name__ == "__main__":
    # df_modif = source.load_parquet_data(INPUT_FILE)
    # usages = generate_usages_list(df_modif)
    # df_result = main(df_modif, usages)

    df_buildings = source.load_building_data(RAW_DATA_DIR / "202505_export_batiments_daact.csv")
    usages = generate_usages_list(df_buildings)
    df_result = main_consumptions(df_buildings,usages)
