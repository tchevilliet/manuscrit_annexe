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

from utils.bw25_utils import K,K2,K3,K4

FIGURES_DIR = "report/figures"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin

output_folder = f"{FIGURES_DIR}/comparaisons_pu/scale sensi"

short_name = dict(pl.read_excel('data/external/short_indicateur.xlsx').iter_rows())

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


# # output_folder = f"{FIGURES_DIR}/archetypes_open_spaces"



indicators = list(df_scores["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


demand_to_plot = sorted(list(df_scores["demand"].unique()))

demand_to_plot = [d for d in demand_to_plot if " - " in d]



scales = sorted(list(df_scores["scale"].unique()))

# ####### BOXENPLOTS

hue_order = demand_to_plot
palette = [list(cmap(np.linspace(0.1,0.9,len(hue_order))))[0]]


for ind in tqdm(indicators,desc = "indicateurs") :

    fig,ax = plt.subplots(figsize = (7,2))

    sns.boxenplot(
        df_scores.filter(
            pl.col("indicator") == ind,
            pl.col("demand") == "programme_1991 - programme_2002"
            # pl.col("demand") == "programme_2002"
            ),
            x = 'scale',
            y="score",
            # hue = "demand",
            palette=palette,
            # hue_order=hue_order,
            alpha = 0.8,
            # showfliers= False
        )

    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    ax.axhline(0,linestyle = ":",color="black")

    label = f"{safe_name} \n {dict_indicators_units[ind]}"

    ax.set_ylabel(textwrap.fill(label, width=30))
    ax.set_xlabel(r"Écart-type relatif de la distribution des coefficients de la matrice $\mathbf{T}$")

    # ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))

    plt.savefig(f"{output_folder}/pu_scale_sensi_prog1991-prog2002_{safe_name}.pdf",bbox_inches = 'tight')
    # plt.savefig(f"{output_folder}/pu_scale_sensi_prog2002_{safe_name}.pdf",bbox_inches = 'tight')
    plt.close()


# #### LINEPLOTS K et STD



# json_path = "data/processed/pu_results/scale_sensi/2026-9-17-7h41_discern_indexes_sensi_scale.json"
# with open(json_path, 'r') as f:
#     res = json.load(f)

# rows = [
#     {
#         "scale": s,
#         "indicator": ind,
#         "k_level": k_lev,
#         "combi": combi_key,
#         "value_key" : k,
#         "value": v,
#     }
#     for s, ind_dict in res.items()
#     for ind, k_dict in ind_dict.items()
#     for k_lev, combi_dict in k_dict.items()
#     for combi_key, arr in combi_dict.items()
#     for k,v in arr.items()
# ]

# df = pl.from_dicts(rows)




# combi_to_plot = ["('programme_1991', 'programme_2002')"]
# index_to_plot = ["K","K4"]
# indicator_to_plot = [
#     'ecoinvent-3.11 | EF v3.1 | eutrophication: freshwater | fraction of nutrients reaching freshwater end compartment (P)',
#     'ecoinvent-3.11 | EF v3.1 | climate change | global warming potential (GWP100)',
#     'ecoinvent-3.11 | EF v3.1 | ecotoxicity: freshwater | comparative toxic unit for ecosystems (CTUe)'
# ]

# palette = list(cmap(np.linspace(0.1,0.9,len(indicator_to_plot))))
# for combi in combi_to_plot : 
#     for k_level in index_to_plot :
#         tmp = df.filter(
#             pl.col("k_level") == k_level,
#             pl.col("indicator").is_in(indicator_to_plot),
#             pl.col("combi") == combi,
#             pl.col("value_key") == f"{k_level}_A"
#             )
#         fig,ax = plt.subplots(figsize = (7,2))
#         sns.lineplot(
#             data = tmp,
#             x= "scale",
#             y="value",
#             hue = "indicator",
#             palette=palette,
#             alpha = 0.8)
        
#         ax.set_ylabel(textwrap.fill(f"{k_level}_A", width=45))
#         ax.set_xlabel(r"Écart-type relatif de la distribution des coefficients de la matrice $\mathbf{T}$")
#         handles, labels = ax.get_legend_handles_labels()
#         labels = [short_name[l] for l in labels]

#         ax.legend(handles, labels,loc="upper left", bbox_to_anchor=(1.01, 1))

#         plt.savefig(f"{output_folder}/pu_scale_sensi_prog1991-prog2002_{k_level}.pdf",bbox_inches = 'tight')
#         plt.close()

