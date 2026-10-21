import os

# --- Parallel settings --------------------------------------------------------
# Must be set BEFORE numpy / pypardiso are imported (spawned workers re-import
# this module, so they pick these values up too).
N_WORKERS = 8            # limited by RAM (each worker holds its own matrices + factorization)
THREADS_PER_WORKER = 3   # N_WORKERS * THREADS_PER_WORKER <= 28 cores
for _v in ("MKL_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = str(THREADS_PER_WORKER)

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from queue import Empty

import bw2calc as bc
import bw2data as bd
import numpy as np
import polars as pl
from tqdm import tqdm

from archetypes_re2020.config import PROCESSED_DATA_DIR


def run_chunk(seed, n_iter, project, demands, indicators_list, progress=None):
    """One worker: its own MultiLCA, its own seed, n_iter Monte Carlo draws.
    Puts a 1 on `progress` after each finished iteration."""
    bd.projects.set_current(project)
    data_objs = bd.get_multilca_data_objs(
        demands, method_config={"impact_categories": indicators_list}
    )
    mlca = bc.MultiLCA(
        demands=demands,
        method_config={"impact_categories": indicators_list},
        data_objs=data_objs,
        use_distributions=True,
        seed_override=seed,
    )
    mlca.lci()
    mlca.lcia()

    scores = {k: np.zeros(n_iter) for k in mlca.scores}
    for i in range(n_iter):
        if i > 0:
            next(mlca)
        for k, v in mlca.scores.items():
            scores[k][i] = v
        if progress is not None:
            progress.put(1)
    return scores


def mlca_parallel(project, demands, indicators_list, n_iter, n_workers=N_WORKERS, base_seed=42):
    seeds = [int(s) for s in np.random.SeedSequence(base_seed).generate_state(n_workers)]
    sizes = [len(c) for c in np.array_split(np.arange(n_iter), n_workers)]

    ctx = mp.get_context("spawn")  # safer than fork with MKL / sqlite
    with ctx.Manager() as manager:
        progress = manager.Queue()
        with ProcessPoolExecutor(n_workers, mp_context=ctx) as ex:
            futures = [
                ex.submit(run_chunk, seed, size, project, demands, indicators_list, progress)
                for seed, size in zip(seeds, sizes)
            ]
            # The bar stays at 0 during worker setup (build + lci + lcia), then moves.
            with tqdm(total=n_iter, desc="MC runs") as bar:
                while bar.n < n_iter:
                    try:
                        bar.update(progress.get(timeout=2))
                    except Empty:
                        for f in futures:  # surface a crashed worker instead of hanging
                            if f.done() and f.exception() is not None:
                                raise f.exception()
                        if all(f.done() for f in futures):
                            break
            parts = [f.result() for f in futures]

    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def scores_to_df(scores, output_dir, write=True):
    # Columns: iteration, demand, indicator, score
    frames = []
    for (indicator, demand), arr in scores.items():
        n = len(arr)
        frames.append(
            pl.DataFrame(
                {
                    "iteration": np.arange(n, dtype=np.uint32),
                    "demand": [demand] * n,
                    "indicator": [" | ".join(indicator)] * n,
                    "score": arr.astype(np.float64),
                }
            )
        )
    df_scores = pl.concat(frames)
    if write:
        df_scores.write_parquet(output_dir / "scores.parquet", compression="zstd")
    print(f"Scores: {df_scores.shape}")
    return df_scores


def write_run_report(folder, horodatage, n_mc, db, indicators_list, demands):
    lines = [
        "# Monte Carlo Run Report",
        "",
        f"horodatage : {horodatage}",
        f"Nombre tirages : {n_mc}",
        f"Base de données concernée : {db.name}",
        "Indicateurs :",
        *[f"- {k}" for k in indicators_list],
        "Procédés concernés :",
        *[f"- {k}" for k in demands],
    ]
    path = Path(folder) / "description.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Rapport dans {path}")


def main():
    n_MC = 5000
    project = "2026-01-13-ecoinvent-3.11-cutoff"

    bd.projects.set_current(project)
    prod_db = bd.Database("2026-8-13-16h52_archetypes_RE2020_BB")
    processes_list = [p for p in prod_db if "Maison" in str(p)]

    indicators_list = [
        ("ecoinvent-3.11", "EF v3.1", "ionising radiation: human health", "human exposure efficiency relative to u235"),
        ("ecoinvent-3.11", "EF v3.1", "human toxicity: carcinogenic", "comparative toxic unit for human (CTUh)"),
        ("ecoinvent-3.11", "EF v3.1", "human toxicity: carcinogenic, inorganics", "comparative toxic unit for human (CTUh)"),
        ("ecoinvent-3.11", "EF v3.1", "human toxicity: non-carcinogenic", "comparative toxic unit for human (CTUh)"),
        ("ecoinvent-3.11", "EF v3.1", "human toxicity: non-carcinogenic, inorganics", "comparative toxic unit for human (CTUh)"),
    ]

    demands = {str(p["code"]): {p["id"]: 1.0} for p in processes_list}

    scores = mlca_parallel(project, demands, indicators_list, n_iter=n_MC)

    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"
    output_dir = Path(PROCESSED_DATA_DIR / "MC_runs" / f"{horodatage}_MC_runs")
    output_dir.mkdir(parents=True, exist_ok=True)

    scores_to_df(scores, output_dir, write=True)
    write_run_report(output_dir, horodatage, n_MC, prod_db, indicators_list, demands)


# Required with the "spawn" start method: without this guard every worker
# would re-run main() when it re-imports the module.
if __name__ == "__main__":
    main()