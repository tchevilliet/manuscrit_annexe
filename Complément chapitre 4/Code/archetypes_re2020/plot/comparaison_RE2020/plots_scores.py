import polars as pl
import polars.selectors as cs
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from cmcrameri import cm

from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.archetypes.buildings_based_archetypes_db import load_parquet_data, INPUT_PATH
from archetypes_re2020.data.source import INPUT_PATHS

output_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/figures/comparaison_calcul_re2020"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin


df_re2020 = load_parquet_data(INPUT_PATH)

df_bat_model = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/bat_composant_only_dynRE2020.parquet")

df_buildings = pl.read_csv(source=INPUT_PATHS["BUILDINGS"], ignore_errors=True)

dict_usage = dict(
    df_buildings.select(
        pl.concat_str(['projet_id', 'batiment_index'], separator="_").alias("key"),
        pl.col('usage_principal_1_txt'),
    ).rows()
)

df_bat_model=df_bat_model.with_columns(usage=pl.col("code").replace_strict(dict_usage, default="unknown"))

df_ic_composant = df_buildings.select(
    pl.concat_str(['projet_id', 'batiment_index'], separator="_").alias("code"),
    "ic_composant",
    "usage_principal_1_txt"
    ).rename({"usage_principal_1_txt" : "usage","ic_composant" : "value"}).with_columns(pl.lit("RE2020").alias("indicateur"))

df_model_norm =df_bat_model.select(
    "usage",
    cs.contains("code") | cs.contains("EN15804")
    ).with_columns(pl.lit("EN15804 +A2").alias("indicateur"))

df_model_ef = df_bat_model.select(
    "usage",
    cs.contains("code") | (cs.contains("EF") & ~cs.contains("EN15804"))
    ).with_columns(pl.lit("EF v3.1").alias("indicateur"))

df_model_norm = df_model_norm.rename({'ecoinvent-3.11|EN15804+A2 - Core impact categories and indicators|climate change: total (EF v3.1 - IPCC 2021)|global warming potential (GWP100)' : "value"})
df_model_ef = df_model_ef.rename({'ecoinvent-3.11|EF v3.1|climate change|global warming potential (GWP100)' : "value"})

# df_ic_composant = outliers(df_ic_composant,value_col="value")
# df_model_norm = outliers(df_model_norm,value_col="value")
# df_model_ef = outliers(df_model_ef,value_col="value")

res = pl.concat(
    [df_ic_composant.select(df_model_ef.columns),
    df_model_ef,
    df_model_norm.select(df_model_ef.columns)]
    ).drop_nulls()



res = (
    res.pivot(on="indicateur", index=["code","usage"], values="value")
    .with_columns(
        (pl.col("EF v3.1") - pl.col("RE2020")).alias("EF v3.1 - RE2020"),
        (pl.col("EN15804 +A2") - pl.col("RE2020")).alias("EN15804 +A2 - RE2020"),
    )
    ).unpivot(
        on=["EF v3.1", "EN15804 +A2", "RE2020","EF v3.1 - RE2020","EN15804 +A2 - RE2020"],
        index=["code","usage"],
        variable_name="indicateur",
        value_name="value",
    ).drop_nulls().filter(pl.col("usage")!="unknown")


usages = sorted(res["usage"].unique())

hue_order = sorted(res["indicateur"].unique())
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))


parts = res.partition_by("usage",'indicateur')
res = pl.concat([outliers(part, "value") for part in parts])
res = res.filter(pl.col("value_extreme_outliers") == False)



#### TRACE des distribs

for u in usages : 

    fig,ax = plt.subplots(figsize = (7,2)) 

    sns.boxenplot(
        data = res.filter(
            pl.col("usage")==u,
            ~pl.col("indicateur").str.contains(" - ")
            ),
        x = "value",
        y = "indicateur",
        hue = 'indicateur',
        palette=palette,
        alpha = 0.8
    )
    ax.set_xlabel( "Indicateur de de changement climatique \n(GWP100)")
    ax.set_ylabel( "Méthode de calcul")

    ax.set_title(u)

    plt.savefig(f"{output_folder}/distrib_scores_{u}.pdf",dpi=300, bbox_inches ='tight')

#### TRACE des différences
for u in usages : 

    fig,ax = plt.subplots(figsize = (7,2)) 

    sns.boxenplot(
        data = res.filter(
            pl.col("usage")==u,
            pl.col("indicateur").str.contains(" - ")
            ),
        x = "value",
        y = "indicateur",
        hue = 'indicateur',
        palette=palette,
        alpha = 0.8
    )
    ax.set_xlabel( "Indicateur de de changement climatique \n (GWP100)")
    ax.set_ylabel( "Méthode de calcul")
    ax.axvline(x = 0,linestyle = ":",color="black")
    ax.set_title(u)

    plt.savefig(f"{output_folder}/distrib_differences_{u}.pdf",dpi=300, bbox_inches ='tight')
