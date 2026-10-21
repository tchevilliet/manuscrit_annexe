import polars as pl
import os
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns
from archetypes_re2020.config import FIGURES_DIR
import bw2data as bd
from cmcrameri import cm

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin



comp_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Comparaisons"

res = []
for file in tqdm(os.listdir(comp_folder),desc = 'Parcours des indicateurs'):
    full = os.path.join(comp_folder, file)
    if os.path.isfile(full):
        per = int(str(file).split(".")[0].split("_")[-1])
        tmp=pl.read_parquet(full)
        tmp = tmp.with_columns(
            pl.lit(per).alias("PER")
        )
        res.append(tmp)

to_graph = pl.concat(res)



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

hue_order = var_to_plot
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))


indicators = list(to_graph["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


for ind in tqdm(indicators,desc="Tracé indicateurs") :
    fig, ax = plt.subplots(figsize=(8,5))

    sns.boxenplot(
        data=to_graph.filter(
            pl.col("variante").is_in(var_to_plot),
            pl.col("indicator")==ind
            ),
        x = "PER",
        y = "score",
        hue = "variante",
        palette=palette,
        hue_order=hue_order
        )
    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    ax.axhline(0,linestyle = ":",color="black")
    ax.set_ylabel(f"{safe_name} - {dict_indicators_units[ind]}")

    plt.savefig(f"{FIGURES_DIR}/Comparaisons_pu/sensitivity/boxen_{safe_name}.pdf")
    plt.close()