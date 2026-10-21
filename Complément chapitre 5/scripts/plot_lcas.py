import polars as pl
import numpy as np
import bw2data as bd
import bw2io as bi
import bw2calc as bc


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

    # 'Castro - Huet',
    # 'Castro - Portzamparc',
    # 'Huet - Portzamparc',

    # 'Castro - Castro-nowindow',
    # 'Huet - Huet-nowindow',
    # 'Portzamparc - Portzamparc-nowindow'

    # 'Castro - Castro-bois',
    # 'Huet - Huet-bois',
    # 'Portzamparc - Portzamparc-bois'
    

    ### WINDOWS
    'Castro - Huet',
    'Castro-nowindow - Huet-nowindow',
    'Castro - Huet-nowindow',
    'Castro-nowindow - Huet',

    'Castro - Portzamparc',
    'Castro-nowindow - Portzamparc-nowindow',
    'Castro - Portzamparc-nowindow',
    'Castro-nowindow - Portzamparc',

    'Huet - Portzamparc',
    'Huet-nowindow - Portzamparc-nowindow',
    'Huet - Portzamparc-nowindow',
    'Huet-nowindow - Portzamparc',


    #### BOIS
    # 'Castro - Huet',
    # 'Castro-bois - Huet-bois',
    # 'Castro - Huet-bois',
    # 'Castro-bois - Huet',

    # 'Castro - Portzamparc',
    # 'Castro-bois - Portzamparc-bois',
    # 'Castro-bois - Portzamparc',
    # 'Castro - Portzamparc-bois',

    # 'Huet - Portzamparc',
    # 'Huet-bois - Portzamparc-bois',
    # 'Huet-bois - Portzamparc',
    # 'Huet - Portzamparc-bois',
    ]


to_graph = to_graph_all.filter(pl.col("variante").is_in(var_to_plot))

# hue_order = to_graph["variante"].unique().to_list()
hue_order = var_to_plot
n= len(to_graph["variante"].unique())
palette = list(cmap(np.linspace(0.1,0.9,n)))

# palette = list(cmap(np.linspace(0.1,0.9,18)))
# palette = [[palette[2+i*6],palette[4+i*6]] for i in range(3)]

# palette = [x for xs in palette for x in xs]

ind = indicators_list[2]



for ind in indicators_list : 
    if "(ultimate reserves)" in str(ind) :
        continue
    fig,ax = plt.subplots(figsize = (8.5,3.5))
    sns.boxenplot(
        data= to_graph.filter(
            pl.col(f"{ind}_extreme_outliers")==False
            ),
        x = ind,
        hue = "variante",
        hue_order= hue_order,
        palette = palette,
        alpha = 0.6,
        )
    ax.set_xlabel(f"{"-".join(ind.split("|")[1:])} - {dict_indicators_units[ind]}")
    ax.legend(loc = "center left",bbox_to_anchor = (1,0.5))
    ax.axvline(x=0,color = "black",linestyle = ":")
    plt.tight_layout()

    # plt.show()
    # plt.savefig(f"{FIGURE_DIR}/boxenplot_scores/{"-".join(ind.replace(":","-").split("|")[1:])}.pdf")
    # plt.savefig(f"{FIGURE_DIR}/Sensibilite/bois/boxen_sensibilite_bois_{"-".join(ind.replace(":","-").split("|")[1:])}.pdf")
    plt.savefig(f"{FIGURE_DIR}/Sensibilite/windows/boxen_sensibilite_window_{"-".join(ind.split("|")[1:])}.pdf")
    # plt.savefig(f"{FIGURE_DIR}/sensibilite_individuelle_windows_{"-".join(ind.split("|")[1:])}.pdf",dpi = 300)
# indicators_list  = [
#     ('ecoinvent-3.11','EF v3.1','climate change','global warming potential (GWP100)'),
#     ('ecoinvent-3.11','EF v3.1','eutrophication: freshwater','fraction of nutrients reaching freshwater end compartment (P)'),
#     ('ecoinvent-3.11','EF v3.1','water use','user deprivation potential (deprivation-weighted water consumption)')
#     ]


# for ind in tqdm(indicators_list) :
#     for k,v in tqdm(ipps.items(), leave=False) :
#         ipps[k] = v.drop_nulls(subset=["process_id", "demand_amount"]).with_columns(
#             pl.struct(["process_id", "demand_amount"])
#             .map_elements(
#                 lambda s: make_lca(s["process_id"], s["demand_amount"],ind),
#                 return_dtype=pl.List(pl.Float64)
#             )
#             .alias(str(ind[1:])),
#             )


# #### BARPLOT 


# var_to_plot = [
#     "Castro",
#     "Huet",
#     "Portzamparc",
#     ]


# to_graph = to_graph_all.filter(pl.col("variante").is_in(var_to_plot))

# # hue_order = to_graph["variante"].unique().to_list()
# hue_order = var_to_plot
# n= len(to_graph["variante"].unique())
# palette = list(cmap(np.linspace(0.1,0.9,n)))


# data = to_graph.filter(
#         pl.col(f"{ind}_extreme_outliers")==False
#         ).unpivot(
#             on=indicators_list,
#             index=["variante","index"],
#             variable_name="Indicateur",
#             value_name="Score",
#         )

# short_name = dict(pl.read_excel('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/short_indicateur.xlsx').iter_rows())

# mean_per_var = pl.col("Score").mean().over("Indicateur", "variante")
# max_mean_per_ind = mean_per_var.max().over("Indicateur")


# data = data.with_columns(
#         (pl.col("Score") / max_mean_per_ind).alias("Score normalisé par la valeur moyenne maximale"),
#         (pl.col("Indicateur").replace_strict(short_name,default=None)).alias("Indicateurs (abréviations)") 
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
#     alpha = 0.6,
#     errorbar=None,
#     order=order
#     )
# ax.legend(loc = "lower center",bbox_to_anchor=(0.5,1))
# # plt.tight_layout()
# plt.xticks(rotation=45,ha="right")
# # plt.show()
# plt.savefig(f"{FIGURE_DIR}/barplot_no_unc/all.pdf",dpi=300, bbox_inches="tight")

    
### COMPARAISON IPPS

# # def comparaison_ipp(ipps_list, aggregate = False) :
# #     for ipp in ipps_list :

# ## Comparaison ipps
# to_keep = ["mass_kg","energy_kWh"]
# comp_ipps  = ipps_no_lca.drop_nulls().group_by("variante","year",'material','type').agg([pl.col(c).sum() for c in to_keep])

# var = "Castro - Portzamparc"

# comp_ipps.filter(
#     pl.col("variante") == var
#     ).write_excel(f"/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/tables/{var}.xlsx")