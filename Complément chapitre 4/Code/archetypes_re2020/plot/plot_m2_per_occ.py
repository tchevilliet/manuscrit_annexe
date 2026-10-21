import polars as pl
import seaborn as sns
import matplotlib.pyplot as plt
from cmcrameri import cm
import numpy as np
import bw2data as bd
from archetypes_re2020.config import FIGURES_DIR


cmap = cm.berlin


bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})



df = pl.read_csv("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/external/nb_occ_par_m2.csv", schema_overrides={"value": pl.Float64})


df_gwp = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Archetypes/").filter(pl.col("variante").str.contains_any(["individuelle","collectif"]))

result = []
for age in df["categorie_age"].unique() :
    tmp = {
    "Maison individuelle ou accolée" : df.filter(pl.col("categorie_age")==age,pl.col("type")=="Individuel")["value"][0],
    "Logement collectif" : df.filter(pl.col("categorie_age")==age,pl.col("type")=="Collectif")["value"][0]
    }
    result.append(df_gwp.with_columns(
                pl.col("score") * pl.col("variante").replace_strict(tmp).alias("score"),
                pl.lit(age).alias("Classe d'âge")
                ))



res = pl.concat(result)

var_to_plot = res["variante"].unique()
indicators = res["indicator"].unique()
classes = res["Classe d'âge"].unique()


dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]





def pooled_pmf(result, variante, indicator,classe):
    d = result.filter((pl.col("variante") == variante) & (pl.col("indicator") == indicator)& (pl.col("Classe d'âge") == classe))
    n_it = d["iteration"].n_unique()
    return (d.group_by("score")
              .agg((pl.col("prob").sum() / n_it).alias("prob"))
              .sort("score"))

 ####### BOXENPLOT EN TIRANT SUR PMF

def pmf_to_samples(pmf, n=10_000, seed=0):
    rng = np.random.default_rng(seed)
    p = pmf["prob"].to_numpy()
    idx = rng.choice(pmf.height, size=n, p=p / p.sum())
    return pmf["score"].to_numpy()[idx]



hue_order = var_to_plot
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))
y_order = [
         'moins de 30 ans',
         '30 à 39 ans',
         '40 à 49 ans',
         '50 à 64 ans',
         '65 à 74 ans',
         'Plus de 75 ans'
         ]


for ind in indicators :

    samples = pl.concat([
        pl.DataFrame({"variante": v,
                    "score": pmf_to_samples(pooled_pmf(res,v,ind,c)),
                    "Classe d'âge" : c})
        for v in var_to_plot
        for c in classes
    ]).to_pandas()


    fig,ax = plt.subplots(figsize = (7,3))
    g = sns.boxenplot(
        data = samples,
        x="score",
        y = "Classe d'âge",
        hue = "variante",
        order = y_order,
        palette=palette,
        # showfliers= False
        alpha = 0.8
        )

    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    # ax.axvline(0,linestyle = ":",color="black")
    ax.set_xlabel(f"{safe_name} - {dict_indicators_units[ind]}")
    sns.move_legend(g,loc = 'upper left',bbox_to_anchor = (1,1),title = None)
    plt.savefig(f"{FIGURES_DIR}/Comparaisons_pu/ponderees/boxen_nb_occ_{safe_name}.pdf",dpi = 300,bbox_inches = 'tight')
    plt.close()

# sns.stripplot(
    # data=df, x="type", y="value", hue="type",
    # dodge=True, alpha=.5, legend=False,
# )
# sns.pointplot(
     # data=df, x="type", y="value", hue="type",
    # dodge=.4, linestyle="none", errorbar=None,
    # marker="_", markersize=20, markeredgewidth=3,
# )
# 
# plt.show()

