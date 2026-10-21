
import seaborn as sns
import matplotlib as mpl
import textwrap
import math

from cmcrameri import cm

import numpy as np
import polars as pl
import questionary
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from archetypes_re2020.utils.utils import LOTS, SOUS_LOTS
from archetypes_re2020.config import FIGURES_DIR


# Nord palette — accent colors Nord7 to Nord15
NORD_PALETTE = [
    "#8FBCBB",  # Nord7  - teal
    "#88C0D0",  # Nord8  - light blue
    "#81A1C1",  # Nord9  - blue
    "#5E81AC",  # Nord10 - dark blue
    "#BF616A",  # Nord11 - red
    "#D08770",  # Nord12 - orange
    "#EBCB8B",  # Nord13 - yellow
    "#A3BE8C",  # Nord14 - green
    "#B48EAD",  # Nord15 - purple
]
CUTOFF_COLOR = "grey"

def get_used_label(label: str, contrib_of: str, translate_dict: dict) -> str:
    if contrib_of not in ("lot", "sous-lot"):
        return label
    if isinstance(label, str) and "consommations" in label.lower():
        return label
    return translate_dict.get(label, label)



def rearrange_colors(cmap) :
    """Pour transformer une colormap divergente ou linéaire en categorical lisible

    Args:
        cmap (_type_): _description_

    Returns:
        _type_: _description_
    """
    tmp = cmap.colors
    n =len(tmp)
    mid = math.ceil(n / 2)
    l1 = range(mid)
    l2 = range(mid,n)
    if len(l1) == len(l2):
        indices = [val for pair in zip(l1,l2) for val in pair]
    else :
        indices = [val for pair in zip(l1[:-1],l2) for val in pair] + [l1[-1]]
    return [tmp[i] for i in indices]

def stackbars_plot(
    to_graph,
    contrib_of: str,
    contrib_to: str,
    cutoff: float = 0.02,  # valeur relative
    figsize: tuple = (8, 4),
    bar_width = 0.8
):
    plt.rcParams.update({
        "text.usetex": True,
        "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
        "font.family": "serif",
        "font.serif": "Computer Modern",
        "savefig.bbox": "tight",
        "savefig.format": "pdf",
    })

    translate_dict = {}
    if contrib_of == "lot":
        translate_dict = LOTS
    elif contrib_of == "sous-lot":
        translate_dict = SOUS_LOTS

    to_graph_sorted = (
        to_graph
        .group_by(contrib_of)
        .agg(pl.col(contrib_to).sum())
        .sort(contrib_to, descending=True)
    )

    labels = to_graph_sorted[contrib_of].to_list()
    values = to_graph_sorted[contrib_to].to_list()
    total = sum(abs(v) for v in values)

    # On divise en bars principales et en cutoff
    main_labels, main_values = [], []
    cutoff_labels, cutoff_values = [], []

    for label, value in zip(labels, values):
        if abs(value) / total < cutoff:
            cutoff_labels.append(get_used_label(label, contrib_of, translate_dict))
            cutoff_values.append(value)
        else:
            main_labels.append(label)
            main_values.append(value)

    # On ajoute une bar pour les cutoff en haut de la pile
    if cutoff_labels:
        main_labels.append("_cutoff")
        main_values.append(sum(cutoff_values))


    
    colors = mpl.colormaps['coolwarm'](np.linspace(0, 1, len(main_labels)))
    # colors = cm.lapazS.colors[2:][:len(main_labels)]
    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)

    bottom_pos, bottom_neg = 0.0, 0.0
    legend_entries = []

    for j, (label, value) in enumerate(zip(main_labels, main_values)):
        bottom = bottom_pos if value >= 0 else bottom_neg
        is_cutoff = label == "_cutoff"
        color = CUTOFF_COLOR if is_cutoff else colors[j]
        display_label = f"Sous le seuil de {cutoff*100} %" if is_cutoff else (
            get_used_label(label, contrib_of, translate_dict)
            )

        ax.bar(
            0, value, bar_width,
            bottom=bottom,
            color=color,
            edgecolor="white",
            linewidth=0.6,
            alpha=1.0,
        )
        legend_entries.append(mpatches.Patch(color=color, label=display_label))

        if value >= 0:
            bottom_pos += value
        else:
            bottom_neg += value

    ax.set_xlim(-1, 1)
    ax.set_xticks([])
    ax.axhline(0, color="#2E3440", linewidth=0.8, linestyle="--", alpha=0.5)

    # Legend: reversed to match visual top → bottom reading
    legend = ax.legend(
        handles=legend_entries[::-1],
        bbox_to_anchor=(1.05, 1),
        loc="upper left",
        frameon=False,
    )

    # Annotation below legend listing the cut-off labels
    if cutoff_labels:
        cutoff_text = f"Sous le seuil de {cutoff*100}" r"%"+ "\n" + "\n".join(
            rf"$\bullet$ {l} : {v:.2f}" for l, v in zip(cutoff_labels, cutoff_values)
        )
        ax.annotate(
            cutoff_text,
            xy=(1.05, 0),
            xycoords="axes fraction",
            fontsize=7,
            color="#4C566A",
            va="bottom",
            ha="left",
        )
    
    ax.set_ylabel(f"{contrib_to}")
    ax.set_title(to_graph["process"].unique()[0])
    

    return fig, ax


def choose_contrib_to(to_graph) :
    ef_or_ind = questionary.select(
        message = "Contribution à flux élémentaires ou indicateur ?",
        choices = ["EF","indicateur"],
    ).ask()

    relativ = questionary.confirm("Analyse en relatif ?").ask()

    if ef_or_ind == "EF" :
        efs = to_graph["contrib_to_ef"].unique().to_list()
        choices = [ef for ef,_ in zip(efs,range(25))] + ["Faire ma recherche"]
        
        ef = questionary.select(
            message = "Quel flux élémentaire ?",
            choices = choices
            ).ask()

        if ef == "Faire ma recherche" :
            keyword = questionary.text("Recherche : ").ask()
            ef = [ef for ef in efs if keyword.lower() in str(ef).lower()][0]
        
        res = to_graph.filter(
        pl.col("contrib_to_ef")==ef
        )
        if relativ :
            contrib_to = "relativ_inventory_value"
        else :
            contrib_to = "inventory_value"

    elif ef_or_ind == "indicateur" :
        inds = to_graph["contrib_to_ind"].unique().to_list()
        choices = [ind for ind,_ in zip(inds,range(25))] + ["Faire ma recherche"]
        
        ind = questionary.select(
            message = "Quel indicateur ?",
            choices = choices
            ).ask()

        if ind == "Faire ma recherche" :
            keyword = questionary.text("Recherche : ").ask()
            ind = [ind for ind in inds if keyword.lower() in str(ind).lower()][0]

        res = to_graph.filter(
            pl.col("contrib_to_ind")==ind
            )
        if relativ :
            contrib_to = "relativ_charac_inventory_value"
        else :
            contrib_to = "charac_inventory_value"
    

    return res, contrib_to

def choose_contrib_of(df) : 
    choices = list(df.columns)

    contrib_of = questionary.select(
        message = "Contribution de ?",
        choices = choices
        ).ask()
    
    return contrib_of


def main() :
    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"
    
    

    input_path = questionary.path(
        "Quel fichier utiliser pour l'analyse de contribution?"
    ).ask()

    to_graph = pl.read_parquet(input_path)

    to_graph_filtered, contrib_to = choose_contrib_to(to_graph)

    contrib_of = choose_contrib_of(to_graph_filtered)

    process = to_graph_filtered["process"].unique().to_list()[0]

    output_path = (
        FIGURES_DIR/ "Contribution"/f"{horodatage}_AC_de_{contrib_of}_a_{contrib_to}_{process}.pdf"
        )

    fig, ax = stackbars_plot(
        to_graph=to_graph_filtered,
        contrib_of=contrib_of,
        contrib_to=contrib_to,
    )

    fig.savefig(output_path,dpi=300)

if __name__ == "__main__":
    main()