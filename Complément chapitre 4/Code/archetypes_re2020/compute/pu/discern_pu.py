import polars as pl
import numpy as np

from itertools import combinations
import os
from tqdm import tqdm
from datetime import datetime
import bw2data as bd
import bw2io as bi

import json

from archetypes_re2020.config import PROCESSED_DATA_DIR, TABLES_DIR
from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.utils.bw25_utils import K,K2,K3,K4

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")


to_graph = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Comparaisons/zac_tous_ind.parquet")

indicators = list(to_graph["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


var_to_plot = [
    "1991",
    "1997",
    "2002",
    "2009"
]



res = {ind : {"K" : {},"K2" : {},"K3" : {},"K4" :{}} for ind in indicators}
for ind in tqdm(indicators,desc = "Indicateurs") : 
    # if "(ultimate reserves)" in str(ind) :
    #     continue

    tmp = to_graph.filter(pl.col("indicator")==ind)

    df_by_variant = {
        v: tmp.filter(pl.col("variante") == v)
        for v in var_to_plot
    }

    for combi in tqdm(combinations(var_to_plot,r=2),desc = "Combinaisons de variantes",leave=False):
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

output_folder = f"{PROCESSED_DATA_DIR}/Discern"

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

df_wide.write_csv(f"{TABLES_DIR}/{horodatage}_discern_table.csv")
print(df_wide.head(10))