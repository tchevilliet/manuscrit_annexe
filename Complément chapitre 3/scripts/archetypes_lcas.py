from os import name
import math 
import bw2data as bd
import bw2io as bi
import bw2calc as bc

import polars as pl
import numpy as np

from tqdm import tqdm



def redefine_unc_scale(list_nodes, new_relative_scale, unc_type_to_change = 3) :
    edges = [
        exc
        for node in list_nodes
        for exc in node.exchanges()
        if exc.get("uncertainty type", 0) == unc_type_to_change
    ]
    
    for exc in tqdm(edges, desc="edges"):

        loc = exc.get("loc")
        if loc is None:
            print(f" Warning : {exc} distrib normale sans loc !")
            continue
        factor = new_relative_scale if new_relative_scale != 0 else 1E-12
        exc["scale"] = np.abs(loc) * factor
        exc.save()
    # if new_relativ_scale ==0 :
    #     for node in tqdm(list_nodes,desc = "noeuds") :
    #         for exc in tqdm(
    #             [e for e in node.exchanges() if e["uncertainty type"]==unc_type_to_change],
    #             desc = "edges",
    #             leave= False
    #          ) :
    #             exc["uncertainty type"] = 0
    #             exc.save()
    # else :
    #     for node in tqdm(list_nodes,desc = "noeuds") :
    #         for exc in tqdm(
    #             [e for e in node.exchanges() if e["uncertainty type"]==unc_type_to_change],
    #             desc = "edges",
    #             leave= False
    #          ) :
    #             loc = exc["loc"]
    #             exc["scale"] = loc*new_relativ_scale
    #             exc.save()

def renew_init(db, PER=50):
    for node in db:
        if "dve" not in list(node.as_dict().keys()):
            continue

        dve = node["dve"]

        create_b_edge = dve < PER
        factor_b = math.ceil(PER / dve) - 1 if create_b_edge else 0

        edges = list(node.technosphere())
        

        for exc in edges:
            input_tuple = exc["input"]
            input_node= bd.get_node(database = input_tuple[0],code = input_tuple[1])
            input_name = input_node["name"].lower()
            step_default = "C" if (
                "waste" in input_name 
                or "treatment" in input_name
                or "used" in input_name
                or "scrap" in input_name
                ) else "A"
            exc["step"] = step_default

            if create_b_edge and step_default == "C":
                exc["amount"] = exc["amount"]*(1+ factor_b)
                exc.save()
                continue
            elif create_b_edge and step_default == "A":
                exc.save()
                attributes = exc.as_dict()
                attributes["amount"] = attributes["amount"]*factor_b
                attributes["step"] = "B"
                new_exc = node.new_edge(**attributes)
                new_exc.save()
            else :
                exc.save()

def renew_change(db,PER) : 
    for node in tqdm(db,desc="noeuds"):
        if "dve" not in list(node.as_dict().keys()):
            continue

        dve = node["dve"]
        create_b_edge = dve < PER
        factor_b = math.ceil(PER / dve) - 1

        edges_B = [e for e in node.technosphere() if e["step"]=="B"]
        edges_C = [e for e in node.technosphere() if e["step"]=="C"]

        if edges_B :
            e = edges_B[0]
            a = [exc for exc in node.technosphere() if exc["step"]=="A" and exc["name"]==e["name"]][0]
            old_factor = e["amount"]/a["amount"]
            for e in edges_C :
                e["amount"] = e["amount"]*(factor_b+1)/(old_factor+1)
                e.save()
            if old_factor != 0 :
                for e in edges_B :
                    e["amount"] = e["amount"]*factor_b/old_factor
                    e.save()

            else : 
                for e in edges_B :
                    a = [exc for exc in node.technosphere() if exc["step"]=="A" and exc["name"]==e["name"]][0]
                    e["amount"] = a["amount"]*factor_b
                    e.save()
        
        else : 

            edges = list(node.technosphere())
            
            for exc in edges:
                input_tuple = exc["input"]
                input_node= bd.get_node(database = input_tuple[0],code = input_tuple[1])
                input_name = input_node["name"].lower()

                if create_b_edge and exc["step"] == "C":
                    exc["amount"] = exc["amount"]*(1+ factor_b)
                    exc.save()
                    continue
                elif create_b_edge and exc["step"]  == "A":
                    attributes = exc.as_dict()
                    attributes["amount"] = attributes["amount"]*factor_b
                    attributes["step"] = "B"
                    new_exc = node.new_edge(**attributes)
                    new_exc.save()
                else :
                    continue

def main():
    bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
    fgdb = bd.Database("archetypes_metabo")

    # renew_init(fgdb, PER=50)

    ef31 = [
        m for m in bd.methods
        if ("EF v3.1" in str(m)) and ("no LT" not in str(m)) and ("EN15804" not in str(m))
    ]

    scales = [0.1*i for i in range(1,11,1)]
    # scales = [0,1]
    n_mc = 500
    arch_nodes = [a for a in fgdb if "arch" in str(a["code"])]
    prog_nodes = [a for a in fgdb if "programme" in str(a["code"])]
    for s in tqdm(scales, desc="scales"):
        redefine_unc_scale(arch_nodes, s)
        fgdb.process()
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

        df.write_parquet(f"data/processed/pu_results/multilca_programs_n_MC_{n_mc}_scale_{s}.parquet")

if __name__ == "__main__" :
    main()