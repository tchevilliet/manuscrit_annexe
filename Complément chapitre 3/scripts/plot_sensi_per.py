from ipywidgets import Output
import polars as pl
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import bw2data as bd
from tqdm import tqdm 
import textwrap
from cmcrameri import cm
import glob
from itertools import combinations

FIGURES_DIR = "report/figures"


bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

queries = []
for filepath in glob.glob("data/processed/pu_results/PER_sensi/*.parquet"):
    # Extract the PER value from the filename
    filename = filepath.split("/")[-1]  # or use os.path.basename
    per_val = filename.split(".")[-2].split("_")[-1]
    # print(per_val,filename)
    # Scan each file and add the column
    q = pl.scan_parquet(filepath).with_columns(
        pl.lit(per_val).alias("PER")
    )
    queries.append(q)

to_graph = pl.concat(queries, how="vertical_relaxed").collect()
to_graph = to_graph.with_columns(
    pl.col("PER").cast(pl.Int32)
)

tmp = to_graph.filter(
    pl.col("iteration")<500,
    pl.col("scale") == 0
    )

# combi des programmes deux à deux
to_assess = list(tmp["demand"].unique())
dfs_combi = []
for prog1,prog2 in combinations(to_assess,r = 2) :
    diff_df = (
        to_graph.filter(pl.col("demand").is_in([prog1, prog2]))
        .group_by(["iteration", "indicator","scale","PER"])
        .agg(
            (
                pl.col("score").filter(pl.col("demand") == prog1).first()
                - pl.col("score").filter(pl.col("demand") == prog2).first()
            ).alias("score")
        )
        .with_columns(demand=pl.lit(f"{prog1} - {prog2}"))
    )
    dfs_combi.append(diff_df) 

df_scores = pl.concat([tmp,*dfs_combi],how="diagonal")



output_folder = f"{FIGURES_DIR}/comparaisons_pu/PER sensi"
# output_folder = f"{FIGURES_DIR}/archetypes_open_spaces"

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

cmap = cm.berlin

indicators = list(df_scores["indicator"].unique())

dict_indicators_units = {}
for ind in indicators :
    splitted = ind.split(" | ")
    key = tuple([e for e in splitted])
    m = bd.Method(key)
    dict_indicators_units[ind] = m.metadata["unit"]


demand_to_plot = sorted(list(df_scores["demand"].unique()))

demand_to_plot = [d for d in demand_to_plot if " - " in d]



PERs = sorted(list(df_scores["PER"].unique()))

# ####### BOXENPLOTS

hue_order = demand_to_plot[0]
palette = [list(cmap(np.linspace(0.1,0.9,len(hue_order))))[0]]


for ind in tqdm(indicators,desc = "indicateurs") :

    fig,ax = plt.subplots(figsize = (7,2))

    sns.boxenplot(
        df_scores.filter(
            pl.col("indicator") == ind,
            pl.col("demand") == "programme_1991 - programme_2002"
            # pl.col("demand") == "programme_2002"
            ),
            x = 'PER',
            y="score",
            # hue = "demand",
            palette=palette,
            # hue_order=hue_order,
            alpha = 0.8,
            # showfliers= False
        )

    safe_name = ind.replace(":", "-").replace("/", "-")
    safe_name = "-".join(safe_name.split("|")[1:])
    ax.axhline(0,linestyle = ":",color="black")

    label = f"{safe_name} \n {dict_indicators_units[ind]}"

    ax.set_ylabel(textwrap.fill(label, width=30))
    ax.set_xlabel("Période d'étude de référence")

    # ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1))

    plt.savefig(f"{output_folder}/pu_PER_sensi_prog1991-prog2002_{safe_name}.pdf",bbox_inches = 'tight')
    # plt.savefig(f"{output_folder}/pu_PER_sensi_prog2002_{safe_name}.pdf",bbox_inches = 'tight')
    plt.close()


