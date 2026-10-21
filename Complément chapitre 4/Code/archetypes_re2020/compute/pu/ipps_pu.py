import bw2data as bd
from bw2data import database
import bw2io as bi
from tqdm import tqdm
from itertools import combinations,permutations
from archetypes_re2020.compute.pu.compare_pu_weighted import f_tilde_from_var


bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")



################################### PROGRAMMES A EVALUER

########### VARIANTES MAQUETTES
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


#### AFFECTATION DES ARCHETYPES AUX PROGRAMMES

map_arch = {
    "individual_housing" : "Maison individuelle ou accolée",
    "collective_housing" : "Logement collectif",
    "office_building" : "Bureau",
    # "industrial_building" : "Bureau",
    # "education_building" : 'Enseignement secondaire (partie jour)',
    "education_building" : "Bureau",
    "roads" : "roads_m2_per",
    "vegetation" : "vegetation_m2_per"}

OPEN_DEMANDS = {"roads_m2_per", "vegetation_m2_per"} # sert à différencier batiments et espaces ext


def ipp_from_f_tilde(f_tilde, qty_by_arch):
    res = {}  
    for k, v in f_tilde.items():
        tmp = qty_by_arch[k]
        for input_code, sub_dict in tmp.items():
            res_sub = res.setdefault(input_code, {})
            for sub_code, amount in sub_dict.items():
                res_sub[sub_code] = res_sub.get(sub_code, 0) + v * amount
    return res


#### COMBINAISON DES PROGRAMMES

to_assess_dict = dict(programmes)
for prog1, prog2 in combinations(programmes.keys(), r=2):
    to_assess_dict[f"{prog1} - {prog2}"] = {
        k: programmes[prog1][k] - programmes[prog2][k] for k in programmes[prog1]
    }

import polars as pl

def main():
    arch_db = bd.Database("2026-8-13-16h52_archetypes_RE2020_BB")

    node_cache = {}
    def get_node_cached(database, code):
        key = (database, code)
        node = node_cache.get(key)
        if node is None:
            node = bd.get_node(database=database, code=code)
            node_cache[key] = node
        return node

    qty_by_arch = {}
    usages = []
    for arch in tqdm(arch_db, desc="archetypes"):
        phi = list(arch.production())[0]["amount"]
        arch_name = arch["name"]
        usages.append(arch_name)
        qty = {}  # {input_code: {sub_input_code: amount}}
        for e in tqdm(arch.technosphere(),desc="batiments",leave=False):
            db_name, code = e["input"]
            alpha = e["amount"]
            b_node = get_node_cached(db_name, code)
            for exc in tqdm(b_node.technosphere(),desc = "composants",leave=False):
                input_db, input_code = exc["input"]
                beta = exc["amount"]
                input_node = get_node_cached(input_db, input_code)

                sub_qty = qty.setdefault(input_code, {})
                for sub_exc in input_node.technosphere():
                    sub_code = sub_exc["input"][1]
                    sub_amount = sub_exc["amount"]
                    sub_qty[sub_code] = sub_qty.get(sub_code, 0) + (alpha*beta*sub_amount/phi)

        qty_by_arch[arch_name] = qty

    import json

    with open("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/ipps_variantes_maquettes/qty_by_arch.json", "w") as f:
        json.dump(qty_by_arch, f)


    result = {}
    for var_key, var_dict in (pbar := tqdm(to_assess_dict.items(), leave=False)):
        pbar.set_description(f"Variante {var_key}")
        f_tilde = f_tilde_from_var(var_dict, usages)
        ipp = ipp_from_f_tilde(f_tilde, qty_by_arch)
        result[var_key] = ipp

    return result


def export_results(result, output_path):
    composants, sous_composants, quantites, variantes = [], [], [], []
    for var_key, ipp in result.items():
        for input_code, sub_dict in ipp.items():
            for sub_code, amount in sub_dict.items():
                composants.append(input_code)
                sous_composants.append(sub_code)
                quantites.append(amount)
                variantes.append(var_key)

    to_export = pl.DataFrame({
        "composant": composants,
        "sous_composant": sous_composants,
        "quantite": quantites,
        "variante": variantes,
    })

    to_export.write_excel(output_path)


def code_to_name_unit(ecoinvent_database,compo_database,code) :
    if "consommation" in str(code) :
        tmp = bd.get_node(database = compo_database.name,code=code)
    
    else : 
        tmp =bd.get_node(database = ecoinvent_database.name,code=code)
        return (tmp["name"],tmp["unit"])


# ### triatement post_export...

def post_traitement(df,eidb,output_path) :
    compdb = bd.Database("2026-8-9_composants_yc_consos")

    df = df.with_columns(
        pl.col("sous_composant").map_elements(
        lambda x: code_to_name_unit(eidb,compdb,x),
        return_dtype=pl.Struct({"name": pl.String, "unit": pl.String}),
        )
        .alias("name_unit")
    ).unnest("name_unit")
    df.write_excel(output_path)

if __name__ == "__main__":
    result = main()
    export_results(
        result,
        "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/ipps_variantes_maquettes/ipps_variantes_maquettes_final.xlsx",
    )
    post_traitement(
        result,
        bd.Database("ecoinvent-3.11-cutoff"),
        "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/ipps_variantes_maquettes/ipps_variantes_maquettes_final_translated.xlsx"
        )
