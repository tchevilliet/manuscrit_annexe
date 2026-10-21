
import bw2data as bd
import bw2calc as bc
import numpy as np
from pathlib import Path
import polars as pl
from tqdm import tqdm

from datetime import datetime

from archetypes_re2020.config import PROCESSED_DATA_DIR


def mlca_to_arrays_scores_only(demands, indicators_list,data_objs,n_iter=2):

    mlca = bc.MultiLCA(
        demands=demands,
        method_config={"impact_categories" : indicators_list},
        data_objs=data_objs,
        use_distributions=True,
        # seed_override=seed,
    )
    mlca.lci()
    mlca.lcia()

    score_keys   = list(mlca.scores.keys())   # (indicateur, demande)


    #arrays pour stocker résultats
    scores = {
        k: np.zeros(n_iter)
        for k in score_keys
    }

    # MC runs
    for i in tqdm(range(n_iter),desc="MC runs"):
        if i > 0:
            next(mlca)

        # Scores
        for k, v in mlca.scores.items():
            scores[k][i] = v

    return scores


def scores_to_df(scores,output_dir,write = True):
    # SCORES 
    # Shape: (n_iter × n_demand × n_indicator) rows with columns [iteration, demand, indicator, score]
    score_rows = []
    for (indicator, demand), arr in tqdm(scores.items(),desc="Parcours des scores"):
        indicator_str = " | ".join(indicator)
        for i, val in enumerate(arr):
            score_rows.append({
                "iteration": i,
                "demand":    demand,
                "indicator":    indicator_str,
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


def write_run_report(folder: str, horodatage,n_mc : int, db, indicators_list, demands ):
    report = f"""# Monte Carlo Run Report

    horadatage :  {horodatage}  
    Nombre tirages : {n_mc}
    Base de données concernée : {db.name}
    Indicateurs : 
        """ + "\n".join(f"{k}" for k in indicators_list) + f"""
    Procédés concernés : 
        """ + "\n".join(f"{k}" for k in demands)

    path = f"{str(folder)}/description.md"
    with open(path, "w") as f:
        f.write(report)
    print(f"Rapport dans {path}")



def main() :
    n_MC = 5000

    bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
    # prod_db = bd.Database("2026-3-19-11h18_processes_RE2020")
    # prod_db = bd.Database('2026-8-9_composants_yc_consos')
    # prod_db = bd.Database('open_spaces')
    prod_db = bd.Database("2026-8-13-16h52_archetypes_RE2020_BB")
    # to_consider = ["'Consommations_électricité' (kilowatt hour, FR, ('custom_process',))",
    # "'Consommations_gaz' (kilowatt hour, FR, ('custom_process',))",
    # "'Consommations_bois' (kilowatt hour, FR, ('custom_process',))",
    # "'Consommations_eau' (cubic meter, FR, ('custom_process',))",
    # "'Consommations_réseau' (kilowatt hour, FR, ('custom_process',))"]
    # to_ignore = ["'Consommations_réseau_autres' (kilowatt hour, FR, ('custom_process',))",
    # "'Consommations_réseau_UVE' (kilowatt hour, FR, ('custom_process',))",
    # "'Consommations_réseau_gaz' (kilowatt hour, FR, ('custom_process',))"]
    # # processes_list = [p for p in prod_db if str(p) in to_consider]
    # processes_list = [p for p in prod_db if str(p) not in to_ignore]
    # processes_list = [p for p in prod_db]
    # processes_list = [p for p in prod_db if "Enseignement" not in str(p)]
    processes_list = [p for p in prod_db if "Maison" in str(p)]
    # processes_list = [arch_db.random()]
    # indicators_list = [m for m in bd.methods if "gwp" in str(m).lower() and "no LT" not in str(m) and "EF v3.1" in str(m) and "fossil" not in str(m) and "biogenic" not in str(m) and "land" not in str(m) and "EN15804" not in str(m)]
    
    # already_done  = [
    #     ('ecoinvent-3.11','EF v3.1','climate change','global warming potential (GWP100)'),
    #     ('ecoinvent-3.11','EF v3.1','eutrophication: freshwater','fraction of nutrients reaching freshwater end compartment (P)'),
    #     ('ecoinvent-3.11','EF v3.1','water use','user deprivation potential (deprivation-weighted water consumption)')
    #     ]
    # indicators_list = [m for m in bd.methods if "EF v3.1" in str(m) and "no LT" not in str(m) and "EN15804" not in str(m) and m not in already_done]
    # indicators_list = [m for m in bd.methods if "EF v3.1" in str(m) and "no LT" not in str(m) and "EN15804" not in str(m)] 
    indicators_list =[('ecoinvent-3.11','EF v3.1','ionising radiation: human health','human exposure efficiency relative to u235'),
    ('ecoinvent-3.11','EF v3.1','human toxicity: carcinogenic','comparative toxic unit for human (CTUh)'),
    ('ecoinvent-3.11','EF v3.1','human toxicity: carcinogenic, inorganics','comparative toxic unit for human (CTUh)'),
    ('ecoinvent-3.11','EF v3.1','human toxicity: non-carcinogenic','comparative toxic unit for human (CTUh)'),
    ('ecoinvent-3.11','EF v3.1','human toxicity: non-carcinogenic, inorganics','comparative toxic unit for human (CTUh)')]

    demands = {str(p["code"]) :{p["id"] : 1.0} for p in processes_list}
    
    data_objs = bd.get_multilca_data_objs(
        demands,
        method_config = {"impact_categories" : indicators_list}
        )

    scores = mlca_to_arrays_scores_only(
        demands,
        indicators_list,
        data_objs,
        n_iter = n_MC
        )

    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

    output_dir = Path(PROCESSED_DATA_DIR/"MC_runs"/f"{horodatage}_MC_runs/")
    output_dir.mkdir(parents=True, exist_ok=True)

    df_scores = scores_to_df(scores,output_dir,write=True)
    write_run_report(output_dir,horodatage,n_MC,prod_db,indicators_list,demands)

if __name__ == main() :
    main()