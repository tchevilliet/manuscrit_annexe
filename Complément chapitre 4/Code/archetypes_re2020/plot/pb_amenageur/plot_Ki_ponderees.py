"""
Maps of K and K4 over the (x, y) plane (x = collective housing, y = offices),
from the grid files written by pb_amenageur_metric.py.

  - K4 : zones "Inférieur Référence / Indiscernable / Supérieur Référence"
         (classification applied AFTER interpolating K4_A and K4_B)
  - K  : continuous K_A = P(projet > référence), with the 0.5 contour

One figure per (reference, indicator, kind), saved as PDF.
"""
import os
import glob
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter

# Importing this module takes ~25 s (Brightway + dict_w loop): only the pure
# helpers are used, so you can move them to a light module if it bothers you.
from archetypes_re2020.compute.pu.pb_amenageur_metric import (
    GRID_DIR, param_amenageur, load_grid, interpolate, classify,
    REF_centrale_KEY, REF_lc_plus_KEY, REF_bur_plus_KEY, cout_projet,
    emprise_projet
)



FIG_DIR = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/figures/Pb_amenageur"

REF_KEYS = {
    "centrale": REF_centrale_KEY,
    "lc_plus": REF_lc_plus_KEY,
    "bur_plus": REF_bur_plus_KEY,
}

XLIM = (-50000, 550000)
YLIM = (-300000, 1500000)
ANNOT_COUT = (280000, 760000)         # position of the "Contrainte de coût" label
ANNOT_EMPRISE = (130000, 950000)      # position of the "Contrainte physique" label

SEUIL_SUP = 0.75
SEUIL_INF = 0.3


def set_style(usetex=True):
    plt.rcParams.update({
        "text.usetex": usetex,
        "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
        "font.family": "serif",
        "font.serif": "Computer Modern",
    })


def draw_constraints(ax, n=600):
    x = np.linspace(*XLIM, n)
    y = np.linspace(*YLIM, n)
    X, Y = np.meshgrid(x, y)
    ax.contour(X, Y, cout_projet(X, Y, param_amenageur),
               levels=[param_amenageur["subvention"]],
               colors="blue", linewidths=2, linestyles="--")
    ax.contour(X, Y, emprise_projet(X, Y, param_amenageur),
               levels=[param_amenageur["aire_projet"]],
               colors="black", linewidths=2, linestyles="-")
    ax.annotate("Contrainte de coût", xy=ANNOT_COUT, fontsize=11, color="blue",
                xytext=(23, -15), textcoords="offset points")
    ax.annotate("Contrainte physique", xy=ANNOT_EMPRISE, fontsize=11, color="black",
                xytext=(8, -12), textcoords="offset points")

def region_mask(X, Y):

    return (
        (cout_projet(X, Y, param_amenageur) <= param_amenageur["subvention"])
        & (emprise_projet(X, Y, param_amenageur) <= param_amenageur["aire_projet"])
    )


def style_axes(ax):
    ax.set_xlabel("Surfaces logements collectifs")
    ax.set_ylabel("Surfaces bureaux")
    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.spines["left"].set_position("zero")
    ax.spines["bottom"].set_position("zero")
    ax.spines["right"].set_color("none")
    ax.spines["top"].set_color("none")
    formatter = ScalarFormatter(useMathText=True)
    formatter.set_scientific(True)
    formatter.set_powerlimits((-3, 3))
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)


def plot_map(grid_file, kind, ref_xy, out_file, seuil_sup=SEUIL_SUP,
             seuil_inf=SEUIL_INF, method="linear", n_fine=400,title=None):
    """kind = "K4" (classified zones) or "K" (continuous K_A)."""
    xs, ys, G = load_grid(grid_file)
    if np.all(np.isnan(G[f"{kind}_A"])):
        print(f"skipped (all NaN, invalid indicator for {kind}): {os.path.basename(grid_file)}")
        return False

    xi = np.linspace(xs.min(), xs.max(), n_fine)
    yi = np.linspace(ys.min(), ys.max(), n_fine)
    Xi, Yi, A = interpolate(xs, ys, G[f"{kind}_A"], xi, yi, method)
    inside = region_mask(Xi, Yi)
    A = np.where(inside, A, np.nan)

    fig, ax = plt.subplots(figsize=(8, 4))

    if kind == "K4":
        _, _, B = interpolate(xs, ys, G["K4_B"], xi, yi, method)
        B = np.where(inside, B, np.nan)
        Zi = classify(A, B, seuil_sup, seuil_inf)
        surf = ax.contourf(Xi, Yi, Zi, levels=[-1.5, -0.5, 0.5, 1.5], cmap="coolwarm")
        cbar = fig.colorbar(surf, ax=ax, label="K4")
        cbar.set_ticks([-1, 0, 1])
        cbar.set_ticklabels(["Inférieur Référence", "Indiscernable", "Supérieur Référence"])
    else:
        surf = ax.contourf(Xi, Yi, A, levels=np.linspace(0, 1, 11), cmap="coolwarm")
        cbar = fig.colorbar(
                surf, ax=ax,
                label=r"$K_A = P(\text{Impact point} > \text{Impact référence})$",
            )
        ax.contour(Xi, Yi, A, levels=[0.5], colors="k", linewidths=1)

    ax.scatter(*ref_xy, color="black", zorder=5)
    ax.set_title(title)
    draw_constraints(ax)
    style_axes(ax)
    # ax.set_aspect("equal")

    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    fig.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return True


def main(kinds=("K4", "K"), refs=REF_KEYS, usetex=True):
    set_style(usetex)
    for ref_name, ref_xy in refs.items():
        prefix = f"k4_grid_{ref_name}_"
        for f in sorted(glob.glob(f"{GRID_DIR}/{prefix}*.parquet")):
            ind_name = os.path.basename(f)[len(prefix):-len(".parquet")]
            for kind in kinds:
                out = f"{FIG_DIR}/{kind}/pb_amenageur_{ind_name}_{kind}_{ref_name}.pdf"
                plot_map(f, kind, ref_xy, out,title=ind_name)


if __name__ == "__main__":
    main()
