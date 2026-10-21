import polars as pl
import numpy as np

from itertools import combinations
import os
from tqdm import tqdm

import bw2data as bd
import bw2io as bi

import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.transforms import blended_transform_factory
# pour voir placer les annotation comme on veut



import textwrap
from cmcrameri import cm

# from archetypes_re2020.config import PROCESSED_DATA_DIR
# from archetypes_re2020.data.remove_extreme_outliers import outliers

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin

FIGURES_DIR = "report/figures"

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")


df_scores = pl.read_parquet("/mnt/ef432d92-e906-4d66-b70a-bdda12ad48be/2609_archetypes_metabo/data/processed/pu_results/no change/multilca_programs_n_MC_1000_scale_0.parquet")


to_assess = list(df_scores["demand"].unique())

# combi des programmes deux à deux
dfs_combi = []
for prog1,prog2 in combinations(to_assess,r = 2) :
    diff_df = (
        df_scores.filter(pl.col("demand").is_in([prog1, prog2]))
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

df_scores = pl.concat([df_scores,*dfs_combi],how="diagonal")

def short_combi_name(combi_name) :
    if "-" in combi_name :
        tmp = combi_name.split(" - ")
        tmp = [s.split("_")[1] for s in tmp]
        return " - ".join(tmp)
    else : 
        return combi_name.split("_")[1] 

# df_scores = df_scores.with_columns(
#     pl.col("demand").map_elements(
#         lambda x : short_combi_name(x),
#         return_dtype=pl.String
#     )
# )

output_folder = f"{FIGURES_DIR}/comparaisons_pu"



indicators = list(df_scores["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


demand_to_plot = sorted(list(df_scores["demand"].unique()))

demand_to_plot = sorted([d for d in demand_to_plot if " - " in str(d)])


tmp = df_scores.filter(
    pl.col("demand").is_in(demand_to_plot),
    pl.col("scale") == 0
    )

# ####### BOXENPLOTS

hue_order = demand_to_plot
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))

for ind in indicators :

    fig,ax = plt.subplots(figsize = (7,2))

    sns.boxenplot(
        tmp.filter(
            pl.col("indicator") == ind,
            ),
            x="score",
            hue = "demand",
            palette=palette,
            hue_order=hue_order,
            alpha = 0.8,
            # showfliers= False
        )

    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    ax.axvline(0,linestyle = ":",color="black")



    # x in data units, y in axes fraction
    trans = blended_transform_factory(ax.transData, ax.transAxes)
    xmin, xmax = ax.get_xlim()
    len_arrow = (xmax - xmin) /3
    dx = 0.02 * (xmax - xmin)
    ### FLECHE POSITIFS
    ax.annotate(
        "",
        xy=(min(dx+len_arrow,xmax), 1.03),
        xytext=(dx, 1.03), xycoords=trans,
        arrowprops=dict(arrowstyle="-|>", lw=1.5, color="black"),
    )
    ax.text((dx+len_arrow)/2, 1.04, "Impact(A) $>$ Impact(B)",
            transform=trans, ha="center", va="bottom", fontsize=10)

    ### FLECHE NEGATIFS
    ax.annotate(
        "",
        xy=(max(-dx-len_arrow,xmin), 1.03),
        xytext=(-dx, 1.03), xycoords=trans,
        arrowprops=dict(arrowstyle="-|>", lw=1.5, color="black"),
    )
    ax.text(-(dx+len_arrow)/2, 1.04, "Impact(A) $<$ Impact(B)",
            transform=trans, ha="center", va="bottom", fontsize=10)

    label = f"{safe_name} \n {dict_indicators_units[ind]}"

    ax.set_xlabel(textwrap.fill(label, width=80))

    ## On change les noms pour plus de clarté :
    handles, labels = ax.get_legend_handles_labels()
    labels = [short_combi_name(l) for l in labels]

    ax.legend(handles,labels,loc="upper left", bbox_to_anchor=(1.01, 1))
    #### ANNOTATION AU DESSUS LEGENDE
    ax.text(1.12, 1.02, r"A \hspace{0.6cm} B",
        transform=ax.transAxes, ha="left", va="bottom", fontsize=10)

    plt.savefig(f"{output_folder}/boxen_comparaisons_{safe_name}.pdf",bbox_inches = 'tight')
    plt.close()








