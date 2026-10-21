
import seaborn as sns
import matplotlib as mpl
import textwrap
import math

import bw2data as bd

from cmcrameri import cm

import numpy as np
import polars as pl
import questionary
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from archetypes_re2020.utils.utils import LOTS, SOUS_LOTS
from archetypes_re2020.config import FIGURES_DIR

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin

def plot_scores_delta(df_scores,arch1,arch2,indicator,output_dir):
    indicator_tuple = eval(indicator)
    indicator_str = " | ".join(indicator_tuple)
    scores1 = df_scores.filter(
        pl.col("demand")== arch1["name"],
        pl.col("method") == indicator_str
        )["score"].to_list()
    scores2 = df_scores.filter(
        pl.col("demand")== arch2["name"],
        pl.col("method") == indicator_str
        )["score"].to_list()
    
    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"
    res = [s1 - s2 for s1,s2 in zip(scores1,scores2)]

    fig, ax = plt.subplots()

    sns.histplot(res, element="step",ax = ax)

    ax.set_title(indicator_tuple[1:])


    fig.savefig(f"{output_dir}/{horodatage}_{arch1["name"]}-{arch2["name"]}_distrib.pdf",dpi = 300)

    print(f"Figure saved in {output_dir}")

    return fig


def plot_scores_distributions(df_scores, arch_list, indicator, output_dir):
    indicator_tuple = eval(indicator)
    indicator_str = " | ".join(indicator_tuple)
    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

    fig, ax = plt.subplots()
    df_filtered = df_scores.filter(
            pl.col("demand").is_in([arch["name"] for arch in arch_list]),
            pl.col("method") == indicator_str
        )

    n_hues = len(df_filtered['demand'].unique())

    palette = list(cmap(np.linspace(0.2, 0.8, n_hues)))
    sns.histplot(
        data = df_filtered,
        x= "score",
        hue = "demand",
        element="step", 
        ax=ax,
        palette= palette
        )

    ax.set_title(indicator_tuple[1:])
    # ax.legend()

    arch_names = "_".join([arch["name"] for arch in arch_list])
    if len(arch_names) > 50:
        arch_names = f"{len(arch_list)}_archetypes"

    fig.savefig(f"{output_dir}/{horodatage}_{arch_names}_distrib.pdf", dpi=300)
    print(f"Figure saved in {output_dir}")

    return fig


def main() :
    df_scores = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-5-5-16h30_MC_runs/scores.parquet")
    bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
    arch_db = bd.Database("2026-4-22-16h25_archetypes_RE2020_BB")
    
    indicators = [m for m in bd.methods if "gwp" in str(m).lower() and "no LT" not in str(m) and "EF v3.1" in str(m) and "fossil" not in str(m) and "biogenic" not in str(m) and "land" not in str(m)]
    
    indicator = str(indicators[0])

    output_dir = FIGURES_DIR/"Distributions" 
    arch1 = arch_db.search("Maison")[0]
    arch2 = arch_db.search("Logement")[0]
    # plot_scores_delta(df_scores,arch1,arch2,indicator,output_dir)
    plot_scores_distributions(
        df_scores,
        [a for a in arch_db if ("enseignement" not in str(a["name"]).lower())],
        indicator,
        output_dir
        )

if __name__ == "__main__":
    main()
