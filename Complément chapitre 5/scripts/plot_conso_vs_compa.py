import polars as pl
import seaborn as sns
import matplotlib.pyplot as plt
from cmcrameri import cm
import numpy as np

plt.clf()
plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
    "font.size": 10
})
cmap = cm.berlin


df = pl.read_ods("consos_vs_compacite.ods")

df = df.with_columns((pl.col("type").cast(pl.Utf8) + "_" + pl.col("programme").cast(pl.Utf8)).alias("type_programme"))


n= len(df["type_programme"].unique())
palette = list(cmap(np.linspace(0.9,0.1,n)))

fig, ax = plt.subplots(figsize = (8.5,3.5))

g=sns.lmplot(data = df,x = "Indice",y = "conso surf",hue = "type_programme",ci=None, palette = palette,line_kws={'ls':":", "alpha" : 0.3}, height = 4,aspect = 2)

g.ax.set_ylabel(r"Consommation surfacique annuelle ($ \text{kWh.m}^{-2}$)")
g.ax.set_xlabel("Indice de compacité")
g.savefig("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/figures/consos_vs_compacite.pdf",dpi = 300)
# plt.show()

