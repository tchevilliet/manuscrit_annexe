import bw2data as bd
import bw2calc as bc
import bw2io as bi
import bw2analyzer as ba
import pandas as pd
from cmcrameri import cm
import matplotlib.pyplot as plt
from tqdm import tqdm
import numpy as np
import polars as pl


plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
    "savefig.bbox": "tight",
    "savefig.format": "pdf",
})

cmap = cm.berlin

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
fgdb = bd.Database("archetypes_metabo")
 
ef31 = [
    m for m in bd.methods
    if ("EF v3.1" in str(m)) and ("no LT" not in str(m)) and ("EN15804" not in str(m))
]
 
nodes = [n for n in fgdb if "arch" in n["code"]]
 
OUTPUT_FOLDER = "report/figures/contributions_archetypes"
CUTOFF = 0.03
 
OTHER_COLOR = "#999999"

short_name = dict(pl.read_excel('/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/short_indicateur.xlsx').iter_rows())

dict_title = {
    "arch_industrial" : "Industrie",
    "arch_collective_housing" : "Logement collectif",
    "arch_individual_housing" : "Maison individuelle",
    "arch_education" : "Enseignement",
    "arch_office" : "Bureau",
    "arch_roads" : "Route",
    "arch_vegetation" : "Espace végétalisé"
}

def make_alt_name(method: tuple) -> str:
    joined = " | ".join(str(part) for part in method)
    return joined
 
 
alt_name_dict = {method: make_alt_name(method) for method in ef31}


def apply_cutoff(series: pd.Series, cutoff: float, normalize: bool = True) -> pd.Series:
    """Fold contributors below `cutoff` (fraction of total |score|) into
    "Other", then optionally normalize so the (signed) total equals 1."""
    abs_total = series.abs().sum()
    if abs_total == 0:
        return series
    # keep the biggest contributors first, so "Other" ends up last in the legend
    series = series.reindex(series.abs().sort_values(ascending=False).index)
    small_mask = (series.abs() / abs_total) < cutoff
    if small_mask.any():
        kept = series[~small_mask]
        grouped_other = series[small_mask].sum()
        if grouped_other != 0:
            kept["Other"] = grouped_other
        series = kept
    if normalize:
        net_total = series.sum()
        if net_total != 0:
            series = series / net_total
    return series
 

 
def colors_for(series: pd.Series,translate_cols_dict):
    tmp = translate_cols_dict["Other"]
    labels = list(series.index) if hasattr(series, "index") else list(series)
    n_named = len(labels) - (1 if tmp in labels else 0)
    palette = cmap(np.linspace(0.05, 0.95, max(n_named, 1)))
    colors = []
    i = 0
    for label in labels:
        if label == tmp:
            colors.append(OTHER_COLOR)
        else:
            colors.append(palette[i])
            i += 1
    return colors

node_first_tier = {
    node: {p.input: p.amount for p in node.technosphere()} for node in nodes
}


lca = bc.LCA(demand={nodes[0]: 1.0}, method=ef31[0])
lca.lci()
lca.lcia()
 
 
for node in tqdm(nodes, desc="Archetypes"):
    first_tier_processes = node_first_tier[node]
 
    # Solve the inventory once per first-tier process (indicator-independent)
    process_inventories = {}
    for p, a in tqdm(
        first_tier_processes.items(), desc=f"LCI ({node['name']})", leave=False
    ):
        lca.lci({p.id: a})
        process_inventories[p] = lca.inventory.copy()
 
    # One row per indicator (normalized, cutoff-grouped), collected here and
    # plotted together as a single figure for this node.
    rows = {}
    for indicator in tqdm(
        ef31, desc=f"Indicators ({node['name']})", leave=False
    ):
        lca.switch_method(indicator)
 
        contrib = {}
        for p in first_tier_processes:
            lca.inventory = process_inventories[p]
            lca.lcia_calculation()
            contrib[p["name"]] = lca.score
 
        series = pd.Series(contrib)
        series = apply_cutoff(series, CUTOFF, normalize=True)
        rows[short_name[alt_name_dict[indicator]]] = series
 
    # Assemble into one DataFrame: index = indicators, columns = processes.
    # Order columns by overall importance so colors/legend order stay stable
    # across nodes, with "Other" always last.
    df = pd.DataFrame(rows).T.fillna(0.0)
    df = df.sort_index()
    named_cols = [c for c in df.columns if c != "Other"]
    named_cols = sorted(named_cols, key=lambda c: -df[c].abs().sum())
    ordered_cols = named_cols + (["Other"] if "Other" in df.columns else [])
    df = df[ordered_cols]

    translate_cols = dict(pl.read_excel('data/external/materials_categories.xlsx').iter_rows())
    df = df.rename(columns=translate_cols)
 
    colors = colors_for(df.columns,translate_cols)
 
    fig, ax = plt.subplots(figsize=(max(5, 0.4 * len(df)), 3.5))
    df.plot(kind="bar", stacked=True, ax=ax, color=colors,alpha = 0.9)
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.set_title(dict_title[node["code"]])
    ax.set_ylabel("Contribution à l'indicateur")
    ax.axhline(0, color="black", linewidth=0.8)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
 
    plt.savefig(f"{OUTPUT_FOLDER}/{node['code']}_all_indicators.pdf")
    # plt.show()
    plt.close(fig)
 


# for node in [n for n in fgdb if "arch" in n["code"]] :
#     first_tier_processes ={p.input : p.amount for p in list(node.technosphere())}
#     contrib_first_processes = {}
#     for p,a in first_tier_processes.items() :
#         lca = bc.LCA(demand={p : a},method=indicator)
#         lca.lci()
#         lca.lcia()
#         contrib_first_processes[p['name']] = lca.score

#     df_first_processes = pd.DataFrame(contrib_first_processes,index=[str(indicator[-1])])
#     df_first_processes.plot(kind='bar', stacked=True)
#     plt.legend(loc='center left', bbox_to_anchor=(1.0, 0.5))
#     plt.xticks(rotation=0, ha='center');

#     plt.show()