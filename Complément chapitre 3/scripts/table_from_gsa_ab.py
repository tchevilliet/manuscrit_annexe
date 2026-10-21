import polars as pl
import glob
from polars.selectors import alpha
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import textwrap

from cmcrameri import cm

FIGURES_DIR = "report/figures"

output_folder = "/mnt/ef432d92-e906-4d66-b70a-bdda12ad48be/2609_archetypes_metabo/report/figures/GSA_ab"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin

res = []
for filepath in glob.glob("/mnt/ef432d92-e906-4d66-b70a-bdda12ad48be/2609_archetypes_metabo/report/tables/GSA_ab/*.xlsx"):
    filename = str(filepath).split("/")[-1]
    indicator = "_".join(filename.split("_")[10:-2])
    df = pl.read_excel(filepath).with_columns(
        indicator = pl.lit(indicator)
    )
    res.append(df)

def from_to_shortname(shortname) :
    tmp = shortname.split("-->")
    return {"from" : tmp[0] , "to" : tmp[1]}

res = pl.concat(res).with_columns(
    pl.col("Shortname (without databases)").map_elements(
        lambda s: from_to_shortname(s),
        return_dtype=pl.Struct({"from": pl.String, "to": pl.String}),
    ).alias("tmp")
).unnest("tmp")


# indicators = res["indicator"].unique()

# hue_order =res["Type"].unique()
# palette= list(cmap(np.linspace(0.1,0.9,len(hue_order))))


def tex_escape(s: str) -> str:
    # usetex chokes on these characters in plain text
    for ch in ["\\", "&", "%", "#", "_", "$"]:
        if ch != "\\":
            s = s.replace(ch, "\\" + ch)
    return s

def make_label(src: str, dst: str, width: int = 40) -> str:
    src = textwrap.fill(tex_escape(src.strip()), width)
    dst = textwrap.fill(tex_escape(dst.strip()), width)
    return f"{src}\n" + r"$\rightarrow$ " + dst

indicators = res["indicator"].unique().to_list()
types_all = sorted(res["Type"].unique().to_list())
palette = cm.berlin(np.linspace(0.1, 0.9, len(types_all)))
color_of = dict(zip(types_all, palette))   # same color per Type across all figures

for ind in indicators:
    tmp = (
        res.filter(pl.col("indicator") == ind)
        .top_k(10, by="delta")
        .sort("delta", descending=True)
        .select("from", "to", "Type", "delta", "delta_conf")
    )

    labels = [make_label(f, t) for f, t in zip(tmp["from"], tmp["to"])]
    colors = [color_of[t] for t in tmp["Type"]]
    vals = tmp["delta"].to_numpy()
    conf = np.abs(tmp["delta_conf"].to_numpy())
    y = np.arange(tmp.height)

    fig, ax = plt.subplots(figsize=(7, 0.55 * tmp.height + 1.2))
    ax.barh(
        y, vals, xerr=conf, color=colors, alpha=0.85,
        error_kw=dict(ecolor="black", capsize=3, lw=1),
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=7)
    ax.invert_yaxis()                      # largest delta on top
    ax.set_xlabel(r"$\delta$")
    ax.legend(
        handles=[Patch(facecolor=color_of[t], alpha=0.85, label=tex_escape(t))
                 for t in types_all],
        loc="lower right", fontsize=7, frameon=False,
    )
    fig.savefig(f"{output_folder}/gsa_ab_{ind}.pdf", bbox_inches="tight")
    plt.close(fig)