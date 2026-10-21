
from ipywidgets import Output
import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd
from tqdm import tqdm 
import textwrap
from cmcrameri import cm
import glob
from itertools import combinations
import json
from datetime import datetime
from utils.bw25_utils import K,K2,K3,K4



output_folder = "data/processed/pu_results/scale_sensi"
bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

to_graph = pl.scan_parquet(
    "data/processed/pu_results/multilca_programs_n_MC_500_scale_*.parquet",
    cast_options=pl.ScanCastOptions(integer_cast="allow-float"),
    ).collect()


# combi des programmes deux à deux
to_assess = list(to_graph["demand"].unique())
dfs_combi = []
for prog1,prog2 in combinations(to_assess,r = 2) :
    diff_df = (
        to_graph.filter(pl.col("demand").is_in([prog1, prog2]))
        .group_by(["iteration", "indicator","scale"])
        .agg(
            (
                pl.col("score").filter(pl.col("demand") == prog1).first()
                - pl.col("score").filter(pl.col("demand") == prog2).first()
            ).alias("score")
        )
        .with_columns(demand=pl.lit(f"{prog1} - {prog2}"))
    )
    dfs_combi.append(diff_df) 

df_scores = pl.concat([to_graph,*dfs_combi],how="diagonal")

df_scores = df_scores.with_columns(
    pl.col("scale").truncate(1)
)

indicators = list(df_scores["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


scales = sorted(list(df_scores["scale"].unique()))

demand_to_plot = sorted(list(df_scores["demand"].unique()))

demand_to_plot = [d for d in demand_to_plot if " - " not in d]


res = {s : {ind : {"K" : {},"K2" : {},"K3" : {},"K4" :{}} for ind in indicators} for s in scales}

for s in scales : 
    
    for ind in tqdm(indicators,desc = "Indicateurs") : 

        tmp = df_scores.filter(pl.col("indicator")==ind,pl.col("scale")==s)

        df_by_variant = {
            v: tmp.filter(pl.col("demand") == v)
            for v in demand_to_plot
        }

        for combi in tqdm(combinations(demand_to_plot,r=2),desc = "Combinaisons de variantes",leave=False):
            a, b = combi
            a_mc = df_by_variant[a]["score"].to_numpy()
            b_mc = df_by_variant[b]["score"].to_numpy()

            key = str(combi)
            res[s][ind]["K"][key] = K(a_mc,b_mc)
            res[s][ind]["K2"][key] = K2(a_mc,b_mc)
            res[s][ind]["K3"][key] = K3(a_mc,b_mc)
            res[s][ind]["K4"][key] = K4(a_mc,b_mc,threshold=1.05)
        

today = datetime.today()
horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

with open(f"{output_folder}/{horodatage}_discern_indexes_sensi_scale.json", 'w') as f:
    json.dump(res, f)


