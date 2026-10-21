import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd
import textwrap

from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.config import FIGURES_DIR

from cmcrameri import cm

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

input_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Comparaisons/ponderees/n_bins_2000"


# to_graph = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Comparaisons/ponderees/n_bins_2000/zac_tous_ind_50_*.parquet")

# indicators = list(to_graph["indicator"].unique())

indicators = (
    pl.scan_parquet(f"{input_folder}/zac_tous_ind_50_*.parquet").select("indicator")
    .unique()
    .collect(streaming=True)
    )["indicator"].to_list()

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


def pooled_pmf(result, variante, indicator):
    d = result.filter((pl.col("variante") == variante) & (pl.col("indicator") == indicator))
    n_it = d["iteration"].n_unique()
    return (d.group_by("score")
              .agg((pl.col("prob").sum() / n_it).alias("prob"))
              .sort("score"))



# ####### BOXENPLOTS


var_to_plot = [
    # "1991",
    # "1997",
    # "2002",
    # "2009",
    "1991 - 1997",
    "1991 - 2002",
    "1991 - 2009",
    "1997 - 2002",
    "1997 - 2009",
    "2002 - 2009"

]


# indicator_to_plot = indicators[3]

 ####### BOXENPLOT EN TIRANT SUR PMF

def pmf_to_samples(pmf, n=20_000, seed=0):
    rng = np.random.default_rng(seed)
    p = pmf["prob"].to_numpy()
    idx = rng.choice(pmf.height, size=n, p=p / p.sum())
    return pmf["score"].to_numpy()[idx]



hue_order = var_to_plot
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))


for ind in indicators :
    d_ind = (
        pl.scan_parquet(f"{input_folder}/zac_tous_ind_50_*.parquet")
        .filter(pl.col("indicator") == ind)
        .collect()
    )
    samples = pl.concat([
        pl.DataFrame({"variante": v,
                    "score": pmf_to_samples(pooled_pmf(d_ind, v,ind))})
        for v in var_to_plot
    ]).to_pandas()


    fig,ax = plt.subplots(figsize = (7,3))

    sns.boxenplot(
        data = samples,
        x="score",
        hue = "variante",
        alpha = 0.8,
        palette=palette,
        # showfliers= False
        )

    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    ax.axvline(0,linestyle = ":",color="black")
    xlabel = "\n".join(textwrap.wrap(f"{safe_name} - {dict_indicators_units[ind]}", 70))
    ax.set_xlabel(xlabel)
    ax.legend(loc = "upper left",bbox_to_anchor = (1.01,0.99),title = None)

    # plt.savefig(f"{FIGURES_DIR}/Comparaisons_pu/ponderees/boxen_solos_{safe_name}.pdf")
    plt.savefig(f"{FIGURES_DIR}/Comparaisons_pu/ponderees/boxen_{safe_name}.pdf",bbox_inches = 'tight')
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


# #  ####### histplot EN TIRANT SUR PMF

# def pmf_to_samples(pmf, n=10_000, seed=0):
#     rng = np.random.default_rng(seed)
#     p = pmf["prob"].to_numpy()
#     idx = rng.choice(pmf.height, size=n, p=p / p.sum())
#     return pmf["score"].to_numpy()[idx]



# hue_order = var_to_plot
# palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))


# for ind in indicators :

#     samples = pl.concat([
#         pl.DataFrame({"variante": v,
#                     "score": pmf_to_samples(pooled_pmf(to_graph, v,ind))})
#         for v in var_to_plot
#     ])

#     fig,ax = plt.subplots(figsize = (7,2))

#     sns.histplot(
#         data = samples,
#         x="score",
#         hue = "variante",
#         palette=palette,
#         element= "step",
#         stat = "probability",
#         alpha = 0.8,
#         # showfliers= False
#         )

#     safe_name = ind.replace(":", "-").replace("/", "-")
#     safe_name = "-".join(safe_name.split("|")[1:])
#     ax.axvline(0,linestyle = ":",color="black")
#     ax.set_xlabel(f"{safe_name} - {dict_indicators_units[ind]}")
#     ax.legend(loc = "upper left",bbox_to_anchor = (1.01,0.99),title = None)

#     plt.savefig(f"{FIGURES_DIR}/Comparaisons_pu/ponderees/histo_diff_{safe_name}.pdf")
#     plt.close()

