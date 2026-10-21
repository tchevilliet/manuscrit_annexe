import polars as pl
import numpy as np

from itertools import combinations,permutations
import os
from tqdm import tqdm

import bw2data as bd
import bw2io as bi

from archetypes_re2020.config import PROCESSED_DATA_DIR
from archetypes_re2020.data.remove_extreme_outliers import outliers

from archetypes_re2020.compute.pu.compare_pu_weighted import *

N_BINS = 2000

OUTPUT_FILE = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Archetypes/distrib_arch"

archetypes = {
    "Maison individuelle ou accolée" : {
    "individual_housing" : 1,
    "collective_housing" : 0,
    "office_building" : 0,
    # "industrial_building" : 0,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    },
    "Logement collectif" : {
    "individual_housing" : 0,
    "collective_housing" : 1,
    "office_building" : 0,
    # "industrial_building" : 0,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    },
    "Bureau" : {
    "individual_housing" : 0,
    "collective_housing" : 0,
    "office_building" : 1,
    # "industrial_building" : 0,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    }
    }

to_assess_dict = archetypes


def main():    
    for file in tqdm(os.listdir(Hbs_folder), desc="Parcours des indicateurs"):
        results_list = []
        full = os.path.join(Hbs_folder, file)
        if not os.path.isfile(full):
            continue
    
        Hb = build_Hb_filtered(full, dict_w)
        indicator = Hb["indicator"].unique()[0]
    
        groups = prepare_groups(Hb)
        # au lieu de min max, on regarde les quantiles extêmes pour que la résolution
        # serve à quelque chose et ne sois pas diluer sur un trop grand spectre
        ranges = Hb.group_by("usage").agg(
            mn=pl.col("score").quantile(0.001), mx=pl.col("score").quantile(0.999)
        )
        usage_ranges = {r["usage"]: (r["mn"], r["mx"]) for r in ranges.iter_rows(named=True)}
        usages = set(usage_ranges)
    
        for var_key, var_dict in (
            pbar := tqdm(to_assess_dict.items(), leave=False)
        ):
            pbar.set_description(f"Variante {var_key}")
            # run_variant(Hb, var_key, indicator, df_open_scores)
            f_tilde = f_tilde_from_var(var_dict, usages)
            open_it = open_by_iter(df_open_scores, var_dict, indicator)
            results_list.append(
                iteration_distributions(
                    groups, usage_ranges, f_tilde, open_it, var_key, indicator,n_bins= N_BINS
                )
            )
        ind_name = "_".join(file.split("_")[1:-1])
        result = pl.concat(results_list, how="vertical")
        result.write_parquet(f"{OUTPUT_FILE}_{ind_name}.parquet")


if __name__ == "__main__":
    main()