import seaborn as sns
import questionary
import matplotlib as mpl
import matplotlib.pyplot as plt
import polars as pl
import numpy as np
from cmcrameri import cm

from archetypes_re2020.data.remove_extreme_outliers import outliers
plt.clf()
plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
    "font.size": 10
})


df_e = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Erreurs/final_demand_vector_error.parquet")

df_e = df_e.with_columns(
    pl.col("code_composant").str.replace("/", "-", literal=True)
)

df_e = df_e.with_columns(
    error_surf = pl.col("q") - pl.col("theta")
)

keyword = questionary.text(message="Quel mot_clé de recherche pour le composant ?").ask()

choices = [c for c in df_e["code_composant"].unique().to_list() if keyword.lower() in str(c.lower())]
composant = questionary.select("quel composant ?",choices=choices).ask()

usages_to_keep = [u for u in df_e["usage"].unique().to_list() if "enseignement" not in str(u).lower()]

cmap = cm.berlin
n= len(usages_to_keep)
palette = list(cmap(np.linspace(0.2,0.9,n)))

hue_order = [
    [u for u in usages_to_keep if "maison" in str(u).lower()][0],
    [u for u in usages_to_keep if "bureau" in str(u).lower()][0],
    [u for u in usages_to_keep if "logement" in str(u).lower()][0],
    ]
print(hue_order)
colors_dict = dict(zip(hue_order, palette))
pos_dict = dict(zip(hue_order, range(len(hue_order))))

df = df_e.filter(
    pl.col("code_composant")==composant,
    # pl.col("usage")==usages_to_keep[0]
    )

# to_graph = outliers(df.filter(
#     pl.col("usage")==usages_to_keep[0],
#     ),"error_true")

# print(to_graph["extreme_outliers"].value_counts())

col = "error_true"

fig,axs = plt.subplots(1,n,figsize = (n*4,4))
for usage in usages_to_keep :
    i=pos_dict[usage]
    to_graph = outliers(df.filter(
        pl.col("usage")==usage,
        ),col)
    sns.histplot(
        data =to_graph.filter(pl.col("extreme_outliers")==False),
        x=col,
        color = colors_dict[usage],
        ax = axs[i],
        element = 'step',
        alpha = 0.6
        )
    axs[i].set_title(usage)
fig.suptitle(f"{composant}")


plt.savefig(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/figures/Distributions/erreurs sur f/f_error_{composant}.pdf",dpi = 300)
plt.clf()