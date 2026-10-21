import polars as pl
import questionary
from tqdm import tqdm
import copy

import bw2data as bd
import bw2io as bi
import bw2calc as bc
import bw2analyzer as bwa

from archetypes_re2020.utils.utils import select_project, select_or_create_database, select_database
from archetypes_re2020.data.source import load_parquet_data, load_building_data, INPUT_PATHS

# Que les champs de consos par poste (on considère dans le code que ça
# a toujours la forme cef_vecteur_poste)
CONSUMPTIONS_TO_ADD = ["cef_bois_ch","cef_bois_ecs","cef_elec_ch",
"cef_elec_depl","cef_elec_dist","cef_elec_ecl","cef_elec_ecs","cef_elec_fr",
"cef_elec_mobi","cef_elec_vent","cef_gaz_ch","cef_gaz_ecs","cef_gaz_fr",
"cef_reseau_ch","cef_reseau_ecs","cef_reseau_fr"]

#consos conventionnelles d'après JO RE2020
WATER_CONSUMPTIONS_RATIOS = {
    "Maison individuelle ou accolée" : 48.0,
    "Bureau" : 5.59,
    "Logement collectif" : 48.0,
    "Enseignement secondaire (partie jour)" : 1.44,
    "Enseignement primaire": 1.44
    }


def copy_node_dict(node_dict,target_db_name) :

    source_db_name = node_dict["database"]
    tmp = {**node_dict, "database": target_db_name}

    for exc in tmp.get("exchanges", []):
        if exc["type"] == "production" :
            exc["input"] = (target_db_name,exc["input"][1])
            exc["output"] = (target_db_name,exc["output"][1])
        elif exc.get("output")[0] == source_db_name:
            exc["output"] = (target_db_name,exc["output"][1])

    return tmp


def get_consumptions_codes(cons_db) : 
    elec = cons_db.search("Consommations_éléctricité")[0]
    gaz = cons_db.search("Consommations_gaz")[0]
    bois = cons_db.search("Consommations_bois")[0]
    reseau = cons_db.search("Consommations_réseau")[0]
    eau = cons_db.search("Consommations_eau")[0]

    return {
        "elec" : (elec["database"],elec["code"]),
        "gaz" : (gaz["database"],gaz["code"]),
        "bois" : (bois["database"],bois["code"]),
        "reseau" : (reseau["database"],reseau["code"]),
        "eau" : (eau["database"],eau["code"])
        }

#Pour éviter l'appel à la fonction filter à chaque fois, on met tout dans un dict
def get_buildings_dict(df_buildings, cols=CONSUMPTIONS_TO_ADD):
    buildings_dict = {}
    for row in df_buildings.select(
        [
            "projet_id", "batiment_index"
            ] + cols + ["nb_occupant","usage_principal_1_txt","sref"]
        ).iter_rows(named=True):
        key = (row["projet_id"], row["batiment_index"])
        buildings_dict[key] = {c: row[c] or 0 for c in cols + ["nb_occupant","usage_principal_1_txt","sref"]}
    return buildings_dict


def get_water_consumption_per_year_per_m2(row):
    use_ratio = WATER_CONSUMPTIONS_RATIOS[row["usage_principal_1_txt"]]
    nb_occ = row["nb_occupant"]
    s = row["sref"]
    return use_ratio*nb_occ/s

def add_consumptions_to_node(node,cons_dict,buildings_dict,cols = CONSUMPTIONS_TO_ADD,PER=50) :
    pid, bid = node["name"].split("_")
    row = buildings_dict.get((int(pid), int(bid)), {})
    # print(row)

    if row :
        # Ajout de l'eau
        water_amount = get_water_consumption_per_year_per_m2(row)*PER

        water_edge_dict = {'type': 'technosphere',
                'amount': water_amount,
                "unit" : "cubic meter",
                'input': cons_dict["eau"],
                'output': (node["database"],node["code"])
                }
        node["exchanges"].append(water_edge_dict)

    # Ajout des consos d'énergie selon différents vecteurs
    for c in cols :
        amount = row.get(c, 0)
        if amount :
            _, vecteur, use = c.split("_")
            new_edge_dict = {'type': 'technosphere',
            'energy_use' : use,
            'amount': amount*PER,
            "unit" : "kWh",
            'input': cons_dict[vecteur],
            'output': (node["database"],node["code"])
            }
            node["exchanges"].append(new_edge_dict)
    return node

def copy_and_add_consumptions(db,target_db_name,cons_db,df_buildings,cols = CONSUMPTIONS_TO_ADD,PER=50) :
    print("Chargement du dictionnaire de la base à copier")
    db_dict = db.load()
    res = {}
    cons_dict = get_consumptions_codes(cons_db)
    buildings_dict = get_buildings_dict(df_buildings,cols)
    for key, node_dict in tqdm(db_dict.items(),desc ="Parcours du dictionnaire") :
        tmp = copy_node_dict(node_dict,target_db_name)

        tmp = add_consumptions_to_node(tmp,cons_dict,buildings_dict,cols,PER)
        new_key = (target_db_name, key[1])
        res[new_key] = tmp
    return res

def main():
    # Sélection des bases de données
    select_project()
    # eidb, eidb_name = select_database("Choix de la technosphère : ")
    # biodb, biodb_name = select_database("Choix de la biosphère : ")
    buildb, buildb_name = select_database("Choix de la base de bâtiments RE2020 à copier : ")
    cons_db, cons_db_name = select_database("Choix de la base de procédés de consommations à utiliser : ")
    # Sélection du nom de la base à créer
    build_cons_db_name = select_or_create_database("building", "BUILDINGS_CONS")

    if build_cons_db_name in list(bd.databases):
      del bd.databases[build_cons_db_name]

    # Chargement des données
    df_buildings = load_building_data(INPUT_PATHS["BUILDINGS"])
    # print(df_buildings.columns)
    res = copy_and_add_consumptions(buildb,build_cons_db_name,cons_db,df_buildings)

    # print("Création de la base de bâtiments avec consommations...")
    print(res[list(res.keys())[10]])

    cont = questionary.confirm("Continuer ?",auto_enter=False).ask()

    build_cons_db = bd.Database(build_cons_db_name)

    build_cons_db.write(res)


if __name__ == "__main__":
    main()