import polars as pl
import numpy as np
import bw2data as bd
import bw2io as bi
import bw2calc as bc

from tqdm import tqdm
from datetime import datetime

from bw25_utils import K,K2,K3,K4
from itertools import combinations

from remove_extreme_outliers import outliers
import seaborn as sns
import matplotlib.pyplot as plt

from cmcrameri import cm


FIGURE_DIR = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/figures"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
    "font.size": 10
})
cmap = cm.berlin



bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")



ipps = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/processed/Lcas/2026-8-20-14h15-maquettes_impacts.parquet")

indicators_list = [c for c in ipps.columns if "ecoinvent" in str(c)]

dict_indicators_units = {}
for ind in indicators_list :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]

to_graph = ipps.drop_nulls().group_by("variante","year","index").agg(
    [pl.col(ind).sum() for ind in indicators_list]
    )


results = []
for variante in to_graph["variante"].unique():
    subset = to_graph.filter(pl.col("variante") == variante)
    for ind in indicators_list:
        subset = outliers(subset, ind)
    results.append(subset)

to_graph_all = pl.concat(results)


var_to_plot = [
    # "Castro",
    # "Huet",
    # "Portzamparc",

    # "Castro-bois",
    # "Huet-bois",
    # "Portzamparc-bois",

    # "Castro-nowindow",
    # "Huet-nowindow",
    # "Portzamparc-nowindow",

    # 'Castro - Huet',
    # 'Castro - Portzamparc',
    # 'Huet - Portzamparc',

    # 'Castro - Castro-nowindow',
    # 'Huet - Huet-nowindow',
    # 'Portzamparc - Portzamparc-nowindow'

    # 'Castro - Castro-bois',
    # 'Huet - Huet-bois',
    # 'Portzamparc - Portzamparc-bois'
    
    'Castro - Huet',
    'Castro-nowindow - Huet-nowindow',
    "Castro - Huet-nowindow",
    "Castro-nowindow - Huet",
    'Castro - Portzamparc',
    'Castro-nowindow - Portzamparc-nowindow',
    'Castro - Portzamparc-nowindow',
    'Castro-nowindow - Portzamparc',
    'Huet - Portzamparc',
    'Huet-nowindow - Portzamparc-nowindow',
    'Huet - Portzamparc-nowindow',
    'Huet-nowindow - Portzamparc',

    # 'Castro - Huet',
    # 'Castro-bois - Huet-bois',
    # 'Castro - Portzamparc',
    # 'Castro-bois - Portzamparc-bois',
    # 'Huet - Portzamparc',
    # 'Huet-bois - Portzamparc-bois',
    ]


# import time
res = {ind : {"K" : {},"K2" : {},"K3" : {},"K4" :{}} for ind in indicators_list}
for ind in tqdm(indicators_list,desc = "Indicateurs") : 
    if "(ultimate reserves)" in str(ind) :
        continue

    tmp = to_graph_all.select(
        ["variante","index",ind,f"{ind}_mild_outliers",f"{ind}_extreme_outliers"]
        ).filter(pl.col(f"{ind}_extreme_outliers")==False)

    df_by_variant = {
        v: tmp.filter(pl.col("variante") == v)
        for v in var_to_plot
    }

    for combi in tqdm(combinations(var_to_plot,r=2),desc = "Combinaisons de variantes",leave=False):
        a, b = combi
        df = df_by_variant[a].join(df_by_variant[b], on="index", how="inner")
        a_mc = df[ind].to_numpy()
        b_mc = df[f"{ind}_right"].to_numpy()

        key = str(combi)
        res[ind]["K"][key] = K(a_mc,b_mc)
        res[ind]["K2"][key] = K2(a_mc,b_mc)
        res[ind]["K3"][key] = K3(a_mc,b_mc)
        res[ind]["K4"][key] = K4(a_mc,b_mc,threshold=1.05)
    
    # import time

    # for combi in tqdm(combinations(var_to_plot, r=2)):
    #     a, b = combi
    #     t0 = time.perf_counter()
    #     df = df_by_variant[a].join(df_by_variant[b], on="index", how="inner")
    #     t1 = time.perf_counter()

    #     a_mc = df[ind].to_list()
    #     b_mc = df[f"{ind}_right"].to_list()
    #     t2 = time.perf_counter()

    #     res[ind]["K2"][str(combi)] = K2(a_mc, b_mc)
    #     t3 = time.perf_counter()
    #     res[ind]["K3"][str(combi)] = K3(a_mc, b_mc)
    #     t4 = time.perf_counter()
    #     res[ind]["K4"][str(combi)] = K4(a_mc, b_mc, threshold=1.05)
    #     t5 = time.perf_counter()

    #     print(f"join={t1-t0:.3f} tolist={t2-t1:.3f} K2={t3-t2:.3f} K3={t4-t3:.3f} K4={t5-t4:.3f}")

import json

today = datetime.today()
horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

output_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/processed/discern"

with open(f"{output_folder}/{horodatage}_discern_indexes.json", 'w') as f:
    json.dump(res, f)
# for combi in combinations(var_to_plot, r=2):
#     a = combi[0]
#     b = combi[1]
#     df_a = tmp.filter(pl.col("variante") == a, pl.col(f"{ind}_extreme_outliers") == False)
#     df_b = tmp.filter(pl.col("variante") == b, pl.col(f"{ind}_extreme_outliers") == False)
    
#     # Inner join on "index"
#     df = df_a.join(df_b, on="index", how="inner")
    
#     a_mc = df[ind].to_list()
#     b_mc = df[f"{ind}_right"].to_list()
#     print
#     if len(a_mc)!= len(b_mc) :
#         print(len(a_mc),len(b_mc))


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

output_folder_table = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/tables"
df_wide.write_csv(f"{output_folder_table}/{horodatage}_discern_table.csv")
print(df_wide.head(10))

