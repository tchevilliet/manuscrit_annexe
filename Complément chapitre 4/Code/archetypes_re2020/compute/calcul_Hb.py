
"""
script pour faire tirages sur tous les bâtiments, à partir de tirages faits 
sur les composants construction de n_MC matrices H_b ou de Hb matrice 3D nb_bat x nb_impacts x N_mc

Problème de mémoire et de taille de fichier donc on tente d'optimiser

"""
import os
import bw2data as bd

import numpy as np
import scipy.sparse as sp
import polars as pl
import gc

from tqdm import tqdm
from datetime import datetime

from archetypes_re2020.config import PROCESSED_DATA_DIR


today = datetime.today()
horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

df_tirages_composants = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-10-2h41_MC_runs/scores_60.parquet")
n_mc=1000
output_dir = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Hb/260827-Hb_per"

# on se met dans le projet bw qui va bien : 
bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

# On charge la db de batiments en dico pour que ça itère plus vite :
print("Chargement du dictionnaire de la base brightway de bâtiments")
bat_db_dict = bd.Database("2026-8-10-0h50_buildings_cons_RE2020").load()


# On construit une sparse matrix avec les beta_ij 
# et on crée des arrays avec les infos du bat

all_comp = set()
bat_edges = []  # (nom, usage, {k: ratio_cumulé})

for bat_node in tqdm(bat_db_dict.values(), desc="précalcul bâtiments", total=len(bat_db_dict)):
    flux_ref = next(e["amount"] for e in bat_node["exchanges"] if e["type"] == "production")
    edges = {}
    for e in bat_node["exchanges"]:
        if e["type"] == "production":
            continue
        # opération non nécessaire normalement, à supprimer en faisant tirages sans ignorer liste dans tirages_processes.py
        k = e["input"][1]
        if "consommations_reseau" in k:
            k = "consommations_reseau"
        edges[k] = edges.get(k, 0.0) + e["amount"] / flux_ref  # cumul sur les différents lots et sous-lots par ex
        all_comp.add(k)
    bat_edges.append((bat_node["name"], bat_node["usage"], edges))

comp_list = sorted(all_comp)
comp_to_idx = {k: i for i, k in enumerate(comp_list)} # on map la position des composants
n_bat, n_comp = len(bat_edges), len(comp_list)

rows_idx, cols_idx, vals = [], [], []
noms_bat = np.empty(n_bat, dtype=object)
usages_bat = np.empty(n_bat, dtype=object)
for i, (nom, usage, edges) in enumerate(bat_edges):
    noms_bat[i], usages_bat[i] = nom, usage # on remplit les arrays avec les infos aux bons endroits
    for comp, ratio in edges.items():
        rows_idx.append(i); cols_idx.append(comp_to_idx[comp]); vals.append(ratio)

# matrice sparse (n_bat x n_comp)  pour peu d'usage mémoire (dataframe fait crasher...)
# float32 pour gagner de l'espace aussi, et on est pas à la virgule...
# chaque cellule est un beta_ij, matrice appelée T_{bat > comp} dans manuscrit
T_b = sp.csr_matrix((vals, (rows_idx, cols_idx)), shape=(n_bat, n_comp), dtype=np.float32)
print(f"T_b : {n_bat} bâtiments x {n_comp} composants, {T_b.nnz} non-zéros, {T_b.data.nbytes/1e6:.1f} Mo")

# On boucle sur les indicateurs, en considérant le nombre de tirages souhaité

indicators = df_tirages_composants["indicator"].unique().to_list()
tirages = sorted(df_tirages_composants["iteration"].unique().to_list())[:n_mc]

for indicator in tqdm(indicators, desc="indicateurs"):
    # on filtre sur tirages et indicateur et on garde que les cols utilisées
    df_ind = df_tirages_composants.filter(
        (pl.col("indicator") == indicator) & pl.col("iteration").is_in(tirages)
    ).select(["demand", "iteration", "score"]) 

    # on passe en format large plutôt que long avec n° iteration en colonne
    pivot = df_ind.pivot(values="score", index="demand", on="iteration")
    demand_order = pivot["demand"].to_list() # liste des composants
    iter_cols = [c for c in pivot.columns if c != "demand"]
    tirages_used = [int(c) for c in iter_cols]

    # une matrice avec chaque ligne = un composant, chaque colonne un tirage
    pivot_vals = pivot.select(iter_cols).to_numpy().astype(np.float32)  # (n_demand, n_tirages)

    # création d'une matrice de score, nulle partout pour l'instant
    S = np.zeros((n_comp, len(iter_cols)), dtype=np.float32)
    missing = []
    for i, k in enumerate(demand_order):
        if k in comp_to_idx:
            S[comp_to_idx[k], :] = pivot_vals[i, :] 
            # On remplit au bon endroit avec le score du composant dans la bonne ligne
        else:
            missing.append(k)
    if missing:
        print(f" {indicator}: clés non utilisées par aucun bâtiment: {missing[:5]}...")

    # On calcul la tranche de Hb correspondant à l'indicateur
    scores = T_b @ S  

    df_out = pl.DataFrame({
        "iteration": np.tile(np.array(tirages_used, dtype=np.int64), n_bat),
        "batiment": pl.Series(np.repeat(noms_bat, len(tirages_used))).cast(pl.Categorical),
        "usage": pl.Series(np.repeat(usages_bat, len(tirages_used))).cast(pl.Categorical),
        "score": scores.ravel(),
    }).with_columns(pl.lit(indicator).alias("indicator"))

    # On s'assure que le nom de fichier ne contient pas des caractères qui crée un bug, genre / et qu'il n'est pas trop long
    suffix = "_".join(indicator.split(" | ")[2:]).replace("/", "-")[:234]

    df_out.write_parquet(f"{output_dir}/scores_60_{suffix}_{n_mc}.parquet") # on enregistre dans un fichier parquet

    del scores, S, df_out, pivot, pivot_vals
    gc.collect()





