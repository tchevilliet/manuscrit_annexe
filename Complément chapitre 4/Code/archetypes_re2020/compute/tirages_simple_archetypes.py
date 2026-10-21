
import bw2data as bd
import bw2calc as bc
import numpy as np
from pathlib import Path
import polars as pl
from tqdm import tqdm

from datetime import datetime
import questionary

from archetypes_re2020.utils.utils import select_from_list,select_database,select_project
from archetypes_re2020.config import PROCESSED_DATA_DIR


def mlca_to_arrays(demands, indicators_list,data_objs,n_iter=2):

    mlca = bc.MultiLCA(
        demands=demands,
        method_config={"impact_categories" : indicators_list},
        data_objs=data_objs,
        use_distributions=True,
        # seed_override=seed,
    )
    mlca.lci()
    mlca.lcia()

    # Première itération : on récupère les keys et la taille de la biosphère
    score_keys   = list(mlca.scores.keys())   # (indicateur, demande)
    demand_keys  = list(mlca.inventories.keys()) # nom des demandes
    n_bio        = mlca.biosphere_matrix.shape[0] # nombre d'EF

    #arrays pour stocker résultats
    scores = {
        k: np.zeros(n_iter)
        for k in score_keys
    }
    inventories = {
        d: np.zeros((n_iter, n_bio))
        for d in demand_keys
    }
    characterized_inventories = {
        k: np.zeros((n_iter, n_bio))
        for k in score_keys
    }

    # MC runs
    for i in tqdm(range(n_iter),desc="MC runs"):
        if i > 0:
            next(mlca)

        # Scores
        for k, v in mlca.scores.items():
            scores[k][i] = v

        # Inventaire agrégé sur les procédés 
        for d, inv_matrix in mlca.inventories.items():
            inventories[d][i, :] = np.asarray(inv_matrix.sum(axis=1)).flatten()

        # Inventaire caractérisé agrégé sur les procédés pour chaque indicateur
        for k, char_matrix in mlca.characterized_inventories.items():
            characterized_inventories[k][i, :] = np.asarray(char_matrix.sum(axis=1)).flatten()

    # Also return bio flow IDs once (same for all iterations)
    bio_flow_ids = np.array(
        [k for k, v in sorted(mlca.dicts.biosphere.items(), key=lambda x: x[1])],
        dtype=np.int64
    )

    return scores, inventories, characterized_inventories, bio_flow_ids


def get_bio_names_ids(bio_flow_ids) :
    bio_names = [str(bd.get_activity(int(i))) for i in bio_flow_ids]
    bio_ids_list = [int(i) for i in bio_flow_ids]

    return bio_names, bio_ids_list


def scores_to_df(scores,output_dir,write = True):
    # SCORES 
    # Shape: (n_iter × n_demand × n_method) rows with columns [iteration, demand, method, score]
    score_rows = []
    for (method, demand), arr in tqdm(scores.items(),desc="Parcours des scores"):
        method_str = " | ".join(method)
        for i, val in enumerate(arr):
            score_rows.append({
                "iteration": i,
                "demand":    demand,
                "method":    method_str,
                "score":     val,
            })

    df_scores = pl.DataFrame(score_rows).with_columns(
        pl.col("iteration").cast(pl.UInt32),
        pl.col("score").cast(pl.Float64),
    )
    if write :
        df_scores.write_parquet(output_dir / "scores.parquet", compression="zstd")

    print(f"Scores: {df_scores.shape}")
    return df_scores



def inventories_to_df(inventories, output_dir, bio_ids_list, bio_names,write = True) :
    # INVENTORIES
    # Choix d'un format long pour filtres plus faciles
    # Shape: (n_iter × n_demand × n_bio_flows) rows
    # Columns: [iteration, demand, flow_id, flow_name, value]
    inv_frames = []
    for demand, arr in tqdm(inventories.items(),desc="Parcours des inventaires"):          # arr: (n_iter, n_bio)
        n_iter_actual = arr.shape[0]
        # Vectorised: repeat iteration index and flow ids
        iters   = np.repeat(np.arange(n_iter_actual), len(bio_ids_list))
        flows   = np.tile(bio_ids_list, n_iter_actual)
        fnames  = np.tile(bio_names, n_iter_actual)
        values  = arr.flatten()

        inv_frames.append(
            pl.DataFrame({
                "iteration": iters,
                "demand":    demand,
                "flow_id":   flows,
                "flow_name": fnames,
                "value":     values,
            })
        )

    df_inv = pl.concat(inv_frames).with_columns(
        pl.col("iteration").cast(pl.UInt32),
        pl.col("flow_id").cast(pl.Int64),
        pl.col("value").cast(pl.Float64),
    )
    if write : 
        df_inv.write_parquet(output_dir / "inventories.parquet", compression="zstd")
    
    print(f"Inventories: {df_inv.shape}")
    return df_inv

def characterized_inventories_to_df(
    characterized_inventories,
    output_dir,
    bio_ids_list,
    bio_names,
    write = True) : 
    # CHARACTERIZED INVENTORIES
    # Choix d'un format long pour filtres plus faciles
    # Columns: [iteration, demand, indicator, flow_id, flow_name, value]
    char_frames = []
    for (indicator, demand), arr in tqdm(characterized_inventories.items(), desc = "Parcours des inventaires caractérisés"):
        indicator_str      = " | ".join(indicator)
        n_iter_actual   = arr.shape[0]
        iters   = np.repeat(np.arange(n_iter_actual), len(bio_ids_list))
        flows   = np.tile(bio_ids_list, n_iter_actual)
        fnames  = np.tile(bio_names, n_iter_actual)
        values  = arr.flatten()

        char_frames.append(
            pl.DataFrame({
                "iteration": iters,
                "demand":    demand,
                "indicator":    indicator_str,
                "flow_id":   flows,
                "flow_name": fnames,
                "value":     values,
            })
        )

    df_char = pl.concat(char_frames).with_columns(
        pl.col("iteration").cast(pl.UInt32),
        pl.col("flow_id").cast(pl.Int64),
        pl.col("value").cast(pl.Float64),
    )
    if write : 
        df_char.write_parquet(output_dir / "characterized_inventories.parquet", compression="zstd")

    print(f"Characterized inventories: {df_char.shape}")


def main() :
    n_MC = 5000

    bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
    arch_db = bd.Database("2026-4-22-16h25_archetypes_RE2020_BB")
    processes_list = [a for a in arch_db if "enseignement" not in str(a).lower()]
    # processes_list = [arch_db.random()]
    indicators_list = [m for m in bd.methods if "gwp" in str(m).lower() and "no LT" not in str(m) and "EF v3.1" in str(m) and "fossil" not in str(m) and "biogenic" not in str(m) and "land" not in str(m) and "EN15804" not in str(m)]
       
    demands = {str(p["name"]) :{p["id"] : 1.0} for p in processes_list}
    
    data_objs = bd.get_multilca_data_objs(
        demands,
        method_config = {"impact_categories" : indicators_list}
        )

    scores, inventories, characterized_inventories, bio_flow_ids = mlca_to_arrays(
        demands,
        indicators_list,
        data_objs,
        n_iter = n_MC
        )

    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

    output_dir = Path(PROCESSED_DATA_DIR/"MC_runs"/f"{horodatage}_MC_runs/")
    output_dir.mkdir(parents=True, exist_ok=True)

    bio_names, bio_ids_list = get_bio_names_ids(bio_flow_ids)
    df_scores = scores_to_df(scores,output_dir,write=True)
    df_inventories = inventories_to_df(inventories,output_dir,bio_ids_list,bio_names,write=True)
    df_inventories = characterized_inventories_to_df(
        characterized_inventories,
        output_dir,
        bio_ids_list,
        bio_names,
        write=True
        )

if __name__ == main() :
    main()