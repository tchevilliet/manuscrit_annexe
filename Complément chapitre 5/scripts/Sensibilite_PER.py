
import polars as pl
import numpy as np
import bw2data as bd
import bw2io as bi
import bw2calc as bc
import math
from tqdm import tqdm
from datetime import datetime
import textwrap
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
ipps = ipps.with_columns(
    pl.lit(50).alias("PER")
)
indicators_list = [c for c in ipps.columns if "ecoinvent" in str(c)]
dict_indicators_units = {}
for ind in indicators_list :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]

def new_impact(old_impact, process_code, new_PER) :
    if "consommation" in str(process_code) : 
        return old_impact*new_PER/50
    else : 
        DVE = float(process_code.split("_")[-1])
        n = math.ceil(50/DVE)
        new_n = math.ceil(new_PER/DVE)
        return old_impact*new_n/n


PERS = range(60,160,10)
frames = [ipps]

for new_PER in tqdm(PERS):
    new_ipps = ipps.with_columns(
        pl.lit(new_PER).alias("PER"),
        *[
            pl.struct([ind, "process_code"])
            .map_elements(
                lambda s, col=ind, p=new_PER: new_impact(
                    s[col], s["process_code"], p
                ),
                return_dtype=ipps.schema[ind],
            )
            .alias(ind)
            for ind in tqdm(indicators_list,leave= False)
        ],
    )
    frames.append(new_ipps)

# Concatenate all generated frames vertically
res = pl.concat(frames)



to_graph = res.drop_nulls().group_by("variante","year","index","PER").agg(
    [pl.col(ind).sum() for ind in indicators_list]
    )

results = []
for variante in tqdm(to_graph["variante"].unique()):
    for per in tqdm(to_graph["PER"].unique(),leave=False): 
        subset = to_graph.filter(pl.col("variante") == variante,pl.col("PER")==per)
        for ind in tqdm(indicators_list,leave=False):
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

    'Castro - Huet',
    'Castro - Portzamparc',
    'Huet - Portzamparc',

    # 'Castro - Castro-nowindow',
    # 'Huet - Huet-nowindow',
    # 'Portzamparc - Portzamparc-nowindow'

    # 'Castro - Castro-bois',
    # 'Huet - Huet-bois',
    # 'Portzamparc - Portzamparc-bois'
    
    # 'Castro - Huet',
    # 'Castro-nowindow - Huet-nowindow',
    # "Castro - Huet-nowindow",
    # "Castro-nowindow - Huet",
    # 'Castro - Portzamparc',
    # 'Castro-nowindow - Portzamparc-nowindow',
    # 'Castro - Portzamparc-nowindow',
    # 'Castro-nowindow - Portzamparc',
    # 'Huet - Portzamparc',
    # 'Huet-nowindow - Portzamparc-nowindow',
    # 'Huet - Portzamparc-nowindow',
    # 'Huet-nowindow - Portzamparc',

    # 'Castro - Huet',
    # 'Castro-bois - Huet-bois',
    # 'Castro - Portzamparc',
    # 'Castro-bois - Portzamparc-bois',
    # 'Huet - Portzamparc',
    # 'Huet-bois - Portzamparc-bois',
    ]


output_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/figures/Sensibilite/PER"



hue_order = var_to_plot
n= len(hue_order)
palette = list(cmap(np.linspace(0.1,0.9,n)))


# for ind in indicators_list : 
#     if "(ultimate reserves)" in str(ind) :
#         continue

#     to_graph = to_graph_all.filter(pl.col("variante").is_in(var_to_plot), pl.col(f"{ind}_extreme_outliers")==False)

#     fig,ax = plt.subplots(figsize = (7,4))
#     sns.boxenplot(
#         data=to_graph, 
#         x = "PER",
#         y = ind,
#         hue = "variante",
#         hue_order= hue_order,
#         palette = palette,
#         alpha = 0.6,
#         )
#     ax.axhline(0,color = "gray",zorder = 0,linestyle = ":")


#     ax.set_ylabel(textwrap.fill(f"{"-".join(ind.split("|")[1:])}\n{dict_indicators_units[ind]}", width=40))
#     ax.set_xlabel("Période d'étude de référence")
#     # ax.legend(loc="upper center", bbox_to_anchor=(0.5,1.2))
#     # plt.show()
#     plt.tight_layout()
#     plt.savefig(f"{output_folder}/{ind}.pdf",dpi = 300)


var_to_discern = [
    "Castro",
    "Huet",
    "Portzamparc",
]

combis_var = list(combinations(var_to_discern,r=2))

################################### ATTENTION K2 et K3 enlevés pour ganer du temps REMETTRE !!!!

# res = {per : {ind : {"K" : {},"K2" : {},"K3" : {},"K4" :{}} for ind in indicators_list}for per in [50,*PERS]}
res = {per : {ind : {"K" : {},"K4" :{}} for ind in indicators_list}for per in [50,*PERS]}

for per,d in tqdm(res.items(),desc = "Périodes d'étude de ref") :

    for ind in tqdm(d.keys(),desc = "Indicateurs",leave=False) : 
        if "(ultimate reserves)" in str(ind) :
            continue

        tmp = to_graph_all.select(
            ["variante","index",ind,f"{ind}_extreme_outliers","PER"]
            ).filter(
                pl.col(f"{ind}_extreme_outliers")==False,
                pl.col("PER")==per
                )
        # print(tmp.shape)

        df_by_variant = {
            v: tmp.filter(pl.col("variante") == v)
            for v in var_to_discern
        }

        for combi in tqdm(
            combis_var,
            desc = "Combinaisons de variantes",
            leave=False
            ):
            a, b = combi
            df = df_by_variant[a].join(
                df_by_variant[b],
                on="index",
                how="inner"
                )
            # print(df)
            a_mc = df[ind].to_numpy()
            b_mc = df[f"{ind}_right"].to_numpy()
            # print(len(a_mc),len(b_mc))
            key = str(combi)
            res[per][ind]["K"][key] = K(a_mc,b_mc)
            # res[per][ind]["K2"][key] = K2(a_mc,b_mc)
            # res[per][ind]["K3"][key] = K3(a_mc,b_mc)
            res[per][ind]["K4"][key] = K4(a_mc,b_mc,threshold=1.05)


records = []

for per, per_dict in res.items():
    for ind, ind_dict in per_dict.items():
        rows_by_combi = {}

        for metric, metric_dict in ind_dict.items():
            for combi_key, result in metric_dict.items():
                row = rows_by_combi.setdefault(combi_key, {
                    "PER": per,
                    "indicator": ind,
                    "combi": combi_key,
                })
                for subkey, value in result.items():
                    row[f"{metric}_{subkey}"] = value

        records.extend(rows_by_combi.values())

res_table = pl.DataFrame(records)


hue_order = [str(c) for c in combis_var]
n= len(hue_order)
palette = list(cmap(np.linspace(0.1,0.9,n)))

for ind in indicators_list : 
    if "(ultimate reserves)" in str(ind) :
        continue
    fig,ax = plt.subplots(figsize = (7,3))
    sns.lineplot(
        data= res_table.filter(pl.col("indicator") ==ind), 
        x = "PER",
        y = "K_K_A",
        hue = "combi",
        hue_order= hue_order,
        palette = palette,
        alpha = 0.8,
        )
    ax.set_xlabel("Période d'étude de référence")
    ax.set_ylabel("K_A pour une comparaison (A,B)")
   
    ax.set_title(f"{"-".join(ind.split("|")[1:])}")
    # ax.legend(loc="upper center", bbox_to_anchor=(1.3,0.5))
    # ax.set_ylim(0,1)
    sns.move_legend(ax,loc = "upper left", bbox_to_anchor = (1.01,0.99),title=None)
    plt.tight_layout()
    plt.savefig(f"{output_folder}/K_{ind}.pdf",dpi = 300)



# for ind in indicators_list : 
#     if "(ultimate reserves)" in str(ind) :
#         continue
#     fig,ax = plt.subplots(figsize = (7,3))
#     sns.lineplot(
#         data= res_table.filter(pl.col("indicator") ==ind), 
#         x = "PER",
#         y = "K2_K2_A",
#         hue = "combi",
#         hue_order= hue_order,
#         palette = palette,
#         alpha = 0.6,
#         )
#     ax.set_xlabel("Période d'étude de référence")
#     ax.set_ylabel("K2_A pour une comparaison (A,B)")
   
#     ax.set_title(f"{"-".join(ind.split("|")[1:])}")
#     # ax.legend(loc="upper center", bbox_to_anchor=(1.3,0.5))
#     # ax.set_ylim(0,1)
#     sns.move_legend(ax,loc = "upper left", bbox_to_anchor = (1.01,0.99),title=None)
#     plt.tight_layout()
#     plt.savefig(f"{output_folder}/K2_{ind}.pdf",dpi = 300)



for ind in indicators_list : 
    if "(ultimate reserves)" in str(ind) :
        continue
    fig,ax = plt.subplots(figsize = (7,3))
    sns.lineplot(
        data= res_table.filter(pl.col("indicator") ==ind), 
        x = "PER",
        y = "K4_K4_A",
        hue = "combi",
        hue_order= hue_order,
        palette = palette,
        alpha = 0.8,
        )
    ax.set_xlabel("Période d'étude de référence")
    ax.set_ylabel(textwrap.fill("K4_A pour une comparaison (A,B),seuil à 5%",width = 40))
    ax.set_title(f"{"-".join(ind.split("|")[1:])}")
    sns.move_legend(ax,loc = "upper left", bbox_to_anchor = (1.01,0.99),title=None)
    # ax.legend(loc="upper center", bbox_to_anchor=(1.3,0.5))
    # ax.set_ylim(0,1)
    plt.tight_layout()
    plt.savefig(f"{output_folder}/K4_{ind}.pdf",dpi = 300)