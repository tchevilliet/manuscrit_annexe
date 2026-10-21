import json
import numpy as np
import polars as pl
from polars.selectors import alpha
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

from tqdm import tqdm

from archetypes_re2020.config import FIGURES_DIR
from cmcrameri import cm




json_path = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Discern/2026-8-26-12h51_discern_indexes.json"
with open(json_path, 'r') as f:
    res = json.load(f)

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

def crop_cmap(cmap_name, start=0.2, end=0.8, n=256):
    """Take only the [start:end] portion of a colormap."""
    original = plt.get_cmap(cmap_name)
    colors = original(np.linspace(start, end, n))
    return LinearSegmentedColormap.from_list(f"{cmap_name}_crop", colors)


cmap = cm.vik

# palette = sns.color_palette(cmap,n_colors=256,desat = 0.8,as_cmap=True)

indicators_list = list(res.keys())


combis_var = list(list(res.values())[0]["K"].keys())




# hue_order = [str(c) for c in combis_var]
# n= len(hue_order)
# palette = list(cmap(np.linspace(0.1,0.9,n)))


# for ind in indicators_list : 
#     fig,ax = plt.subplots(figsize = (9,5))
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
#     ax.set_ylabel("Index K2_A pour une comparaison (A,B)")
#     ax.set_title(f"{"-".join(ind.split("|")[1:])}")
#     ax.legend(loc="upper center", bbox_to_anchor=(1.3,0.5))
#     # ax.set_ylim(0,1)
#     safe_name = ind.replace(":", "-").replace("/", "-")
#     safe_name = "-".join(safe_name.split("|")[1:])

#     output_folder = f"{FIGURES_DIR}/Comparaisons_pu/Discern"
#     plt.savefig(f"{output_folder}/K2_{ind}.pdf",dpi = 300, bbox_inches="tight")


##### HEATMAP



for ind in tqdm(indicators_list, desc = "Indicateurs") :

    for k_index in ["K","K2","K3","K4"] :

        data = res[ind][k_index]

        a_key, b_key = f"{k_index}_A", f"{k_index}_B"

        rows = []
        for pair_str, vals in data.items():
            var_a, var_b = eval(pair_str)
            rows.append({"var_a": var_a, "var_b": var_b, "val": vals[a_key]})
            rows.append({"var_a": var_b, "var_b": var_a, "val": vals[b_key]})

        df = pl.DataFrame(rows)

        df = df.pivot(values="val", index="var_a", on="var_b").sort("var_a")
    
        df = df.select([df.columns[0]] + sorted(df.columns[1:]))
        plt.figure(figsize=(8, 6))
        g = sns.heatmap(
            df.to_pandas().set_index(df.columns[0]), annot=True, fmt=".2f", cmap="coolwarm",
            # xticklabels=years, yticklabels=years,
            cbar_kws={"label": "cbar"}, vmin=0, vmax=1,
            square=True,
            alpha = 0.8,
            annot_kws= {"fontsize" : 12}
        )

        cbar = g.collections[0].colorbar
        cbar.set_label("Probabilité (Impact variante A $\geqslant$ Impact variante B)", fontsize=12) 
        plt.title(ind, fontsize=12)
        plt.xlabel("Variante A", fontsize=12)
        plt.ylabel("Variante B", fontsize=12)
        safe_name = ind.replace(":", "-").replace("/", "-")
        safe_name = "-".join(safe_name.split("|")[1:])

        output_folder = f"{FIGURES_DIR}/Comparaisons_pu/Discern"
        plt.savefig(f"{output_folder}/{k_index}_{safe_name}.pdf",dpi = 300, bbox_inches="tight")
        plt.close()