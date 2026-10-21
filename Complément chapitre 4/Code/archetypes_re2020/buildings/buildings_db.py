
from archetypes_re2020.utils.utils import *
import archetypes_re2020.utils.bw25_utils as bw25u
from archetypes_re2020.data.source import load_parquet_data
from archetypes_re2020.config import INTERIM_DATA_DIR

import numpy as np
import pandas as pd
import polars as pl

import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats
import warnings

import bw2data as bd
import bw2io as bi
import bw2calc as bc
import bw2analyzer as bwa

from datetime import datetime
import os
import re
import openpyxl
import math
import questionary
from tqdm import tqdm
import ast

# Constantes
INPUT_PATH = INTERIM_DATA_DIR / "quantites_augmentees.parquet"

DEFAULT_BUILDING_UNIT = "m2"
DEFAULT_LOCATION = "FR"
EXCHANGE_METADATA = ["lot_ref","sous_lot_ref"]



def get_existing_building_databases():
    """
    Récupère les bases de données existantes contenant 'batiments' ou 'bâtiments'.

    Returns:
        list: Liste des noms de bases de données de bâtiments existantes.
    """
    return [
        db for db in list(bd.databases)
        if ("batiments" in db.lower()) or ("bâtiments" in db.lower()) or ("building" in db.lower())
    ]


def select_or_create_building_database(pattern_key):
    """
    Sélectionne une base de données de bâtiments existante ou en crée une nouvelle.

    Returns:
        str: Nom de la base de données à utiliser.
    """
    existing_dbs = get_existing_building_databases()
    
    if existing_dbs:
        choice = select_from_list(
            f"Les bdd {existing_dbs} existent déjà, en écraser une ?",
            existing_dbs + ["Non"]
        )
        if choice != "Non":
            return choice
    
    return generate_database_name(pattern_key)


def create_product_code(product_dict, product_codes_set):
    """
    Génère le code d'un produit pour la recherche dans la base de données.

    Args:
        product_dict (dict): Dictionnaire contenant nomenclatures, unité et dve.
        product_codes_set (set): Ensemble des codes existants dans la base de produits.

    Returns:
        str: Code du produit si trouvé dans la base, 'False' sinon.
    """
    # try:
    #     product_dict = ast.literal_eval(product_dict_str)
    # except (ValueError, SyntaxError):
    #     print(f"problème de product_dict_str : {type(product_dict_str)}")
    #     return 'False'

    product_dve =product_dict.get('dve')
    product_unit = product_dict.get('unite_uf_txt')
    if product_unit is None or product_dve is None:
        return 'False'
    
    product_name = get_name(product_dict, 2)

    if not product_name:
        return 'False'

    code = f"{product_name.lower()}_{product_unit}_{str(product_dve)[:-2]}"
 
    return code if code in product_codes_set else 'False'


def add_product_codes(df, product_database):
    """
    Ajoute une colonne avec le code du produit dans la base s'il existe.

    Args:
        df (pl.DataFrame): DataFrame à enrichir.
        product_database (bd.Database): Base de données des produits RE2020.

    Returns:
        pl.DataFrame: DataFrame avec colonne 'code_prodb' ajoutée.
    """
    product_codes_set = {act['code'] for act in product_database}
    
    print("On ajoute une colonne avec le code du produit dans la base s'il existe")
    return df.with_columns(
        pl.col("nomenclatures_UF_dve")
        .map_elements(
            lambda x: create_product_code(x, product_codes_set),
            return_dtype=pl.String
        )
        .alias('code_prodb')
    )


def create_reference_flow(building_id, database_name):
    """
    Crée le flux de référence pour un bâtiment.

    Args:
        building_id (tuple): (projet_id, batiment_index).
        database_name (str): Nom de la base de données de bâtiments.

    Returns:
        dict: Dictionnaire représentant le flux de référence.
    """
    building_code = f"{building_id[0]}_{building_id[1]}"
    return {
        'input': (database_name, building_code),
        'amount': 1.0,
        'type': 'production',
        'output': (database_name, building_code)
    }



def create_technosphere_exchanges(df, building_id, database_name, product_db_name,median_pac_values=False):
    """
    Crée les échanges technosphère pour un bâtiment.

    Args:
        df (pl.DataFrame): DataFrame avec les quantités.
        building_id (tuple): (projet_id, batiment_index).
        database_name (str): Nom de la base de données de bâtiments.
        product_db_name (str): Nom de la base de données des produits.

    Returns:
        list: Liste des échanges technosphère.
    """
    df_filtered = (
        df.filter(
        (pl.col("projet_id") == building_id[0]),
        (pl.col("batiment_index") == building_id[1]),
        (pl.col("code_prodb") != "False")
        )
        .select(
            [
                "code_prodb",
                "quant_surf",
                'puissance_thermique_max_restituable_ch_1',
                'puissance_thermique_max_restituable_ch_2',
                "sref",
                "usage_principal_1_txt",
                *EXCHANGE_METADATA])

    )
    
    building_code = f"{building_id[0]}_{building_id[1]}"
    rows = df_filtered.to_dicts()

    #construction des échanges avec la quantité surfacique
    exchanges=[
        {
            'input': (product_db_name, row["code_prodb"]),
            'amount': row["quant_surf"],
            'type': 'technosphere',
            'output': (database_name, building_code),
            **{ k : row[k] for k in EXCHANGE_METADATA}
            } 
        for row in rows
        ]

    codes_pac = [
        a["code"] for a in bd.Database(product_db_name) if "Pompes à chaleur" in a["name"]
        ]
    # print(codes_pac)

    def _pac_amount(row, median_pac_values) :
        sref = row["sref"]
        sref = float(sref) if sref is not None else 1.0
        if median_pac_values :
            try : 
                return median_pac_values[row["usage_principal_1_txt"]]/sref
            except KeyError :
                print(row)
                return 0
             
        else :
            print("mode chacun sa puissance")
            ch1 = row["puissance_thermique_max_restituable_ch_1"]
            ch2 = row["puissance_thermique_max_restituable_ch_2"]
            
            ch1 = float(ch1) if ch1 is not None else 0.0
            ch2 = float(ch2) if ch2 is not None else 0.0
            
            return (ch1 + ch2)/sref


    i = 0
    for j,e in enumerate(exchanges) :
        row_code = e['input'][1]
        # print(row_code)
        if row_code in codes_pac:
            if i == 0:
                e['amount'] = _pac_amount(rows[j],median_pac_values)
            else:
                e['amount'] = 0.0  # Extra heat pumps get zero
            i += 1
    
    return exchanges


def get_exchanges(building_id, df, database_name, product_db_name,median_pac_values = False):
    """
    Crée la liste complète des échanges pour un bâtiment.

    Args:
        building_id (tuple): (projet_id, batiment_index).
        df (pl.DataFrame): DataFrame avec les quantités.
        database_name (str): Nom de la base de données de bâtiments.
        product_db_name (str): Nom de la base de données des produits.

    Returns:
        list: Liste complète des échanges (référence + technosphère).
    """
    reference_flow = create_reference_flow(building_id, database_name)
    technosphere = create_technosphere_exchanges(df, building_id, database_name, product_db_name,median_pac_values)
    
    return [reference_flow] + technosphere


def create_building_node(building, df, database_name, product_db_name,median_pac_values=False):
    """
    Crée un nœud complet pour un bâtiment.

    Args:
        building (tuple): (projet_id, batiment_index, usage_principal_1_txt).
        df (pl.DataFrame): DataFrame avec les quantités.
        database_name (str): Nom de la base de données de bâtiments.
        product_db_name (str): Nom de la base de données des produits.

    Returns:
        tuple: (clé, valeur) pour le dictionnaire de nœuds.
    """
    building_id = (building[0], building[1])
    building_code = f"{building[0]}_{building[1]}"
    
    key = (database_name, building_code)
    value = {
        "name": building_code,
        "usage": building[2],
        "unit": DEFAULT_BUILDING_UNIT,
        "location": DEFAULT_LOCATION,
        "exchanges": get_exchanges(building_id, df, database_name, product_db_name,median_pac_values)
    }
    
    return key, value


def create_nodes_dictionary(buildings, df, database_name, product_db_name,median_pac_values=False):
    """
    Crée le dictionnaire complet de tous les nœuds de bâtiments.

    Args:
        buildings (list): Liste des tuples (projet_id, batiment_index, usage).
        df (pl.DataFrame): DataFrame avec les quantités.
        database_name (str): Nom de la base de données de bâtiments.
        product_db_name (str): Nom de la base de données des produits.

    Returns:
        dict: Dictionnaire de nœuds prêt à être écrit dans brightway.
    """
    return {
        key: value
        for key, value in (
            create_building_node(b, df, database_name, product_db_name,median_pac_values)
            for b in tqdm(buildings, desc="Dictionnaire de nœuds complets")
        )
    }


def main():
    """
    Pipeline principal de création de la base de données de bâtiments RE2020.
    """
    # Chargement et prétraitement des données
    df_quantities = load_parquet_data(INPUT_PATH)
  
    # Sélection des bases de données
    select_project()
    eidb, eidb_name = select_database("Choix de la technosphère : ")
    biodb, biodb_name = select_database("Choix de la biosphère : ")
    prodb, prodb_name = select_database("Choix de la base de procédés RE2020 : ")
    
    # Sélection ou création de la base de données de bâtiments
    name_db = select_or_create_building_database("BUILDINGS")
    
    # Suppression de la base si elle existe déjà
    if name_db in list(bd.databases):
        del bd.databases[name_db]
    
    batdb = bd.Database(name_db)
    
    # Ajout des codes produits
    df_quantities = add_product_codes(df_quantities, prodb)
    
    # Extraction des bâtiments uniques
    buildings = df_quantities.select(
        "projet_id", "batiment_index", "usage_principal_1_txt"
    ).unique().rows()
    

    # A CHANGER : hardcoding des valeurs médianes des puissances chauds
    # par usage pour résultats rapides, faire une fonction propre
    pac_medians = {
        "Maison individuelle ou accolée" : 12.6,
        "Logement collectif" : 20.2,
        "Bureau" : 16.3,
        "Enseignement primaire" : 13.9,
        "Enseignement secondaire (parite jour)" : 20.4,
    }

    # Création des nœuds
    nodes = create_nodes_dictionary(buildings, df_quantities, name_db, prodb_name,median_pac_values = pac_medians)
    
    # sauvegarde du dictionnaire au cas ou l'écriture plante : 

    import pickle

    with open(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/batdb.pkl", "wb") as f:
        pickle.dump(nodes, f)

    # batdb = bd.Database('2026-8-9-23h6_buildings_RE2020')
    # import pickle
    # with open(f"/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/batdb.pkl", "rb") as f:
    #     nodes = pickle.load(f)

    # Écriture de la base
    batdb.write(nodes)
    print(f"Base de données '{name_db}' créée avec {len(nodes)} bâtiments.")


if __name__ == "__main__":
    main()