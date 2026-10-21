from os import name
import math 
import bw2data as bd
import bw2io as bi
import bw2calc as bc

import polars as pl
import numpy as np

from tqdm import tqdm


from archetypes_lcas import redefine_unc_scale, renew_change


def main():
    bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
    fgdb = bd.Database("archetypes_metabo")
    # 
    ef31 = [
        m for m in bd.methods
        if ("EF v3.1" in str(m)) and ("no LT" not in str(m)) and ("EN15804" not in str(m))
    ]

    scales = [0]
    n_mc = 500

    for PER in tqdm([70,90,110,130,150],desc = "PERs") :

        renew_change(fgdb, PER=PER)

        arch_nodes = [a for a in fgdb if "arch" in str(a["code"])]
        prog_nodes = [a for a in fgdb if "programme" in str(a["code"])]
        for s in tqdm(scales, desc="scales"):
            redefine_unc_scale(arch_nodes, s)

            demands = {node["code"]: {node.id: 1.0} for node in prog_nodes}
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
            ).with_columns(pl.lit(s).alias("scale"))

            df.write_parquet(f"data/processed/pu_results/PER_sensi/multilca_programs_n_MC_{n_mc}_scale_{s}_PER_{PER}.parquet")

if __name__ == "__main__" :
    main()

