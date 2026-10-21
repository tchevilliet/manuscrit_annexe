"""
Compare, pour une variante de programme et pour chaque indicateur, la distribution
des scores avec poids (surfaces) et sans poids (poids uniforme = 1 pour tous les
bâtiments, y compris ceux de poids nul dans la version pondérée).

Un histogramme par indicateur (pondéré vs non pondéré) est enregistré en PNG.
"""
from itertools import combinations, permutations
import os

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import polars as pl
from tqdm import tqdm

import textwrap
from cmcrameri import cm
import bw2data as bd

from archetypes_re2020.config import PROCESSED_DATA_DIR
from archetypes_re2020.data.remove_extreme_outliers import outliers

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin

COLORS = [cmap(0.1), cmap(0.9)]

#### CONFIG

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")



PER = 50
N_BINS = 2000  # résolution de la convolution
N_HIST_BINS = 100  # nombre de classes des histogrammes tracés
VARIANTE = "1991"

Hbs_folder = f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Hb/260827-Hb_per/{PER}"
df_open_scores = pl.read_parquet(
    f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-25-23h5_MC_runs/scores_{PER}.parquet"
)
OUTPUT_DIR = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

indicators = list(df_open_scores["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]




programmes = {
    "1991" : {
    "individual_housing" : 0,
    "collective_housing" : 520000,
    "office_building" : 900000,
    # "industrial_building" : 165000,
    "education_building" : 582000,
    "roads" : 100000,
    "vegetation" : 53000,
    },
    "1997" : {
    "individual_housing" : 0,
    "collective_housing" : 520000,
    "office_building" : 900000,
    # "industrial_building" : 150000,
    "education_building" : 684000,
    "roads" : 100000,
    "vegetation" : 80600,
    },
    "2002" : {
    "individual_housing" : 0,
    "collective_housing" : 430000,
    "office_building" : 700000,
    # "industrial_building" : 150000,
    "education_building" : 920000,
    "roads" : 100000,
    "vegetation" : 100000,
    },
    "2009" : {
    "individual_housing" : 0,
    "collective_housing" : 585000,
    "office_building" : 745000,
    # "industrial_building" : 150000,
    "education_building" : 920000,
    "roads" : 100000,
    "vegetation" : 100000,
    },
    "Maison individuelle ou accolée" : {
    "individual_housing" : 1,
    "collective_housing" : 0,
    "office_building" : 0,
    # "industrial_building" : 165000,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    },
    "Logement collectif" : {
    "individual_housing" : 0,
    "collective_housing" : 1,
    "office_building" : 0,
    # "industrial_building" : 165000,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    },
    "Bureau" : {
    "individual_housing" : 0,
    "collective_housing" : 0,
    "office_building" : 1,
    # "industrial_building" : 165000,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    }
    }
     
map_arch = {
    "individual_housing": "Maison individuelle ou accolée",
    "collective_housing": "Logement collectif",
    "office_building": "Bureau",
    "education_building": "Bureau",
    "roads": "roads_m2_per",
    "vegetation": "vegetation_m2_per",
}
OPEN_DEMANDS = {"roads_m2_per", "vegetation_m2_per"}


#### COMBINAISON DES PROGRAMMES

to_assess_dict = dict(programmes)
for prog1, prog2 in combinations(programmes.keys(), r=2):
    to_assess_dict[f"{prog1} - {prog2}"] = {
        k: programmes[prog1][k] - programmes[prog2][k] for k in programmes[prog1]
    }

#### POIDS DES BATIMENTS POUR CHAQUE ARCHETYPE

arch_db = bd.Database("2026-8-13-16h52_archetypes_RE2020_BB")
dict_w = {}
for a in tqdm(arch_db, desc="Poids des bâtiments"):
    phi = list(a.production())[0]["amount"]
    dict_w |= {e["input"][1]: e["amount"] / phi for e in a.technosphere()}


#### PREPARATION DES DONNEES


def build_Hb_filtered(parquet_file, dict_w):
    tmp = pl.read_parquet(parquet_file)
    tmp = tmp.with_columns(
        poids=pl.col("batiment").replace_strict(dict_w, default=0.0, return_dtype=pl.Float64)
    ).drop_nulls("usage")
    parts = tmp.partition_by("usage")
    tmp = pl.concat([outliers(part, "score") for part in parts])
    return tmp.filter(pl.col("score_extreme_outliers") == False)  # noqa: E712


def prepare_groups(Hb):
    groups = {}
    for (it, u), g in Hb.partition_by(["iteration", "usage"], as_dict=True).items():
        w = g["poids"].to_numpy()
        if w.sum() > 0:
            groups[(it, u)] = (g["score"].to_numpy(), w / w.sum())
    return groups


def f_tilde_from_var(var_dict, allowed):
    f_tilde = {}
    for k, v in var_dict.items():
        key = map_arch[k]
        if key in allowed and v != 0:
            f_tilde[key] = f_tilde.get(key, 0) + v
    return {k: v for k, v in f_tilde.items() if v != 0}


def open_by_iter(open_scores, var_dict, indicator):
    f_tilde = f_tilde_from_var(var_dict, OPEN_DEMANDS)
    if not f_tilde:
        return {}
    tmp = (
        open_scores.filter(
            (pl.col("indicator") == indicator) & pl.col("demand").is_in(list(f_tilde))
        )
        .with_columns(
            score=pl.col("score")
            * pl.col("demand").replace_strict(f_tilde, return_dtype=pl.Float64)
        )
        .group_by("iteration")
        .agg(pl.col("score").sum())
    )
    return dict(zip(tmp["iteration"].to_list(), tmp["score"].to_list()))


def iteration_distributions(groups, usage_ranges, f_tilde, open_it, indicator, n_bins=N_BINS):
    iterations = sorted({it for it, _ in groups})
    iterations = [it for it in iterations if all((it, u) in groups for u in f_tilde)]

    if not f_tilde:
        return pl.DataFrame(
            {
                "iteration": iterations,
                "score": [open_it.get(it, 0.0) for it in iterations],
                "prob": [1.0] * len(iterations),
            }
        )

    ov = list(open_it.values()) or [0.0]
    lo, hi = min(ov), max(ov)
    for u, v in f_tilde.items():
        smin, smax = usage_ranges[u]
        lo += min(v * smin, v * smax)
        hi += max(v * smin, v * smax)
    dx = (hi - lo) / n_bins if hi > lo else 1.0

    frames = []
    for it in iterations:
        kmin_tot = int(round(open_it.get(it, 0.0) / dx))
        pmf_tot = np.array([1.0])
        for u, v in f_tilde.items():
            s, w = groups[(it, u)]
            k = np.round(s * v / dx).astype(np.int64)
            kmin = int(k.min())
            pmf_tot = np.convolve(pmf_tot, np.bincount(k - kmin, weights=w))
            kmin_tot += kmin
        values = (kmin_tot + np.arange(len(pmf_tot))) * dx
        keep = pmf_tot > 0
        frames.append(
            pl.DataFrame({"iteration": it, "score": values[keep], "prob": pmf_tot[keep]})
        )
    return pl.concat(frames)


#### VARIANTE POUR UN Hb DONNE


def run_variant(Hb, var_dict, indicator):
    groups = prepare_groups(Hb)
    ranges = Hb.group_by("usage").agg(
        mn=pl.col("score").quantile(0.001), mx=pl.col("score").quantile(0.999)
    )
    usage_ranges = {r["usage"]: (r["mn"], r["mx"]) for r in ranges.iter_rows(named=True)}
    f_tilde = f_tilde_from_var(var_dict, set(usage_ranges))
    open_it = open_by_iter(df_open_scores, var_dict, indicator)
    return iteration_distributions(groups, usage_ranges, f_tilde, open_it, indicator)


def pooled_pmf(res):
    n_it = res["iteration"].n_unique()
    return (
        res.group_by("score")
        .agg((pl.col("prob").sum() / n_it).alias("prob"))
        .sort("score")
    )


def pooled_stats(pmf):
    s, p = pmf["score"].to_numpy(), pmf["prob"].to_numpy()
    m = (s * p).sum()
    return m, (p * (s - m) ** 2).sum()



def main():
    summary = []
    for file in tqdm(sorted(os.listdir(Hbs_folder)), desc="Indicateurs"):
        full = os.path.join(Hbs_folder, file)
        if not os.path.isfile(full):
            continue

        Hb = build_Hb_filtered(full, dict_w)
        indicator = Hb["indicator"].unique()[0]
        ind_name = "_".join(file.split("_")[1:-1])

        # A : pondéré par surface ; B : poids uniforme, tous bâtiments (poids nuls inclus)
        Hb_A = Hb
        Hb_B = Hb.with_columns(poids=pl.lit(1.0))

        pmfs = {
            "Pondéré": pooled_pmf(run_variant(Hb_A, to_assess_dict[VARIANTE], indicator)),
            "Non pondéré": pooled_pmf(run_variant(Hb_B, to_assess_dict[VARIANTE], indicator)),
        }

        # classes communes aux deux versions
        all_s = np.concatenate([p["score"].to_numpy() for p in pmfs.values()])
        edges = np.linspace(all_s.min(), all_s.max(), N_HIST_BINS + 1)

        fig, ax = plt.subplots(figsize=(7, 3))
        for (name, pmf), color in zip(pmfs.items(), COLORS):
            # m, v = pooled_stats(pmf)
            # summary.append({"indicateur": ind_name, "version": name, "moyenne": m, "variance": v})
            sns.histplot(
                x=pmf["score"].to_numpy(),
                weights=pmf["prob"].to_numpy(),
                bins=edges.tolist(),   # liste, pas ndarray
                stat="probability",
                element="step",
                color=color,
                alpha=0.3,
                label=name,
                ax=ax,
            )
            # ax.axvline(m, color=color, linestyle="--", linewidth=1)
        
        ax.axvline(0,linestyle = ":",color="black")

        safe_name = indicator.replace(":", "-").replace("/", "-")
        safe_name = "-".join(safe_name.split("|")[1:])
        xlabel = "\n".join(textwrap.wrap(f"{safe_name} - {dict_indicators_units[ind]}", 70))
        ax.set_xlabel(xlabel)

        ax.legend(loc = "upper left",bbox_to_anchor = (1.01,0.99))
        fig.tight_layout()
        fig.savefig(f"{OUTPUT_DIR}/figures/Comparaisons_pu/sensitivity/a la ponderation/hist_{ind_name}.pdf", dpi=300)
        plt.close(fig)
        
    # pl.DataFrame(summary).write_csv(f"{OUTPUT_DIR}/tables/comparaison pu/stats_ponderation.csv")
    # print(pl.DataFrame(summary))

if __name__ == "__main__":
    main()
