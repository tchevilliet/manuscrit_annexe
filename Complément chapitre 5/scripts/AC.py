import polars as pl
import polars.selectors as cs
import numpy as np
import bw2data as bd
import bw2io as bi
import bw2calc as bc

from datetime import datetime
from tqdm import tqdm
from datetime import datetime

from bw25_utils import K,K2,K3,K4
from itertools import combinations

from remove_extreme_outliers import outliers
import seaborn as sns
import matplotlib.pyplot as plt

from cmcrameri import cm


FIGURE_DIR = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/figures"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
    "font.size": 10
})
cmap = cm.berlin


group_dict = { 
    "Electric Equipment" : "Consommations électriques",
    "Heating" : "Chauffage",
    "Interior Lighting" : "Éclairage",
    "Double vitrage U = 1.2" : "Menuiseries",
    "Water Systems" : "Consommations électriques",
    "reinforced concrete 20 cm" : "Béton armé",
    "Cooling": "Climatisation",
    "Generic LW Concrete" : "Béton et ciment",
    "plasterboard" : "Plâtre",
    "Generic Acoustic Tile" : "Laine minérale",
    "mineral wool 15 cm" : "Laine minérale",
    'EPDM' : "Étanchéité",
    'Enduit ciment 1 cm' : "Béton et ciment",
    'Gravier 5cm' : "Gravier",
    'Pare-Vapeur' : "Pare-Vapeur",
    'XPS 16cm' : "Isolant Polystyrène",
    'XPS 22cm' : "Isolant Polystyrène",
    'mineral wool 3 cm' : "Laine minérale",
    'water_use': "Consommations d'eau"
    }





bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")


ipps = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/processed/Lcas/2026-8-20-14h15-maquettes_impacts.parquet")

indicators_list = [c for c in ipps.columns if "ecoinvent" in str(c)]

df_ac = ipps.group_by(["material","program","type","variante","process_code","process_id"]).mean()


df_ac = df_ac.with_columns(
    [(
        pl.col(ind) / pl.col(ind).sum().over("variante")
        ).alias(f"{ind}_relativ") for ind in indicators_list
        ]
)


today = datetime.today()
horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

output_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report"
df_ac.write_excel(f"{output_folder}/tables/{horodatage}_analyse_contribution.xlsx")


var_to_plot = [
    "Castro",
    "Huet",
    "Portzamparc",

    # 'Castro - Huet',
    # 'Castro - Portzamparc',
    # 'Huet - Portzamparc',

    # 'Castro - Castro-nowindow',
    # 'Huet - Huet-nowindow',
    # 'Portzamparc - Portzamparc-nowindow'

    # 'Castro - Castro-bois',
    # 'Huet - Huet-bois',
    # 'Portzamparc - Portzamparc-bois'
    
    # 'Castro - Huet',
    # 'Castro-nowindow - Huet-nowindow',
    # 'Castro - Portzamparc',
    # 'Castro-nowindow - Portzamparc-nowindow',
    # 'Huet - Portzamparc',
    # 'Huet-nowindow - Portzamparc-nowindow',

    # 'Castro - Huet',
    # 'Castro-bois - Huet-bois',
    # 'Castro - Huet-bois',
    # 'Castro-bois - Huet',

    # 'Castro - Portzamparc',
    # 'Castro-bois - Portzamparc-bois',
    # 'Castro-bois - Portzamparc',
    # 'Castro - Portzamparc-bois',

    # 'Huet - Portzamparc',
    # 'Huet-bois - Portzamparc-bois',
    # 'Huet-bois - Portzamparc',
    # 'Huet - Portzamparc-bois',
    ]

to_graph = df_ac.group_by(
    ["variante","type","material"]
    ).agg(cs.numeric().sum()).filter(
    pl.col("variante").is_in(var_to_plot)
    ).with_columns(
        pl.when(pl.col("type") == "composant")
        .then(pl.col("material"))
        .otherwise(pl.col("type"))
        .alias("Contributeur")
        ).unpivot(
            on=[
                c for c in df_ac.columns if (
                    ("ecoinvent" in str(c)) and ("_relativ" not in str(c))
                )
                    ],
            index=["variante","Contributeur"],
            variable_name="Indicateur",
            value_name="Contribution",
            )

sum_per_var = pl.col("Contribution").sum().over("Indicateur", "variante")
max_sum_per_ind = sum_per_var.max().over("Indicateur")
    
to_graph = to_graph.with_columns(
    (pl.col("Contribution") / max_sum_per_ind).alias("Contribution normalisée par le maximum")
)
    
short_name = dict(pl.read_excel('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/short_indicateur.xlsx').iter_rows())
to_graph = to_graph.with_columns(
    (pl.col("Indicateur").replace_strict(short_name,default=None)).alias("Indicateurs (abréviations)")
    ).sort("Indicateurs (abréviations)")


import altair as alt


base = alt.Chart(to_graph.to_pandas()).encode(
    x=alt.X("variante:N", title="Variante"),
    y=alt.Y("Contribution normalisée par le maximum:Q", title="Score Normalisé"),
    color=alt.Color("Contributeur:N", title="Contributeur"),
)

chart = base.mark_bar().facet(
    column=alt.Column("Indicateurs (abréviations):N", title="Indicateurs")
)

chart.save("grouped_stacked.html")


import re
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

# Motifs retirés des noms d'indicateurs à l'affichage (insensible à la casse).
# Ex. "climate change - ecoinvent 3.9.1" -> "climate change"
DEFAULT_STRIP_PATTERNS = (r"ecoinvent[\s\d._v-]*",)


def simplify_label(label: str, patterns=DEFAULT_STRIP_PATTERNS) -> str:
    """Retire les motifs indiqués puis nettoie séparateurs et espaces."""
    out = str(label)
    for p in patterns:
        out = re.sub(p, "", out, flags=re.IGNORECASE)
    out = re.sub(r"\(\s*\)|\[\s*\]", "", out)           # parenthèses vides
    out = re.sub(r"\s*[-–—:,;|/]\s*(?=$)", "", out)     # séparateur final
    out = re.sub(r"^\s*[-–—:,;|/]\s*", "", out)         # séparateur initial
    out = re.sub(r"\s{2,}", " ", out).strip(" -–—:,;|/")
    return out or str(label)


def plot_grouped_stacked_bar(
    df: pl.DataFrame,
    value_col: str = "Contribution normalisée par le maximum",
    indicators: list[str] | None = None,
    n_indicators: int = 3,
    threshold: float = 0.02,
    figsize: tuple = (7, 3),
    output: str | None = "test.pdf",
    strip_patterns: tuple = DEFAULT_STRIP_PATTERNS,
    label_func=None,
    group_dict: dict[str, str] | None = None,
):
    """
    Grouped stacked bar chart restreint à quelques indicateurs.

    Parameters
    ----------
    df : pl.DataFrame
        Colonnes requises : variante, Contributeur, Indicateur, <value_col>
    value_col : str
        Colonne utilisée pour la hauteur des barres.
    indicators : list[str] | None
        Liste explicite d'indicateurs à afficher. Si None, on prend les
        `n_indicators` indicateurs ayant la plus grande contribution totale.
    n_indicators : int
        Nombre d'indicateurs affichés quand `indicators` est None.
    threshold : float
        Les contributeurs dont la contribution moyenne est inférieure à ce
        seuil sont regroupés dans « Autres ».
    figsize : tuple
        Taille de la figure matplotlib.
    output : str | None
        Chemin de sauvegarde (None = pas de sauvegarde).
    strip_patterns : tuple
        Regex retirées des noms d'indicateurs à l'affichage uniquement
        (par défaut : « ecoinvent » et son numéro de version).
    label_func : callable | None
        Fonction personnalisée str -> str pour nommer les indicateurs ;
        remplace `strip_patterns` si fournie.
    group_dict : dict | None
        {nom d'origine du contributeur: nom affiché}. Plusieurs contributeurs
        peuvent pointer vers le même nom : leurs valeurs sont alors sommées.
        Les contributeurs absents du dict gardent leur nom.
    """

    # ── 1. Sélection des indicateurs ───────────────────────────────────────
    if indicators is None:
        totals = (
            df.group_by(["Indicateur", "variante"])
            .agg(pl.col(value_col).sum().alias("tot"))
            .group_by("Indicateur")
            .agg(pl.col("tot").max())
            .sort("tot", descending=True)
        )
        indicators = totals["Indicateur"].head(n_indicators).to_list()
    df = df.filter(pl.col("Indicateur").is_in(indicators))
    if df.is_empty():
        raise ValueError("Aucun des indicateurs demandés n'est présent dans df.")

    # ── 1bis. Renommage / regroupement des contributeurs via group_dict ────
    # Les clés identiques après traduction (ex. deux contributeurs vers
    # « Consommations électriques ») sont sommées avant le calcul du seuil.
    if group_dict:
        unmapped = sorted(set(df["Contributeur"].unique().to_list()) - set(group_dict))
        if unmapped:
            print(f"Contributeurs absents de group_dict (nom conservé) : {unmapped}")
        df = (
            df.with_columns(pl.col("Contributeur").replace(group_dict))
            .group_by(["Indicateur", "variante", "Contributeur"])
            .agg(pl.col(value_col).sum())
        )

    # ── 2. Regroupement des contributeurs mineurs dans « Autres » ──────────
    contrib_mean = (
        df.group_by("Contributeur")
        .agg(pl.col(value_col).mean().alias("mean_contrib"))
        .sort("mean_contrib", descending=True)
    )
    major = contrib_mean.filter(pl.col("mean_contrib") > threshold)[
        "Contributeur"
    ].to_list()

    df_plot = (
        df.with_columns(
            pl.when(pl.col("Contributeur").is_in(major))
            .then(pl.col("Contributeur"))
            .otherwise(pl.lit("Autres"))
            .alias("Contributeur_merged")
        )
        .group_by(["Indicateur", "variante", "Contributeur_merged"])
        .agg(pl.col(value_col).sum())
    )

    # ── 3. Ordres ──────────────────────────────────────────────────────────
    # on conserve l'ordre des indicateurs fourni / calculé
    variants = df_plot["variante"].unique().sort().to_list()

    merged_order = (
        df_plot.group_by("Contributeur_merged")
        .agg(pl.col(value_col).mean().alias("mean"))
        .sort("mean", descending=True)["Contributeur_merged"]
        .to_list()
    )
    contributors = [c for c in merged_order if c != "Autres"]
    if "Autres" in merged_order:
        contributors.append("Autres")

    # ── 4. Couleurs ────────────────────────────────────────────────────────
    n_contrib = len(contributors)
    base = plt.cm.tab20(np.linspace(0, 1, 20))
    if n_contrib <= 20:
        palette = base[:n_contrib].copy()
    else:
        extras = plt.cm.Set3(np.linspace(0, 1, 12))[: n_contrib - 20]
        palette = np.vstack([base, extras])
    if "Autres" in contributors:
        palette[contributors.index("Autres")] = [0.75, 0.75, 0.75, 1.0]
    colors = dict(zip(contributors, palette))

    # ── 5. Tenseur [variante, indicateur, contributeur] ────────────────────
    v_idx = {v: i for i, v in enumerate(variants)}
    i_idx = {k: i for i, k in enumerate(indicators)}
    c_idx = {c: i for i, c in enumerate(contributors)}
    data = np.zeros((len(variants), len(indicators), len(contributors)))
    for row in df_plot.iter_rows(named=True):
        data[
            v_idx[row["variante"]],
            i_idx[row["Indicateur"]],
            c_idx[row["Contributeur_merged"]],
        ] += row[value_col]

    # ── 6. Tracé ───────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=figsize)

    n_var = len(variants)
    group_width = 0.8
    bar_width = group_width / n_var
    x_groups = np.arange(len(indicators))

    tick_pos, tick_lab = [], []
    for vi, variant in enumerate(variants):
        # barres centrées autour de la position du groupe
        x = x_groups + (vi - (n_var - 1) / 2) * bar_width
        bottom = np.zeros(len(indicators))
        for ci, contributor in enumerate(contributors):
            vals = data[vi, :, ci]
            ax.bar(
                x,
                vals,
                bar_width,
                bottom=bottom,
                label=contributor if vi == 0 else None,
                color=colors[contributor],
                edgecolor="white",
                linewidth=0.3,
            )
            bottom += vals
        tick_pos.extend(x)
        tick_lab.extend([variant] * len(indicators))

    # Niveau 1 : une étiquette de variante sous CHAQUE barre
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_lab, rotation=45, ha="right", va="top", fontsize=7)
    ax.tick_params(axis="x", length=2, pad=1)

    # Niveau 2 : nom de l'indicateur sous chaque groupe (texte retourné à la ligne)
    # (décalage en points pour passer sous les labels de variante)
    for gi, ind in enumerate(indicators):
        ax.annotate(
            "\n".join(
                textwrap.wrap(
                    label_func(ind) if label_func else simplify_label(ind, strip_patterns),
                    width=20,
                )
            ),
            xy=(x_groups[gi], 0),
            xycoords=ax.get_xaxis_transform(),
            xytext=(0, -42),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=7,
            fontweight="bold",
        )

    ax.set_ylabel(value_col, fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_xlim(-0.6, len(indicators) - 0.4)
    ax.set_ylim(0, max(data.sum(axis=2).max() * 1.1, 1.05))
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.axhline(y=1, color="black", linewidth=0.5)

    ax.legend(
        bbox_to_anchor=(1.01, 1),
        loc="upper left",
        frameon=True,
        prop={"size": 8},
        title=None,
        # title_fontsize=7,
    )

    if output:
        # bbox_inches="tight" inclut légende et labels hors des axes
        fig.savefig(output, bbox_inches="tight")
    return fig, ax


# plot_grouped_stacked_bar(to_graph, n_indicators=3, figsize=(7, 3))
plot_grouped_stacked_bar(
    to_graph,
    group_dict = group_dict,
    indicators=[
            # 'ecoinvent-3.11 | EF v3.1 | energy resources: non-renewable | abiotic depletion potential (ADP): fossil fuels',
            # 'ecoinvent-3.11 | EF v3.1 | photochemical oxidant formation: human health | tropospheric ozone concentration increase',
            # 'ecoinvent-3.11 | EF v3.1 | climate change: land use and land use change | global warming potential (GWP100)',
            # 'ecoinvent-3.11 | EF v3.1 | human toxicity: carcinogenic, inorganics | comparative toxic unit for human (CTUh)',
            # 'ecoinvent-3.11 | EF v3.1 | climate change: fossil | global warming potential (GWP100)',
            # 'ecoinvent-3.11 | EF v3.1 | human toxicity: non-carcinogenic, organics | comparative toxic unit for human (CTUh)',
            # 'ecoinvent-3.11 | EF v3.1 | eutrophication: terrestrial | accumulated exceedance (AE)',
            # 'ecoinvent-3.11 | EF v3.1 | climate change | global warming potential (GWP100)',
            # 'ecoinvent-3.11 | EF v3.1 | human toxicity: non-carcinogenic, inorganics | comparative toxic unit for human (CTUh)',
            # 'ecoinvent-3.11 | EF v3.1 | ecotoxicity: freshwater | comparative toxic unit for ecosystems (CTUe)',
            # 'ecoinvent-3.11 | EF v3.1 | eutrophication: marine | fraction of nutrients reaching marine end compartment (N)',
            # 'ecoinvent-3.11 | EF v3.1 | water use | user deprivation potential (deprivation-weighted water consumption)',
            # 'ecoinvent-3.11 | EF v3.1 | ionising radiation: human health | human exposure efficiency relative to u235',
            # 'ecoinvent-3.11 | EF v3.1 | human toxicity: carcinogenic, organics | comparative toxic unit for human (CTUh)',
            # 'ecoinvent-3.11 | EF v3.1 | particulate matter formation | impact on human health',
            # 'ecoinvent-3.11 | EF v3.1 | eutrophication: freshwater | fraction of nutrients reaching freshwater end compartment (P)',
            # 'ecoinvent-3.11 | EF v3.1 | material resources: metals/minerals | abiotic depletion potential (ADP): elements (ultimate reserves)',
            # 'ecoinvent-3.11 | EF v3.1 | ecotoxicity: freshwater, organics | comparative toxic unit for ecosystems (CTUe)',
            # 'ecoinvent-3.11 | EF v3.1 | climate change: biogenic | global warming potential (GWP100)',
            # 'ecoinvent-3.11 | EF v3.1 | human toxicity: non-carcinogenic | comparative toxic unit for human (CTUh)',
            'ecoinvent-3.11 | EF v3.1 | acidification | accumulated exceedance (AE)',
            'ecoinvent-3.11 | EF v3.1 | human toxicity: carcinogenic | comparative toxic unit for human (CTUh)',
            'ecoinvent-3.11 | EF v3.1 | ecotoxicity: freshwater, inorganics | comparative toxic unit for ecosystems (CTUe)',
            'ecoinvent-3.11 | EF v3.1 | land use | soil quality index',
            'ecoinvent-3.11 | EF v3.1 | ozone depletion | ozone depletion potential (ODP)',
        ],
        output=f"{output_folder}/figures/Contribution/AC_all.pdf"
    )
