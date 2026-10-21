from tqdm import tqdm
# import copy


from archetypes_re2020.utils.utils import *


def building_node_to_prod_dict(building_exch_dict) :
    db, code = building_exch_dict["input"]
    b = bd.get_node(database = db,code=code)
    # print(list(b.technosphere())[0].unit)
    res = {}
    for e in b.technosphere() :
        ed = e.as_dict()
        # print(ed)
        if "lot_ref" in ed.keys() :
            res[
                (
                    ed["input"],
                    ed["lot_ref"],
                    ed["sous_lot_ref"]
                    )
                    ]  = ed["amount"]
        elif "energy_use" in ed.keys() :
            res[
                (
                    ed["input"],
                    ed["input"][1],
                    ed["energy_use"]
                    )
                    ]  = ed["amount"]
        else : 
            res[
                (
                    ed["input"],
                    ed["input"][1],
                    ed["input"][1]
                    )
                    ]  = ed["amount"]                 
    return res


def sum_or_create_item(res_dict,new_dict,surf) :
    for k,v in new_dict.items():
        if k in res_dict : 
            res_dict[k] += surf*v
        else : 
            res_dict[k] = surf*v
    return res_dict

def aggregate_per_product(arch_node_dict) :
    res_dict = {}

    for b in tqdm(
        [e for e in arch_node_dict["exchanges"] if e["type"]=="technosphere"],
        desc="Parcours des bâtiments",
        leave=False,
        position=2
        ) :
        # print(b)
        surf = b["amount"]
        tmp = building_node_to_prod_dict(b)
        res_dict = sum_or_create_item(res_dict,tmp,surf)
    
    return res_dict

def create_technosphere_flows_from_agg_dict(agg_dict,new_key) :

    exchanges_list = [
        {
            'type': 'technosphere',
            'amount': v,
            "input" : k[0],
            "output" : new_key,
            "lot_ref" : k[1],
            "sous_lot_ref" : k[2]
        }
        for k,v in tqdm(agg_dict.items(),desc = "Parcours du dictionnaire agrégé",leave=False,position=1)
    ]
    return exchanges_list

def copy_arch_node_only_ref_flow(arch_node_dict,target_db_name) :
    res = { k : v for k,v in arch_node_dict.items() if k != "exchanges"}

    ref_flow = [e for e in arch_node_dict["exchanges"] if e["type"]=="production"][0]

    res["database"] = target_db_name
    new_key = (target_db_name,ref_flow["input"][1])
    ref_flow["input"] = new_key
    ref_flow["output"] = new_key
    res["exchanges"] = [ref_flow]
    return res


def copy_and_aggregate_per_product(bb_arch_db,target_db_name,buildings_db) :
    bb_arch_db_dict = bb_arch_db.load()
    res = {}
    for old_key, arch_node_dict in tqdm(
        bb_arch_db_dict.items(),
        desc="Parcours des arcéhtypes",
        position=0
        ):
        new_arch_node = copy_arch_node_only_ref_flow(arch_node_dict,target_db_name)
        new_key = new_arch_node["exchanges"][0]["input"]
        inter_flows = create_technosphere_flows_from_agg_dict(
            aggregate_per_product(
                arch_node_dict
            ),new_key
            )
        new_arch_node["exchanges"] += inter_flows
        
        res[new_key] = new_arch_node
    return res

def main():
    # Sélection des bases de données
    select_project()

    buildings_db = select_database("Choix de la base de bâtiments RE2020 : ")

    bb_arch_db, bb_arch_db_name = select_database("Choix de la base d'archétypes buildings based RE2020 : ")
    
    # Sélection du nom de la base à créer
    arch_pr_db_name = select_or_create_database("archetypes", "ARCHETYPES_PR")

    # Création de la base d'archétypes
    print("Création de la base de données d'archétypes...")
    if arch_pr_db_name in list(bd.databases):
        del bd.databases[arch_pr_db_name]

    arch_pr_db = bd.Database(arch_pr_db_name)

    nodes = copy_and_aggregate_per_product(bb_arch_db,arch_pr_db_name,buildings_db)
    print(nodes)
    arch_pr_db.write(nodes)


if __name__ == "__main__":
    main()