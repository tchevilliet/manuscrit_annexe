from ipywidgets import Output
import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd
from tqdm import tqdm 
import textwrap
from cmcrameri import cm

FIGURES_DIR = "report/figures"


bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

to_graph = pl.scan_parquet(
    "data/processed/archetypes_results/UA/multilca_archetypes_n_MC_1000_uncertainty_on_*.parquet",
    cast_options=pl.ScanCastOptions(integer_cast="allow-float"),
    ).collect()

output_folder = f"{FIGURES_DIR}/archetypes_buildings/UA"
# output_folder = f"{FIGURES_DIR}/archetypes_open_spaces"

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
unc_on = list(to_graph["uncertainty_on"].unique())

unc_on_to_plot =sorted([ u for u in unc_on if u !="C"])

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
    pl.col("uncertainty_on").is_in(unc_on_to_plot)
    )

# ####### BOXENPLOTS

dict_title = {
    "arch_collective_housing" : "Logement collectif",
    "arch_individual_housing" : "Maison individuelle",
    "arch_education" : "Enseignement",
    "arch_office" : "Bureau",
    "arch_roads" : "Route",
    "arch_vegetation" : "Espace végétalisé"
}
dict_legend = {
    "A" : r"$\mathbf{A}$",
    "B" : r"$\mathbf{B}$",
    "C" : r"$\mathbf{Q}$",
    "AB" : r"$\mathbf{A}, \mathbf{B}$",
    "ABC" : r"$\mathbf{A}, \mathbf{B}, \mathbf{Q} $",
}


hue_order = unc_on_to_plot
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))
legend = [dict_legend[h] for h in hue_order]

for d in tqdm(demand_to_plot,desc="demandes") :
    for ind in tqdm(indicators,desc = "indicateurs") :

        fig,ax = plt.subplots(figsize = (7,2))

        sns.boxenplot(
            to_graph.filter(
                pl.col("indicator") == ind,
                pl.col("demand") == d,
                ),
                x="score",
                hue = "uncertainty_on",
                palette=palette,
                hue_order=hue_order,
                alpha = 0.8,
                # showfliers= False
            )

        safe_name = ind.replace(":", "-").replace("/", "-")
        safe_name = "-".join(safe_name.split("|")[1:])
        # ax.axvline(0,linestyle = ":",color="black")

        # offset_text = ax.xaxis.get_offset_text().get_text()
        # ax.xaxis.get_offset_text().set_visible(False)
        label = f"{safe_name} \n {dict_indicators_units[ind]}"

        ax.set_xlabel(textwrap.fill(label, width=80))

        handles, _ = ax.get_legend_handles_labels()
        handles = [h for h in handles if h.get_label() in hue_order]

        ax.set_title(dict_title[d])

        ax.legend(handles, legend, loc="upper left", bbox_to_anchor=(1.01, 1))

        plt.savefig(f"{output_folder}/boxen_UA_{safe_name}_{d}.pdf",bbox_inches = 'tight')
        plt.close()


