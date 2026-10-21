import pandas as pd
import polars as pl
import seaborn as sns
import matplotlib.pyplot as plt
from cmcrameri import cm
import numpy as np
import bw2data as bd
from archetypes_re2020.config import FIGURES_DIR


cmap = cm.berlin

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})



df = pl.read_csv("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/external/nb_occ_par_m2.csv", schema_overrides={"value": pl.Float64})

x_order = [
    'moins de 30 ans',
    '30 à 39 ans',
    '40 à 49 ans',
    '50 à 64 ans',
    '65 à 74 ans',
    'Plus de 75 ans'
    ]

df = (
    df.with_columns(
        pl.col("categorie_age").replace_strict(x_order, range(len(x_order))).alias("_rank")
    )
    .sort("_rank")
)

hue_order = ("Individuel","Collectif")
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))
fig,ax = plt.subplots(figsize = (7,3))
g = sns.lineplot(df.to_pandas(),x= "categorie_age",y = "value",hue = "type",marker="o",palette = palette, alpha = 0.8,sort = False)
sns.move_legend(g,loc = "upper left",title = None)
ax.set_xlabel("Catégorie d'âge")
ax.set_ylabel("Surface par occupant ($m^{2}$)")
# plt.show()
plt.savefig(f"{FIGURES_DIR}/surface_par_occupant.pdf",dpi=300,bbox_inches = 'tight')
