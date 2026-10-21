from ipywidgets import Output
import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd

import textwrap
from cmcrameri import cm

FIGURES_DIR = "report/figures"


bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

to_graph = pl.scan_parquet(
    "data/processed/archetypes_results/multilca_archetypes_n_MC_1000_scale_*.parquet",
    cast_options=pl.ScanCastOptions(integer_cast="allow-float"),
    ).collect()

# output_folder = f"{FIGURES_DIR}/archetypes_buildings"
output_folder = f"{FIGURES_DIR}/archetypes_open_spaces"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin


indicators = list(to_graph["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]

demand_to_plot = list(to_graph["demand"].unique())


## tracés bâtiments
demand_to_plot = sorted([d for d in demand_to_plot if (
    "industrial" not in d 
    and "road" not in d
    and "vegetation" not in d
    )
    ])

# ### tracés espaces ouverts
# demand_to_plot = sorted([d for d in demand_to_plot if (
#     "industrial" not in d 
#     and ("road" in d or "vegetation" in d)
#     )
#     ])

tmp = to_graph.filter(
    pl.col("demand").is_in(demand_to_plot),
    pl.col("scale") == 0
    )

dict_legend = {
    "arch_collective_housing" : "Logement collectif",
    "arch_individual_housing" : "Maison individuelle",
    "arch_education" : "Enseignement",
    "arch_office" : "Bureau",
    "arch_roads" : "Route",
    "arch_vegetation" : "Espace végétalisé"
    }




# ####### BOXENPLOTS


# hue_order = demand_to_plot
# palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))
# legend = [dict_legend[h] for h in hue_order]

# for ind in indicators :

#    fig,ax = plt.subplots(figsize = (7,2))

#    sns.boxenplot(
#        to_graph.filter(
#            pl.col("indicator") == ind,
#            pl.col("demand").is_in(demand_to_plot)
#            ),
#            x="score",
#            hue = "demand",
#            palette=palette,
#            hue_order=hue_order,
#            alpha = 0.8,
#            # showfliers= False
#        )

#    safe_name = ind.replace(":", "-").replace("/", "-")
#    safe_name = "-".join(safe_name.split("|")[1:])
#    # ax.axvline(0,linestyle = ":",color="black")

#    # offset_text = ax.xaxis.get_offset_text().get_text()
#    # ax.xaxis.get_offset_text().set_visible(False)
#    label = f"{safe_name} \n {dict_indicators_units[ind]}"

#    ax.set_xlabel(textwrap.fill(label, width=80))

#    handles, _ = ax.get_legend_handles_labels()
#    handles = [h for h in handles if h.get_label() in hue_order]

#    ax.legend(handles, legend, loc="upper left", bbox_to_anchor=(1.01, 1))

#    plt.savefig(f"{output_folder}/boxen_solo_{safe_name}.pdf",bbox_inches = 'tight')
#    plt.close()



#### BARPLOT 

# # hue_order = to_graph["variante"].unique().to_list()
hue_order = demand_to_plot
n= len(tmp["demand"].unique())
palette = list(cmap(np.linspace(0.1,0.9,n)))
legend = [dict_legend[h] for h in hue_order]

short_name = dict(pl.read_excel('data/external/short_indicateur.xlsx').iter_rows())

mean_per_var = pl.col("score").mean().over("indicator", "demand")
max_mean_per_ind = mean_per_var.max().over("indicator")


data = tmp.with_columns(
        (pl.col("score") / max_mean_per_ind).alias("Score normalisé par la valeur moyenne maximale"),
        (pl.col("indicator").replace_strict(short_name,default=None)).alias("Indicateurs (abréviations)") 
    )


order = sorted(short_name.values())

fig,ax = plt.subplots(figsize = (7,3))
sns.barplot(
    data= data ,
    x = "Indicateurs (abréviations)",
    y="Score normalisé par la valeur moyenne maximale",
    hue = "demand",
    hue_order= hue_order,
    palette = palette,
    alpha = 0.8,
    errorbar=None,
    order=order
    )

handles, _ = ax.get_legend_handles_labels()
handles = [h for h in handles if h.get_label() in hue_order]

ax.legend(handles, legend,loc = "lower center",bbox_to_anchor=(0.5,1))
ax.set_ylabel("Score normalisé \n par la valeur moyenne maximale")
plt.tight_layout()
plt.xticks(rotation=45,ha="right")
# plt.show()
plt.savefig(f"{FIGURES_DIR}/barplot_no_unc_all.pdf",dpi=300, bbox_inches="tight")


# #### STATS

# stats = (
#     to_graph
#     .filter(pl.col("demand").is_in(demand_to_plot))
#     .group_by(["indicator", "demand"])
#     .agg(
#         pl.col("score").count().alias("n"),
#         pl.col("score").mean().alias("mean"),
#         pl.col("score").std().alias("std"),
#         pl.col("score").min().alias("min"),
#         pl.col("score").quantile(0.05).alias("p05"),
#         pl.col("score").quantile(0.25).alias("q1"),
#         pl.col("score").median().alias("median"),
#         pl.col("score").quantile(0.75).alias("q3"),
#         pl.col("score").quantile(0.95).alias("p95"),
#         pl.col("score").max().alias("max"),
#     )
#     .with_columns(
#         (pl.col("std") / pl.col("mean").abs()).alias("cv"),
#         pl.col("indicator")
#             .map_elements(lambda i: dict_indicators_units[i], return_dtype=pl.String)
#             .alias("unit"),
#         pl.col("indicator")
#             .map_elements(
#                 lambda i: "-".join(i.replace(":", "-").replace("/", "-").split("|")[1:]),
#                 return_dtype=pl.String,
#             )
#             .alias("indicator_short"),
#         pl.col("demand")
#             .replace_strict(dict_legend, default=None)
#             .alias("demand_label"),
#         pl.col("demand")
#             .replace_strict({d: i for i, d in enumerate(demand_to_plot)}, default=None)
#             .alias("_order"),
#     )
#     .sort(["indicator", "_order"])
#     .select(
#         "indicator_short", "unit", "demand_label",
#         "n", "mean", "std", "cv",
#         "min", "p05", "q1", "median", "q3", "p95", "max",
#     )
# )

# # Affichage complet
# with pl.Config(tbl_rows=-1, tbl_cols=-1, tbl_width_chars=250, fmt_float="full"):
#     print(stats)

# # Export
# stats.write_csv(f"/mnt/ef432d92-e906-4d66-b70a-bdda12ad48be/2609_archetypes_metabo/report/tables/stats_solo.csv")





