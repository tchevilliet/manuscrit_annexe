import polars as pl
import numpy as np
import json
from itertools import combinations
import os
from tqdm import tqdm

import bw2data as bd
import bw2io as bi
from datetime import datetime 
import seaborn as sns
import matplotlib.pyplot as plt

import textwrap
from cmcrameri import cm

from utils.bw25_utils import K,K2,K3,K4

# from archetypes_re2020.config import PROCESSED_DATA_DIR
# from archetypes_re2020.data.remove_extreme_outliers import outliers

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin



bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")


df_scores = pl.read_parquet("data/processed/pu_results/multilca_programs_n_MC_1000_scale_0.parquet")

output_folder = "data/processed/pu_results/discern"

output_folder_table = "report/tables"

indicators = list(df_scores["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


demand_to_plot = list(df_scores["demand"].unique())

res = {ind : {"K" : {},"K2" : {},"K3" : {},"K4" :{}} for ind in indicators}
for ind in tqdm(indicators,desc = "Indicateurs") : 

    tmp = df_scores.filter(pl.col("indicator")==ind)

    df_by_variant = {
        v: tmp.filter(pl.col("demand") == v)
        for v in demand_to_plot
    }

    for combi in tqdm(combinations(demand_to_plot,r=2),desc = "Combinaisons de variantes",leave=False):
        a, b = combi
        a_mc = df_by_variant[a]["score"].to_numpy()
        b_mc = df_by_variant[b]["score"].to_numpy()

        key = str(combi)
        res[ind]["K"][key] = K(a_mc,b_mc)
        res[ind]["K2"][key] = K2(a_mc,b_mc)
        res[ind]["K3"][key] = K3(a_mc,b_mc)
        res[ind]["K4"][key] = K4(a_mc,b_mc,threshold=1.05)
    

today = datetime.today()
horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

with open(f"{output_folder}/{horodatage}_discern_indexes.json", 'w') as f:
    json.dump(res, f)


import ast

rows = {}

for indicator, criteria_dict in res.items():
    for criterion, pairs_dict in criteria_dict.items():
        for pair_key, values_dict in pairs_dict.items():
            item_a, item_b = ast.literal_eval(pair_key)
            key = (indicator, item_a, item_b)

            row = rows.setdefault(key, {
                "indicator": indicator,
                "variante_A": item_a,
                "variante_B": item_b,
            })
            for val_name, val in values_dict.items():
                row[f"{criterion}_{val_name}"] = val

df_wide = pl.DataFrame(list(rows.values()))

df_wide.write_csv(f"{output_folder_table}/{horodatage}_discern_table.csv")
print(df_wide.head(10))