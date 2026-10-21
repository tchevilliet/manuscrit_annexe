import polars as pl
import numpy as np

from functools import reduce
from itertools import combinations
import os
from tqdm import tqdm
from datetime import datetime
import bw2data as bd
import bw2io as bi

import json

from archetypes_re2020.config import PROCESSED_DATA_DIR, TABLES_DIR
from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.utils.bw25_utils import K,K2,K3,K4

from archetypes_re2020.compute.pu.compare_pu_weighted import build_Hb_filtered, f_tilde_from_var,open_by_iter,prepare_groups,iteration_distributions,programmes

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

PER = 50
N_BINS = 2000 # résolution 
GAMMA = 1.05

pu_res_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Comparaisons/ponderees/n_bins_2000"

Hbs_folder = f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Hb/260827-Hb_per/{PER}"
df_open_scores = pl.read_parquet(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-25-23h5_MC_runs/scores_{PER}.parquet")


#### POIDS DES BATIMENTS POUR CHAQUE ARCHETYPE

arch_db = bd.Database("2026-8-13-16h52_archetypes_RE2020_BB")
dict_w = {}

for a in tqdm(arch_db) :
    phi = list(a.production())[0]["amount"]
    tmp = {e["input"][1] : e["amount"]/phi for e in tqdm(a.technosphere(),leave = False)}
    dict_w = dict_w | tmp


to_assess_dict = dict(programmes)


def prepare(Hb):
    """Once per indicator: groups + robust usage ranges (quantiles instead of min/max
    so the grid resolution isn't diluted by a few extreme buildings)."""
    groups = prepare_groups(Hb)
    ranges = Hb.group_by("usage").agg(
        mn=pl.col("score").quantile(0.001), mx=pl.col("score").quantile(0.999)
    )
    usage_ranges = {r["usage"]: (r["mn"], r["mx"]) for r in ranges.iter_rows(named=True)}
    return groups, usage_ranges


def run_variant(Hb, var_dict, var_key, indicator, df_open_scores, prep=None):
    groups, usage_ranges = prep if prep is not None else prepare(Hb)
    f_tilde = f_tilde_from_var(var_dict, set(usage_ranges))
    open_it = open_by_iter(df_open_scores, var_dict, indicator)
    return iteration_distributions(groups, usage_ranges, f_tilde, open_it, var_key, indicator)


def K_pmf(res_diff):
    """res_diff: rows of one 'A - B' variant, one indicator (iteration, score, prob)."""
    n_it = res_diff["iteration"].n_unique()
    ka = res_diff.filter(pl.col("score") < 0)["prob"].sum() / n_it   # P(B > A)
    kb = res_diff.filter(pl.col("score") > 0)["prob"].sum() / n_it   # P(A > B)
    return {"K_A": ka, "K_B": kb, "ties": 1 - ka - kb}


def K4_pmf(Hb, vA, vB, indicator, df_open, gamma=GAMMA, prep=None):
    out = {"gamma_0": gamma}
    for key, (vX, vY) in {"K4_A": (vA, vB), "K4_B": (vB, vA)}.items():
        d = {k: vY[k] - gamma * vX[k] for k in vX}          # Y - gamma * X
        res = run_variant(Hb, d, key, indicator, df_open, prep=prep)
        out[key] = res.filter(pl.col("score") > 0)["prob"].sum() / res["iteration"].n_unique()
    return out


def get_diff(tmp, a, b):
    """Rows of the 'a - b' variant; if only 'b - a' exists, use it and flag the swap."""
    d = tmp.filter(pl.col("variante") == f"{a} - {b}")
    if d.height:
        return d, False
    d = tmp.filter(pl.col("variante") == f"{b} - {a}")
    return (d, True) if d.height else (None, False)


def main() :

    res = {}

    var_to_assess = list(to_assess_dict.keys())


    for file in tqdm(os.listdir(Hbs_folder), desc="Indicateurs"):
        full = os.path.join(Hbs_folder, file)
        if not os.path.isfile(full):
            continue

        Hb = build_Hb_filtered(full, dict_w)
        ind = Hb["indicator"].unique()[0]

        res[ind] = {"K": {}, "K4": {}}

        prep = prepare(Hb)       # computed once per indicator
        del Hb                   # only prep is needed from here

        ind_name = "_".join(file.split("_")[1:-1])          # same rule as in the main script
        pu_file = os.path.join(pu_res_folder, f"zac_tous_ind_{PER}_{ind_name}.parquet")

        needed = var_to_assess + [f"{a} - {b}" for a, b in combinations(var_to_assess, r=2)]
        tmp = (
            pl.scan_parquet(pu_file)
            .filter(pl.col("variante").is_in(needed))       # skips the K4_* variants
            .select("variante", "iteration", "score", "prob")
            .collect()
        )
        
        EPS = 0.01    # accepted error on K4 (max probability of a non-positive total)

        def neg_mass(tmp, v):
            d = tmp.filter(pl.col("variante") == v)
            return float(d.filter(pl.col("score") <= 0)["prob"].sum() / d["iteration"].n_unique())

        neg = {v: neg_mass(tmp, v) for v in var_to_assess}

        # min_score = {v: tmp.filter(pl.col("variante") == v)["score"].min() for v in var_to_assess}

        for a, b in tqdm(list(combinations(var_to_assess, r=2)), desc="Combinaisons", leave=False):
            key = str((a, b))

            # ---- K: mass of the paired 'a - b' variant on each side of zero
            d, swapped = get_diff(tmp, a, b)
            if d is None:
                res[ind]["K"][key] = None
            else:
                k = K_pmf(d)
                if swapped:                       # d is 'b - a': roles are exchanged
                    k["K_A"], k["K_B"] = k["K_B"], k["K_A"]
                res[ind]["K"][key] = {k_: float(v) for k_, v in k.items()}



            # ---- K4: linear form is exact when totals are > 0; error bounded by P(total <= 0)
            if neg[a] <= EPS and neg[b] <= EPS:
                k4 = K4_pmf(None, to_assess_dict[a], to_assess_dict[b],
                            ind, df_open_scores, gamma=GAMMA, prep=prep)
                res[ind]["K4"][key] = {k_: float(v) for k_, v in k4.items()}
                res[ind]["K4"][key].update(neg_mass_A=neg[a], neg_mass_B=neg[b])
            else:
                res[ind]["K4"][key] = None
                print(ind)


            # # ---- K4: needs both totals > 0 for the linear form to be equivalent to the ratio
            # if min_score[a] > 0 and min_score[b] > 0:
            #     k4 = K4_pmf(None, to_assess_dict[a], to_assess_dict[b],
            #                 ind, df_open_scores, gamma=GAMMA, prep=prep)
            #     res[ind]["K4"][key] = {k_: float(v) for k_, v in k4.items()}
            # else:
            #     res[ind]["K4"][key] = None

    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"
    output_folder = f"{PROCESSED_DATA_DIR}/Discern/ponderees"

    with open(f"{output_folder}/{horodatage}_discern_indexes.json", "w") as f:
        json.dump(res, f)


if __name__ == "__main__":
    main()


