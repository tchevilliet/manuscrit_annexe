import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd


from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.config import FIGURES_DIR

from cmcrameri import cm

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

to_graph = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Archetypes/distrib_arch_*.parquet")

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


def pooled_pmf(result, variante, indicator):
    d = result.filter((pl.col("variante") == variante) & (pl.col("indicator") == indicator))
    n_it = d["iteration"].n_unique()
    return (d.group_by("score")
              .agg((pl.col("prob").sum() / n_it).alias("prob"))
              .sort("score"))




def pmf_to_samples(pmf, n=200_000, seed=0):
    rng = np.random.default_rng(seed)
    p = pmf["prob"].to_numpy()
    idx = rng.choice(pmf.height, size=n, p=p / p.sum())
    return pmf["score"].to_numpy()[idx]


var_to_plot =  to_graph["variante"].unique()
hue_order = var_to_plot
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))

# #  ####### BOXENPLOT EN TIRANT SUR PMF
# for ind in indicators :

#     samples = pl.concat([
#         pl.DataFrame({"variante": v,
#                     "score": pmf_to_samples(pooled_pmf(to_graph, v,ind))})
#         for v in var_to_plot
#     ]).to_pandas()


#     fig,ax = plt.subplots(figsize = (7,4))

#     sns.boxenplot(
#         data = samples,
#         x="score",
#         hue = "variante",
#         palette=palette,
#         # showfliers= False
#         alpha = 0.8
#         )

#     safe_name = ind.replace(":", "-").replace("/", "-")
#     safe_name = "-".join(safe_name.split("|")[1:])
#     # ax.axvline(0,linestyle = ":",color="black")
#     ax.set_xlabel(f"{safe_name} - {dict_indicators_units[ind]}")
#     ax.legend(loc = "upper left",bbox_to_anchor = (1.01,0.99))

#     plt.savefig(f"{FIGURES_DIR}/Archetypes_ponderees/boxen_arch_{safe_name}.pdf",bbox_inches = 'tight')
#     plt.close()



##### BARPLOT

tmp = to_graph.filter(pl.col("variante").is_in(var_to_plot))


short_name = dict(pl.read_excel('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/short_indicateur.xlsx').iter_rows())

mean_per_var = pl.col("score").mean().over("indicator", "variante")
max_mean_per_ind = mean_per_var.max().over("indicator")


data = tmp.with_columns(
        (pl.col("score") / max_mean_per_ind).alias("Score normalisé par la valeur moyenne maximale"),
        (pl.col("indicator").replace_strict(short_name,default=None)).alias("Indicateurs (abréviations)") 
    )


order = sorted(short_name.values())

fig,ax = plt.subplots(figsize = (8,3.5))
sns.barplot(
    data= data ,
    x = "Indicateurs (abréviations)",
    y="Score normalisé par la valeur moyenne maximale",
    hue = "variante",
    hue_order= hue_order,
    palette = palette,
    alpha = 0.8,
    # errorbar=None,
    order=order
    )
ax.legend(loc = "upper left",bbox_to_anchor=(1.01,0.99))
plt.tight_layout()
plt.xticks(rotation=45,ha="right")
# plt.show()
# plt.savefig(f"{FIGURES_DIR}/Archetypes_ponderees/barplot_no_unc_all.pdf",dpi=300, bbox_inches="tight")
plt.savefig(f"{FIGURES_DIR}/Archetypes_ponderees/barplot_all.pdf",dpi=300, bbox_inches="tight")

    