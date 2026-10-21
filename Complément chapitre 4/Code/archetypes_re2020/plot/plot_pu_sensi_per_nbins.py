import os
import numpy as np
import polars as pl
import seaborn as sns
import matplotlib.pyplot as plt
from cmcrameri import cm
import bw2data as bd
from tqdm import tqdm
from archetypes_re2020.compute.pu.compare_pu_weighted import N_BINS
from archetypes_re2020.config import PROCESSED_DATA_DIR

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")


INDICATORS = None                     
VARIANTS = [
    # "1991",
    # "1997",
    # "2002",
    # "2009",
    "1991 - 1997",
    "1991 - 2002",
    # "1991 - 2009",
    "1997 - 2002",
    # "1997 - 2009",
    # "2002 - 2009"
]    

PERS = [50, 60, 70, 80, 90, 100]      
FIXED_N_BINS = 2000

N_BINS_LIST = range(500,5001,500) 
# N_BINS_LIST = None                  
FIXED_PER = 50

N_SAMPLES = 5000                      
SEED = 0
 
OUTPUT_FOLDER = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/figures/Comparaisons_pu/sensitivity/ponderees"


plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin

palette = list(cmap(np.linspace(0.1,0.9,len(VARIANTS))))




def load_pooled_pmf(path, variants):
    """Charge un fichier de résultats et renvoie la pmf poolée (moyenne sur itérations) par variante."""
    df = pl.read_parquet(path).filter(pl.col("variante").is_in(variants))
    n_it = df.group_by("variante").agg(pl.col("iteration").n_unique().alias("n_it"))
    df = df.join(n_it, on="variante")
    return (
        df.group_by(["variante", "score"])
        .agg((pl.col("prob").sum() / pl.col("n_it").first()).alias("prob"))
        .sort("score")
    )


def resample_pmf(pmf, variants, n_samples, rng):
    """Tire n_samples valeurs de score par variante, pondérées par la pmf, pour nourrir le boxenplot."""
    rows = []
    for variante in variants:
        sub = pmf.filter(pl.col("variante") == variante)
        s, p = sub["score"].to_numpy(), sub["prob"].to_numpy()
        p = p / p.sum()
        draws = rng.choice(s, size=n_samples, p=p)
        rows.append(pl.DataFrame({"variante": variante, "score": draws}))
    return pl.concat(rows)


def plot_sweep(values, sweep_label, path_fmt,path,unit,hue_order=VARIANTS):
    rng = np.random.default_rng(SEED)
    frames = []
    for val in values:
        pmf = load_pooled_pmf(path_fmt(val), VARIANTS)
        sampled = resample_pmf(pmf, VARIANTS, N_SAMPLES, rng)
        frames.append(sampled.with_columns(pl.lit(str(val)).alias(sweep_label)))
    long_df = pl.concat(frames).to_pandas()
 
    fig, ax = plt.subplots(figsize=(7, 2))
    sns.boxenplot(
        data=long_df,
        x=sweep_label,
        y="score",
        hue="variante",
        hue_order=hue_order,
        palette=palette,
        ax=ax
        )
    xlabel = "Résolution" if sweep_label == "n_bins" else "PER"
    ax.set_ylabel(unit)
    ax.set_xlabel(xlabel)
    ax.axhline(0,linestyle = ":",color="black")
    ax.legend(loc = "upper left", bbox_to_anchor = (1.01,0.99))
    # ax.set_title(title)
    plt.savefig(path,dpi = 300, bbox_inches ='tight')
    # plt.tight_layout()
    # plt.show()
    plt.close()
 


def per_path(per, indicator):
    return f"{PROCESSED_DATA_DIR}/Comparaisons/ponderees/n_bins_{FIXED_N_BINS}/zac_tous_ind_{per}_{indicator}.parquet"


def n_bins_path(n_bins, indicator):
    return f"{PROCESSED_DATA_DIR}/Comparaisons/ponderees/n_bins_{n_bins}/zac_tous_ind_{FIXED_PER}_{indicator}.parquet"


def discover_indicators(per, n_bins):
    """Devine les ind_name disponibles en listant un dossier de sortie, en retirant le préfixe/suffixe du nom de fichier."""
    folder = f"{PROCESSED_DATA_DIR}/Comparaisons/ponderees/n_bins_{n_bins}"
    prefix, suffix = f"zac_tous_ind_{per}_", ".parquet"
    return sorted(
        f[len(prefix):-len(suffix)]
        for f in os.listdir(folder)
        if f.startswith(prefix) and f.endswith(suffix)
    )


if __name__ == "__main__":
    ref_per = PERS[0] if PERS else FIXED_PER
    ref_n_bins = FIXED_N_BINS if PERS else N_BINS_LIST[0]
    indicators = INDICATORS or discover_indicators(ref_per, ref_n_bins)

    dict_indicators_units = {}
    # tmp  =[]
    for ind in tqdm(indicators) :
        splitted = ind.replace("metals-minerals","metals/minerals").split("_")
        splitted = ['ecoinvent-3.11','EF v3.1']+splitted
        key = tuple([e for e in splitted])
        # tmp.append(key)
        m = bd.Method(key)
        dict_indicators_units[ind] = m.metadata["unit"]

    for indicator in tqdm(indicators):
        if PERS:
            plot_sweep(PERS, "PER", lambda per: per_path(per, indicator),
                       f"{OUTPUT_FOLDER}/sensi_PER_{VARIANTS}_n_bins_{FIXED_N_BINS}_{indicator}.pdf",
                       dict_indicators_units[indicator],
                       )

        if N_BINS_LIST:
            plot_sweep(N_BINS_LIST, "n_bins", lambda nb: n_bins_path(nb, indicator),
                       f"{OUTPUT_FOLDER}/sensi_n_bins_{VARIANTS}_per_{FIXED_PER}_{indicator}.pdf",
                       dict_indicators_units[indicator],
                       )