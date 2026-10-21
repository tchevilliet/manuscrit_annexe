from os import name
import math 
import bw2data as bd
import bw2io as bi
import bw2calc as bc

import polars as pl
import numpy as np

from archetypes_lcas import redefine_unc_scale

from tqdm import tqdm


def ua_ABC(nodes, indicators,n_mc,new_relativ_scale =0) :
    redefine_unc_scale(nodes, new_relativ_scale)
    demands = {node["code"]: {node.id: 1.0} for node in nodes}
    method_config = {"impact_categories": indicators}
    data_objs = bd.get_multilca_data_objs(demands, method_config)

    uncertainties_on = ["A","B","C","ABC"]
    selective_use_dict = {
        "A" : {
            "technosphere_matrix" : {"use_distributions" : True},
            "biosphere_matrix" : {"use_distributions" : False},
            "characterization_matrix" : {"use_distributions" : False}
            },
        "B" :{
            "technosphere_matrix" : {"use_distributions" : False},
            "biosphere_matrix" : {"use_distributions" : True},
            "characterization_matrix" : {"use_distributions" : False}
            },
        "C" :{
            "technosphere_matrix" : {"use_distributions" : False},
            "biosphere_matrix" : {"use_distributions" : False},
            "characterization_matrix" : {"use_distributions" : True}
            },
        "AB" :{
            "technosphere_matrix" : {"use_distributions" : True},
            "biosphere_matrix" : {"use_distributions" : True},
            "characterization_matrix" : {"use_distributions" : False}
            },
        "ABC" : {
            "technosphere_matrix" : {"use_distributions" : True},
            "biosphere_matrix" : {"use_distributions" : True},
            "characterization_matrix" : {"use_distributions" : True}
            },
        }

    for unc in tqdm(uncertainties_on,desc="Incertitudes sur ...") :
        mc = bc.MultiLCA(
            demands=demands,
            method_config=method_config,
            data_objs=data_objs,
            selective_use=selective_use_dict[unc],
            seed_override = 18
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

        df = pl.DataFrame(
            {
                "iteration": np.repeat(np.arange(n_mc), n_keys),
                "demand": np.tile(demand_labels, n_mc),
                "indicator": np.tile(indicator_labels, n_mc),
                "score": scores.ravel(),
            }
        ).with_columns(pl.lit(unc).alias("uncertainty_on"))

        df.write_parquet(f"data/processed/archetypes_results/UA/multilca_archetypes_n_MC_{n_mc}_uncertainty_on_{unc}_scale_{new_relativ_scale}.parquet")
    
    return None



def main():
    bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
    fgdb = bd.Database("archetypes_metabo")
    # renew(fgdb, PER=50)
    n_mc = 1000
    ef31 = [
        m for m in bd.methods
        if ("EF v3.1" in str(m)) and ("no LT" not in str(m)) and ("EN15804" not in str(m))
    ]
    arch_nodes = [a for a in fgdb if "arch" in str(a["code"])]

    ua_ABC(arch_nodes,ef31,n_mc)


if __name__ == "__main__" :
    main()