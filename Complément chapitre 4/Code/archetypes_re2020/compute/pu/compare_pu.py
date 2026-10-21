import polars as pl
import numpy as np

from itertools import combinations
import os
from tqdm import tqdm

import bw2data as bd
import bw2io as bi

from archetypes_re2020.config import PROCESSED_DATA_DIR
from archetypes_re2020.data.remove_extreme_outliers import outliers


bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

PER = 100

Hbs_folder = f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Hb/260827-Hb_per/{PER}"
df_open_scores = pl.read_parquet(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-25-23h5_MC_runs/scores_{PER}.parquet")

# Hbs_folder = f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Hb/260810-Hb"
# df_open_scores = pl.read_parquet(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-25-23h5_MC_runs/scores.parquet")


arch_db = bd.Database("2026-8-13-16h52_archetypes_RE2020_BB")
dict_w = {}

for a in tqdm(arch_db) :
    phi = list(a.production())[0]["amount"]
    tmp = {e["input"][1] : e["amount"]/phi for e in tqdm(a.technosphere(),leave = False)}
    dict_w = dict_w | tmp


programmes = {
    "1991" : {
    "individual_housing" : 0,
    "collective_housing" : 520000,
    "office_building" : 900000,
    # "industrial_building" : 165000,
    "education_building" : 582000,
    "roads" : 100000,
    "vegetation" : 53000,
    },
    "1997" : {
    "individual_housing" : 0,
    "collective_housing" : 520000,
    "office_building" : 900000,
    # "industrial_building" : 150000,
    "education_building" : 684000,
    "roads" : 100000,
    "vegetation" : 80600,
    },
    "2002" : {
    "individual_housing" : 0,
    "collective_housing" : 430000,
    "office_building" : 700000,
    # "industrial_building" : 150000,
    "education_building" : 920000,
    "roads" : 100000,
    "vegetation" : 100000,
    },
    "2009" : {
    "individual_housing" : 0,
    "collective_housing" : 585000,
    "office_building" : 745000,
    # "industrial_building" : 150000,
    "education_building" : 920000,
    "roads" : 100000,
    "vegetation" : 100000,
    }
    }

map_arch = {
    "individual_housing" : "Maison individuelle ou accolée",
    "collective_housing" : "Logement collectif",
    "office_building" : "Bureau",
    # "industrial_building" : "Bureau",
    # "education_building" : 'Enseignement secondaire (partie jour)',
    "education_building" : "Bureau",
    "roads" : "roads_m2_per",
    "vegetation" : "vegetation_m2_per"}




def build_Hb_filtered(parquet_file,dict_w):
    tmp = pl.read_parquet(parquet_file)
    tmp = tmp.with_columns(
        poids = pl.col("batiment").replace_strict(dict_w, default = 0.,return_dtype = pl.Float64)
    ).drop_nulls("usage")

    # valeurs aberrantes par usage
    parts = tmp.partition_by('usage')
    tmp = pl.concat([outliers(part, "score") for part in parts])
    return tmp.filter(pl.col("score_extreme_outliers")==False)

def eval_one_var(Hb_filtered,var_dict) : 

    # On projette le projet urbain sur f tilde
    f_tilde = {k: 0 for k in Hb_filtered["usage"].unique()}          

    for k, v in var_dict.items():
        key = map_arch[k]
        if key not in f_tilde:
            # print(f"{k} non considéré")
            continue
        else:
            f_tilde[key] += v

    # On enlève les poids nuls, on pondère les non nuls
    tmp = Hb_filtered.filter(pl.col("usage").is_in([k for k, v in f_tilde.items() if v != 0]))

    expr = pl.col("score")
    for k, v in f_tilde.items():
        if v != 0:
            expr = pl.when(pl.col("usage") == k).then(pl.col("score") * v).otherwise(expr)
    
    tmp = tmp.with_columns(expr.alias("score"))

    return tmp


def get_result(updated_Hp) :
    pl.Config.set_streaming_chunk_size(10_000)

    result = (
        updated_Hp.lazy()
        .group_by("iteration", "indicator")
        .agg(pl.col("score").sum())
        .collect(engine="streaming")
    )

    return result

def add_open_spaces_results(result,open_scores,var_dict) :
    # On projette le projet urbain sur f tilde
    ind = result["indicator"].unique()[0]
    tmp = open_scores.filter(pl.col("indicator")==ind)
    f_tilde = {k: 0 for k in tmp["demand"].unique()}          

    for k, v in var_dict.items():
        key = map_arch[k]
        if key not in f_tilde:
            continue
        else:
            f_tilde[key] += v
    
    tmp = tmp.filter(pl.col("demand").is_in([k for k, v in f_tilde.items() if v != 0]))

    expr = pl.col("score")
    for k, v in f_tilde.items():
        if v != 0:
            expr = pl.when(pl.col("demand") == k).then(pl.col("score") * v).otherwise(expr)

    tmp = tmp.with_columns(expr.alias("score")).group_by("iteration").agg(pl.col("score").sum())
    res = result.join(
        tmp, on="iteration", how="left", suffix="_right"
        ).with_columns(
            (pl.col("score") + pl.col("score_right").fill_null(0)
            ).alias("score")
            ).drop("score_right")

    return res





#construction des dictionnaires de projets à évaluer
to_assess_dict = dict(programmes)

for prog1,prog2 in combinations(programmes.keys(),r = 2) :
    tmp = {k : programmes[prog1][k] - programmes[prog2][k] for k in programmes[prog1].keys()}
    to_assess_dict[f"{prog1} - {prog2}"] = tmp

# On fait les Hb un par un sinon mémoire crash
results_list = []
for file in tqdm(os.listdir(Hbs_folder),desc = 'Parcours des indicateurs'):
    full = os.path.join(Hbs_folder, file)
    if os.path.isfile(full):
        Hb_filtered = build_Hb_filtered(full,dict_w)
        frames = []
        for var_key,var_dict in (pbar := tqdm(
            to_assess_dict.items(), leave = False
            )):
            pbar.set_description(f"Variante {var_key}")
            tmp = eval_one_var(Hb_filtered,var_dict)
            res = get_result(tmp)
            res = add_open_spaces_results(res,df_open_scores,var_dict)
            res = res.with_columns(
                pl.lit(var_key).alias("variante")
                )
            frames.append(res)
        
        results_list.append(pl.concat(frames, how="vertical"))

# result = pl.concat(
#     results_list, how="vertical"
#     ).write_parquet(f"{PROCESSED_DATA_DIR}/Comparaisons/zac_tous_ind.parquet")

result = pl.concat(
    results_list, how="vertical"
    ).write_parquet(f"{PROCESSED_DATA_DIR}/Comparaisons/zac_tous_ind_{PER}.parquet")





