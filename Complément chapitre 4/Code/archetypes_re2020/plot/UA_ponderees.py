import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd
import textwrap


from archetypes_re2020.data.remove_extreme_outliers import outliers
from archetypes_re2020.config import FIGURES_DIR

from cmcrameri import cm

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap=cm.berlin


output_folder ="/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/figures/Archetypes_ponderees/UA"

#### FICHIERS SOURCES


##  Avec variabilité
to_graph = pl.read_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Archetypes/distrib_arch_*.parquet")

indicators = list(to_graph["indicator"].unique())
dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


def pooled_pmf(result, variante, indicator):
    d = result.filter((pl.col("variante") == variante) & (pl.col("indicator") == indicator))
    n_it = d["iteration"].n_unique()
    return (d.group_by("score")
              .agg((pl.col("prob").sum() / n_it).alias("prob"))
              .sort("score"))




def pmf_to_samples(pmf, n=200_000, seed=0):
    rng = np.random.default_rng(seed)
    p = pmf["prob"].to_numpy()
    idx = rng.choice(pmf.height, size=n, p=p / p.sum())
    return pmf["score"].to_numpy()[idx]

var_to_plot =  to_graph["variante"].unique()



samples = pl.concat([
    pl.DataFrame({"variante": v,
                "indicateur" : ind ,
                "score": pmf_to_samples(pooled_pmf(to_graph, v,ind))})
    for v in var_to_plot for ind in indicators
]).with_columns(
    approche = pl.lit("Incertitudes d'arrière-plan + variabilité des bâtiments")
    ).rename(
        {"variante": "demand","indicateur":"indicator"}
        ).with_columns(
            pl.col("demand")
            .str.to_lowercase()
            .str.replace_all(" ", "_", literal=True)
            )
del to_graph

## Archetype moyenne pondérée
res_path = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-9-22-15h50_MC_runs/scores.parquet"

df_scores  = pl.read_parquet(res_path).with_columns(approche = pl.lit("Incertitudes d'arrière-plan uniquement"))

df = pl.concat([samples,df_scores.select(["demand","indicator","score","approche"])])

parts = df.partition_by("demand","indicator","approche")
tmp = pl.concat([outliers(part, "score") for part in parts])

df = tmp.filter(pl.col("score_extreme_outliers") == False)

stats_rows = [] 

hue_order = df["approche"].unique()
palette = list(cmap(np.linspace(0.1,0.9,len(hue_order))))
for arch in df["demand"].unique() : 
    for ind in df["indicator"].unique() : 
        tmp = df.filter(pl.col('demand')==arch,pl.col('indicator')==ind)

        #stats dans une table avant de tracer 
        stats = (
            tmp.group_by("approche")
               .agg(
                   pl.col("score").mean().alias("mean"),
                   pl.col("score").median().alias("median"),
                   pl.col("score").std().alias("std"),
                   pl.col("score").count().alias("n"),
               )
               .with_columns(
                   pl.lit(arch).alias("demand"),
                   pl.lit(ind).alias("indicator"),
               )
        )
        stats_rows.append(stats)

        fig,ax = plt.subplots(figsize = (7,2))
        sns.histplot(
            tmp, 
            x = "score",
            hue = "approche",
            hue_order=hue_order,
            palette = palette,
            # alpha = 0.8,
            stat = "probability",
            common_norm=False,
            element="step",
            ax=ax
            )
        safe_name = ind.replace(":", "-").replace("/", "-")
        safe_name = "-".join(safe_name.split("|")[1:])
        xlabel = "\n".join(textwrap.wrap(f"{safe_name} - {dict_indicators_units[ind]}", 100))
        ax.set_xlabel(xlabel)

        sns.move_legend(ax, loc="upper center", bbox_to_anchor=(0.5, -0.3),title=None,fontsize = 9)
        # ax.legend(loc="lower center",bbox_to_anchor = (0.5,0.5))
        plt.title(" ".join(arch.split("_")).capitalize(),fontsize = 9)
        # plt.show()
        plt.savefig(f"{output_folder}/{arch}_{safe_name}.pdf",dpi = 300, bbox_inches = 'tight')
        plt.close()

# summary_df = pl.concat(stats_rows)

# ### On calcule les ratios de variances

# var_wide = (
#     summary_df
#     .with_columns((pl.col("std") ** 2).alias("var"))
#     .pivot(values="var", index=["demand", "indicator"], on="approche")
# )

# # hue_order[0] and hue_order[1] are your two approche names
# a, b = hue_order[0], hue_order[1]

# var_wide = var_wide.with_columns(
#     (pl.col(a) / pl.col(b)).alias(f"var_ratio_{a}_over_{b}")
# )

# container = "Incertitudes d'arrière-plan + variabilité des bâtiments"
# contained = "Incertitudes d'arrière-plan uniquement"

# var_wide = (
#     summary_df
#     .with_columns((pl.col("std") ** 2).alias("var"))
#     .pivot(values="var", index=["demand", "indicator"], on="approche")
# )

# var_wide = var_wide.with_columns([
#     (pl.col(contained) / pl.col(container)).alias("var_retained_ratio"),
#     (1 - pl.col(contained) / pl.col(container)).alias("var_reduction_ratio"),
# ])


# summary_df = summary_df.join(var_wide, on=["demand", "indicator"], how="left")

# summary_df.write_excel(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/tables/UA/summary_stats_UA_arch.xlsx")

# from openpyxl import Workbook

# short_name = dict(pl.read_excel('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/short_indicateur.xlsx').iter_rows())

# for target_demand in summary_df["demand"].unique() :
#     demand_df = summary_df.filter(pl.col("demand") == target_demand)

#     indicators = demand_df["indicator"].unique(maintain_order=True).to_list()

#     rows = []
#     for ind in indicators:
#         row = demand_df.filter(pl.col("indicator") == ind)

#         contained_row = row.filter(pl.col("approche") == contained)
#         container_row = row.filter(pl.col("approche") == container)

#         mean_c, median_c, std_c = contained_row[0, "mean"], contained_row[0, "median"], contained_row[0, "std"]
#         mean_k, median_k, std_k = container_row[0, "mean"], container_row[0, "median"], container_row[0, "std"]
#         ratio = container_row[0, "var_retained_ratio"]  # same value on both rows post-join

#         rows.append([short_name[ind], mean_c, median_c, std_c, mean_k, median_k, std_k, ratio])

#     rows.sort(key=lambda r: r[0]) # on tri selon le nom de l'incateur
    
#     wb = Workbook()
#     ws = wb.active
#     ws.title = "summary"

#     ws.cell(row=1, column=2, value=contained)
#     ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=4)
#     ws.cell(row=1, column=5, value=container)
#     ws.merge_cells(start_row=1, start_column=5, end_row=1, end_column=7)

#     for col, label in zip([2, 3, 4, 5, 6, 7], ["mean", "median", "std", "mean", "median", "std"]):
#         ws.cell(row=2, column=col, value=label)
#     ws.cell(row=2, column=8, value="var_ratio")

#     for i, row in enumerate(rows, start=3):
#         for j, val in enumerate(row, start=1):
#             ws.cell(row=i, column=j, value=val)

#     wb.save(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/reports/tables/UA/{target_demand}_summary_table.xlsx")