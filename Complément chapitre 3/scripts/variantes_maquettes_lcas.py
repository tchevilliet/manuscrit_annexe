import bw2data as bd
import bw2calc as bc
import numpy as np
import polars as pl

from tqdm import tqdm

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
fgdb = bd.Database("archetypes_metabo")

n_mc = 1000

ef31 = [m for m in bd.methods if ("EF v3.1" in str(m)) and ("no LT" not in str(m)) and ("EN15804" not in str(m))]

programmes = {
    "Castro" : {
    "individual_housing" : 0,
    "collective_housing" : 59095,
    "office_building" : 91598,
    # "industrial_building" : 165000,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    },
    "Huet" : {
    "individual_housing" : 0,
    "collective_housing" : 76580,
    "office_building" : 103759,
    # "industrial_building" : 150000,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    },
    "Portzamparc" : {
    "individual_housing" : 0,
    "collective_housing" : 63312,
    "office_building" : 155191,
    # "industrial_building" : 150000,
    "education_building" : 0,
    "roads" : 0,
    "vegetation" : 0,
    },
    }

nodes = { k : fgdb.search(k)[0] for k in programmes["Castro"].keys()}

demands = {key_prog : {nodes[k].id : v for k,v in dict_prog.items()} for key_prog, dict_prog in programmes.items()}
method_config = {"impact_categories": ef31}
data_objs = bd.get_multilca_data_objs(demands, method_config)

mc = bc.MultiLCA(
    demands=demands,
    method_config=method_config,
    data_objs=data_objs,
    use_distributions=True,
)
mc.lci()
mc.lcia()


keys = list(mc.scores.keys())
n_keys = len(keys)

demand_labels = np.array([k[1] for k in keys])
indicator_labels = np.array([" | ".join(k[0]) for k in keys])

scores = np.empty((n_mc, n_keys), dtype=np.float64)

for i in tqdm(range(n_mc), desc="mc iterations", leave=False):
    next(mc)
    scores[i, :] = np.fromiter(mc.scores.values(), dtype=np.float64, count=n_keys)

# print(n_mc)
# print(len(np.tile(demand_labels, n_mc)))
df = pl.DataFrame(
    {
        "iteration": np.repeat(np.arange(n_mc), n_keys),
        "demand": np.tile(demand_labels, n_mc),
        "indicator": np.tile(indicator_labels, n_mc),
        "score": scores.ravel(),
    }
)

df.write_parquet(f"data/processed/pu_results/multilca_variantes_maquettes_n_MC_{n_mc}.parquet")




