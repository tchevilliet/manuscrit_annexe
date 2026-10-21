
import seaborn as sns
import matplotlib as mpl
import textwrap
import math

from scipy.stats import lognorm
from cmcrameri import cm

import numpy as np
import polars as pl
import questionary
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from archetypes_re2020.utils.utils import get_name
from archetypes_re2020.config import FIGURES_DIR


df_int = pl.read_excel("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/2026-2-6-10h16_intensites_matieres_RE2020.xlsx")

usages_to_keep = ["Maison individuelle ou accolée","Bureau","Logement collectif"]

# df_int = df_int.with_columns(
    # pl.col("quant_surf")
    # .str.strip_chars("[]")
    # .str.split(", ")
    # .list.len()
    # .alias("list_len")
# )
    # 

df_int = df_int.with_columns(
    pl.col("quant_surf")
    .str.strip_chars("[]")
    .str.split(", ")
    .list.eval(
        pl.element()
        .str.strip_chars(", ")
        .cast(pl.Float64, strict=False)  # null quand problème
    )
    .alias("quant_surf_list")
)

df_int = df_int.with_columns(
    pl.col("quant_surf_list")
    .list.len()
    .alias("list_len")
)

top = 3

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
    "font.size": 10
})

cmap = cm.berlin
n_hues = len(usages_to_keep)

palette = list(cmap(np.linspace(0.2,1,n_hues)))

for j, u in enumerate(usages_to_keep) : 
    color = palette[j]
    to_graph=df_int.filter(pl.col("usage")==u,~pl.col("produit").str.contains("Approche simplifiée"),pl.col("produit").str.contains("Structure"),~pl.col("produit").str.contains("Chape")).top_k(top, by="list_len")

    fig, ax = plt.subplots(1,top,figsize=(4*top,4), constrained_layout=True)

    for i, prod in enumerate(to_graph["produit"]) :
        tmp = to_graph.filter(pl.col("produit")==prod)
        nb_bat =tmp["target_len"][0]
        nb_non_zeros = tmp["list_len"][0]
        nb_zeros = nb_bat-nb_non_zeros
        print(f"{u}, non-zeros = {nb_non_zeros}")
        
        prod_dict = eval(prod)
        prod_name = get_name(prod_dict,2)

        data = tmp["quant_surf_list"][0].to_numpy()
        
        sns.histplot(data = data ,ax = ax[i], stat="density", element = "step",kde=False, color=color, alpha= 0.4)
        x = np.linspace(min(data), max(data), 1000)
        
        pdf = lognorm.pdf(x,tmp["shape"],tmp["loc"], tmp["scale"])
        ax[i].plot(x, pdf, color = 'r', linewidth=1,label=f'Log-Norm Fit')
        
        title = f"{prod_name} en {prod_dict['unite_uf_txt']} \n Nombre de zéros (non représentés) : {nb_zeros} sur {nb_bat}"
        wrapped_title = textwrap.fill(title, width=45)
        ax[i].set_title(wrapped_title)

    fig.savefig(f"{FIGURES_DIR}/intensites_matieres/{u}_top{top}.pdf", bbox_inches='tight')
    plt.clf()
