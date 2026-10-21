import ast
import json
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from archetypes_re2020.config import FIGURES_DIR

JSON_FILE = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Discern/ponderees/2026-9-21-11h47_discern_indexes.json"
INDEX = "K4"            # "K" or "K4"
NCOLS = 5              # subplots per row when plotting all indicators

OUTPUT_FOLDER = f"{FIGURES_DIR}/Comparaisons_pu/Discern/ponderees"

OUTPUT_PREFIX=f"discern_heatmaps_{INDEX}"
OUTPUT_PDF = f"{OUTPUT_FOLDER}/{OUTPUT_PREFIX}.pdf"

KEYS = {"K": ("K_A", "K_B"), "K4": ("K4_A", "K4_B")}


# ----------------------------------------------------------------------------
# JSON -> square matrix
# ----------------------------------------------------------------------------
def to_matrix(res_ind, index):
    """Square matrix (variants x variants) for one indicator.

    Convention: cell (row r, column c) = probability that the COLUMN variant has a
    higher impact than the ROW variant (K: P(c > r), K4: P(c / r > gamma)).
    So a high value means the row variant is better than the column variant.
    For a pair (a, b) stored in the JSON:
        K_A  = P(B > A)  -> cell (row a, col b)
        K_B  = P(A > B)  -> cell (row b, col a)
    """
    entries = res_ind[index]
    pairs = {ast.literal_eval(k): v for k, v in entries.items()}   # "('1991', '1997')" -> tuple

    variants = []
    for a, b in pairs:
        for v in (a, b):
            if v not in variants:
                variants.append(v)

    M = pd.DataFrame(np.nan, index=variants, columns=variants)
    key_a, key_b = KEYS[index]
    for (a, b), v in pairs.items():
        if v is None:              # comparison not computed (e.g. K4 with negative totals)
            continue
        M.loc[a, b] = v[key_a]
        M.loc[b, a] = v[key_b]
    return M


# ----------------------------------------------------------------------------
# Plotting
# ----------------------------------------------------------------------------
def style(index):
    if index == "K":
        return dict(cmap="coolwarm", center=0.5, vmin=0.0, vmax=1.0)
    return dict(cmap="coolwarm", vmin=0.0, vmax=1.0)


def plot_heatmap(M, ax, title, index):
    sns.heatmap(
        M, ax=ax, annot=True, fmt=".2f", cbar=False, square=True,
        linewidths=0.5, linecolor="white", **style(index),
    )
    ax.set_facecolor("#e6e6e6")     # NaN cells (diagonal, missing comparisons) stay grey
    ax.set_title("\n".join(textwrap.wrap(title, 40)), fontsize=9)
    ax.set_xlabel("")
    ax.set_ylabel("")


def plot_all(res, index=INDEX, ncols=NCOLS, indicators=None, output=OUTPUT_PDF):
    indicators = indicators or list(res)
    nrows = int(np.ceil(len(indicators) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 4.2 * nrows), squeeze=False)

    for ax, ind in zip(axes.ravel(), indicators):
        plot_heatmap(to_matrix(res[ind], index), ax, ind, index)
    for ax in axes.ravel()[len(indicators):]:
        ax.axis("off")

    st = style(index)
    sm = ScalarMappable(
        norm=Normalize(vmin=st["vmin"], vmax=st["vmax"]), cmap=st["cmap"]
    )
    fig.colorbar(sm, ax=axes.ravel().tolist(), shrink=0.6, pad=0.02,
                 label="P(column worse than row)" if index == "K"
                 else "P(column / row > gamma)")
    fig.savefig(output, dpi=300, bbox_inches="tight")
    return fig


def plot_one(res, ind, index=INDEX):
    fig, ax = plt.subplots(figsize=(5, 4.5))
    plot_heatmap(to_matrix(res[ind], index), ax, ind, index)
    return fig


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    with open(JSON_FILE) as f:
        res = json.load(f)

    for ind in res.keys() :
        fig = plot_one(res,ind)
        safe_name = ind.replace(":", "-").replace("/", "-")
        safe_name = "-".join(safe_name.split("|")[1:])
        fig.savefig(f"{OUTPUT_FOLDER}/{OUTPUT_PREFIX}_{safe_name}.pdf", dpi=300, bbox_inches="tight")
        plt.close()
    # plot_all(res)
    # plt.show()