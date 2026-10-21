import polars as pl
import polars.selectors as cs

import pandas as pd
from collections import defaultdict
from tqdm import tqdm  # was missing in the original

import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from cmcrameri import cm
import bw2data as bd
import bw2calc as bc

from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.archetypes.buildings_based_archetypes_db import load_parquet_data, INPUT_PATH
from archetypes_re2020.data.source import INPUT_PATHS

import numpy as np
from collections import defaultdict
from scipy.sparse.linalg import spsolve
from tqdm import tqdm

output_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/figures/comparaison_calcul_re2020"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

lots = {
    "1": "VRD (Voirie et Réseaux Divers)",
    "2": "Fondations et infrastructure",
    "3": "Superstructure Maçonnerie",
    "4": "Couverture Étanchéité Charpente – Zinguerie",
    "5": "Cloisonnement Doublage – Plafonds suspendus Menuiseries intérieures",
    "6": "Façades et menuiseries extérieures",
    "7": "Revêtements des sols, murs et plafonds – Chape – Peintures",
    "8": "CVC (Chauffage Ventilation Refroidissement – ECS)",
    "9": "Installations sanitaires",
    "10": "Réseaux d’énergie (courant fort)",
    "11": "Réseaux de communication (courant faible)",
    "12": "Appareils élévateurs et autres équipements de transport intérieur",
    "13": "Équipement de production locale d’électricité",
}

sous_lots = {
    "1.1": "Réseaux (extérieurs, jusqu’au domaine public)",
    "1.2": "Stockage",
    "1.3": "Aires de stationnement extérieures",
    "2.1": "Fondations",
    "2.2": "Murs et structures enterrées (escalier de cave, parc de stationnement…)",
    "2.3": "Parcs de stationnement en superstructure (hors garages individuels)",
    "3.1": "Éléments horizontaux – Planchers, dalles, balcons",
    "3.2": "Éléments horizontaux – Poutres",
    "3.3": "Éléments verticaux – Façades",
    "3.4": "Éléments verticaux – Refends",
    "3.5": "Éléments verticaux – Poteaux",
    "3.6": "Escaliers et rampes",
    "3.7": "Éléments d’isolation",
    "3.8": "Maçonneries diverses (appuis de baie)",
    "4.1": "Toitures terrasses",
    "4.2": "Toitures en pente",
    "4.3": "Éléments techniques de toiture (cheminées, lanterneaux, etc.)",
    "5.1": "Cloisons et portes intérieures",
    "5.2": "Doublages mur, matériaux de protection, isolants et membranes",
    "5.3": "Plafonds suspendus",
    "5.4": "Planchers surélevés",
    "5.5": "Menuiseries, métalleries et quincailleries",
    "6.1": "Revêtement, isolation et doublage extérieur",
    "6.2": "Portes, fenêtres, fermetures, protections solaires",
    "6.3": "Habillages et ossatures",
    "7.1": "Revêtement des sols",
    "7.2": "Revêtement des murs et plafonds",
    "7.3": "Éléments de décoration et revêtements des menuiseries",
    "8.1": "Équipements de production (chaud/froid) – hors cogénération",
    "8.2": "Systèmes de cogénération",
    "8.3": "Systèmes d’émission",
    "8.4": "Traitement de l’air et éléments de désenfumage",
    "8.5": "Réseaux et conduits",
    "8.6": "Stockage (combustibles)",
    "8.7": "Fluides frigorigènes",
    "9.1": "Éléments sanitaires et robinetterie",
    "9.2": "Canalisations, réseaux et systèmes de traitement",
    "10.1": "Réseaux électriques",
    "10.2": "Ensemble de dispositifs pour la sécurité",
    "10.3": "Éclairage intérieur (général)",
    "10.4": "Éclairage extérieur",
    "10.5": "Systèmes d’automatisation et de contrôle",
    "10.6": "Tableaux et appareillages",
    "11.1": "Réseaux électriques et de communications",
    "11.2": "Systèmes de sécurité (personnes et biens)",
    "11.3": "Installations techniques et appareillages",
    "12.1": "Ascenseurs, monte‑charges, escaliers mécaniques, nacelles de nettoyage",
    "13.1": "Installation dédiée à la production d’électricité (panneaux, onduleur, etc.)",
}



### import des résultats RE2020


df_buildings = pl.read_csv(source=INPUT_PATHS["BUILDINGS"], ignore_errors=True)

ic_cols = cs.expand_selector(df_buildings, cs.contains("ic_composant_lot"))
df_ic_composant = (
    df_buildings.select(
        pl.concat_str(["projet_id", "batiment_index"], separator="_").alias("code"),
        cs.contains("ic_composant_lot"),
        "usage_principal_1_txt",
        "sref"
    )
    .rename(
        {
            "usage_principal_1_txt": "usage",
            **{c: c.split("_")[-1] for c in ic_cols},  # rename ic_composant_lot columns to their last part
        }
    )
    .with_columns(pl.lit("RE2020").alias("indicateur"))
)

df_ic_composant=df_ic_composant.unpivot(
    on = [str(i) for i in range(1,14)],
    index=["code","usage","indicateur","sref"],
    variable_name="lot"
    ).drop_nulls()


parts = df_ic_composant.partition_by("usage",'lot')
df_ic_composant = pl.concat([outliers(part, "value") for part in parts])
df_ic_composant = df_ic_composant.filter(pl.col("value_extreme_outliers") == False)

df_bdd = (
    df_ic_composant.filter(pl.col("sref") > 0)
    .group_by("usage", "lot")
    .agg(
        (
            (pl.col("value") * pl.col("sref")).sum()
            / pl.col("sref").sum()
        ).alias("value")
    )
)
bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
indicators = [
    m for m in bd.methods if (
        "gwp" in str(m).lower()
        and "no LT" not in str(m)
        and "EF v3.1" in str(m)
        and "fossil" not in str(m)
        and "biogenic" not in str(m)
        and "land" not in str(m))]

ind_en = [ind for ind in indicators if "15804" in str(ind)][0]


arch_db = bd.Database("2026-9-20-19h32_archetypes_RE2020_PRB_dynRE2020")

lca = bc.LCA(demand={arch_db.random(): 1.0}, method=ind_en)
lca.lci()
lca.lcia()

# Characterized impact per unit of activity (row vector), then one solve for everything
h = np.asarray((lca.characterization_matrix @ lca.biosphere_matrix).sum(axis=0)).ravel()
unit_scores = spsolve(lca.technosphere_matrix.T.tocsc(), h)   # score per 1 unit of each product

prod_idx = lca.dicts.product   # id -> row index

result = {}
for node in tqdm(arch_db, desc="Archétypes"):
    phi = list(node.production())[0]["amount"]
    res = defaultdict(float)
    for p in node.technosphere():
        lot = str(p.get("lot_ref")) or UNKNOWN_LOT
        res[lot] += p.amount * unit_scores[prod_idx[p.input.id]]
    result[node] = dict({ k : v/phi for k,v in res.items()})


# df = pd.DataFrame(result).T.fillna(0)          # rows = buildings, columns = lots
# df.index = [n["name"] for n in df.index]       # readable labels (adjust the key if needed)

# # Convert lot numbers to text with the "lots" dict (unknown keys are kept as is)
# df.columns = [lots.get(c, c) for c in df.columns]

# # Normalize: each building sums to 100 %
# df_norm = df.div(df.sum(axis=1), axis=0) * 100

# # Berlin colors, skipping the dark center
# n = df_norm.shape[1]
# k = n // 2
# pos = np.r_[np.linspace(0.2, 0.5, k), np.linspace(0.5, 0.8, n - k)]
# colors = [cm.vikO(x) for x in pos]

# ax = df_norm.plot(
#     kind="bar",
#     stacked=True,
#     figsize=(12, 6),
#     color=colors,
#     edgecolor="white",
#     linewidth=1.2,
# )
# ax.set_ylabel("Share of GWP (\\%)")
# ax.set_ylim(0, 100)

# # Reverse the legend so its top-to-bottom order matches the stacking order
# handles, labels = ax.get_legend_handles_labels()
# ax.legend(handles[::-1], labels[::-1], title="Lot",
#           bbox_to_anchor=(1.02, 1), loc="upper left")

# plt.tight_layout()
# plt.show()



###############################################################@
# --- Existing data (your LCA result), normalized ---
df = pd.DataFrame(result).T.fillna(0)
df.index = [n["name"] for n in df.index]
df.columns = [lots.get(c, c) for c in df.columns]
# df_norm = df.div(df.sum(axis=1), axis=0) * 100
df_norm = df

# --- Polars data: usages / lot / value -> wide pandas table, normalized ---
ref = (
    df_bdd.pivot(on="lot", index="usage", values="value", aggregate_function="sum")
        .to_pandas()
        .set_index("usage")
        .fillna(0)
)
ref.columns = [lots.get(c, c) for c in ref.columns]
# ref_norm = ref.div(ref.sum(axis=1), axis=0) * 100
ref_norm = ref
clean = lambda s: str(s).strip().lower().replace("_", " ")
df_norm.index = df_norm.index.map(clean)
ref_norm.index = ref_norm.index.map(clean)

# --- Align both tables on the same usages and the same lots ---
usages = [u for u in df_norm.index if u in ref_norm.index and "enseignement" not in str(u).lower()]
cols = list(df_norm.columns) + [c for c in ref_norm.columns if c not in df_norm.columns]
A = df_norm.reindex(index=usages, columns=cols, fill_value=0)
B = ref_norm.reindex(index=usages, columns=cols, fill_value=0)

# --- Berlin colors, skipping the dark center (one color per lot, shared by both sources) ---
n = len(cols)
k = n // 3
pos = np.r_[np.linspace(0, 0.35, k),np.linspace(0.65, 0.98, n-2*k),np.linspace(0, 0.35, k)]
colors = [cm.berlin(x) for x in pos]

# --- Grouped stacked bars: two bars per usage ---
x = np.arange(len(usages))
w = 0.38
gap = 0.06
off = w+gap
fig, ax = plt.subplots(figsize=(7, 4))
bot_a = np.zeros(len(usages))
bot_b = np.zeros(len(usages))

for col, color in zip(cols, colors):
    ax.bar(x -  off/ 2, A[col], w, bottom=bot_a, color=color,
           edgecolor="white", linewidth=1, label=col)
    ax.bar(x + off/ 2, B[col], w, bottom=bot_b, color=color,
           edgecolor="white", linewidth=1)
    bot_a += A[col].to_numpy()
    bot_b += B[col].to_numpy()

# Usage names centered under each pair, source labels under each bar
ax.set_xticks(x)
ax.set_xticklabels(usages, rotation=0, ha="center")
ax.tick_params(axis="x", pad=18)
ax.set_xticks(np.r_[x - w / 2, x + w / 2], minor=True)
ax.set_xticklabels(["Modèle"] * len(x) + ["Base"] * len(x), minor=True, fontsize=10)
ax.tick_params(axis="x", which="minor", length=0, pad=2)

ax.set_ylabel("Indicateur de changement climatique (GWP100)")
# ax.set_ylim(0, 100)

# Reverse the legend so it matches the stacking order
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles[::-1], labels[::-1], title="Lot",
          bbox_to_anchor=(1.02, 1), loc="upper left")

# plt.tight_layout()
# plt.show()

plt.savefig(f"{output_folder}/contrib_lots_comparaison_bdd.pdf",dpi=300, bbox_inches ='tight')