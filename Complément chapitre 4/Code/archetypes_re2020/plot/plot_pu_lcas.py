import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd


from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.config import FIGURES_DIR

from cmcrameri import cm

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")


to_graph = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Comparaisons/zac_tous_ind.parquet")

indicators = list(to_graph["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin



# ####### BOXENPLOTS


var_to_plot = [
    "1991",
    "1997",
    "2002",
    "2009",
    # "1991 - 1997",
    # "1991 - 2002",
    # "1991 - 2009",
    # "1997 - 2002",
    # "1997 - 2009",
    # "2002 - 2009"

]

hue_order = var_to_plot
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))


for ind in indicators :

    fig,ax = plt.subplots(figsize = (8,5))

    sns.boxenplot(
        to_graph.filter(
            pl.col("indicator") == ind,
            pl.col("variante").is_in(var_to_plot)
            ),
            x="score",
            hue = "variante",
            palette=palette,
            # showfliers= False
        )

    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    # ax.axvline(0,linestyle = ":",color="black")
    ax.set_xlabel(f"{safe_name} - {dict_indicators_units[ind]}")

    plt.savefig(f"{FIGURES_DIR}/Comparaisons_pu/all_var/boxen_solo_{safe_name}.pdf")
    plt.close()



# #### BARPLOT 


# var_to_plot = [
#     "1991",
#     "1997",
#     "2002",
#     "2009"
# ]


# tmp = to_graph.filter(pl.col("variante").is_in(var_to_plot))

# # # hue_order = to_graph["variante"].unique().to_list()
# hue_order = var_to_plot
# n= len(tmp["variante"].unique())
# palette = list(cmap(np.linspace(0.1,0.9,n)))

# short_name = dict(pl.read_excel('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/short_indicateur.xlsx').iter_rows())

# mean_per_var = pl.col("score").mean().over("indicator", "variante")
# max_mean_per_ind = mean_per_var.max().over("indicator")


# data = tmp.with_columns(
#         (pl.col("score") / max_mean_per_ind).alias("Score normalisé par la valeur moyenne maximale"),
#         (pl.col("indicator").replace_strict(short_name,default=None)).alias("Indicateurs (abréviations)") 
#     )


# order = sorted(short_name.values())

# fig,ax = plt.subplots(figsize = (8,3.5))
# sns.barplot(
#     data= data ,
#     x = "Indicateurs (abréviations)",
#     y="Score normalisé par la valeur moyenne maximale",
#     hue = "variante",
#     hue_order= hue_order,
#     palette = palette,
#     alpha = 0.8,
#     errorbar=None,
#     order=order
#     )
# ax.legend(loc = "lower center",bbox_to_anchor=(0.5,1))
# plt.tight_layout()
# plt.xticks(rotation=45,ha="right")
# # plt.show()
# plt.savefig(f"{FIGURES_DIR}/Comparaisons_pu/barplot_no_unc_all.pdf",dpi=300, bbox_inches="tight")

    