
import numpy as np
import pandas as pd
import polars as pl

from polars.meta import build
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

from archetypes_re2020.buildings.buildings_db import INPUT_PATH
from archetypes_re2020.process.processes_db import select_source_file
import archetypes_re2020.utils.bw25_utils as bw25u
from archetypes_re2020.utils.utils import *
from archetypes_re2020.data.source import load_parquet_data
from archetypes_re2020.data.remove_extreme_outliers import outliers

def add_sref_per_use(df):
    print("On ajoute une colonne avec le ratio de surface sref_bat/sref_total")
    usages = df.select(pl.col("usage_principal_1_txt").unique()).drop_nulls()["usage_principal_1_txt"]

    sref_per_use = {
    u : df.filter(pl.col("usage_principal_1_txt")==u).select(pl.col("sref").sum())[0,0]
    for u in usages
    }
    df = df.with_columns(
        part_sref = pl.col("sref")/pl.col("usage_principal_1_txt").replace_strict(
            sref_per_use,
            return_dtype=pl.Float64
            )
            )
    
    return df

def pac_outliers(df) :
    df= df.with_columns(
        pmax_cumul = (
            pl.col('puissance_thermique_max_restituable_ch_1')
            + pl.col('puissance_thermique_max_restituable_ch_2')
            )
            )
    
    return outliers(df,"pmax_cumul")


def total_area_per_use(df) :
    
    usages = df.select(
        pl.col("usage_principal_1_txt").unique()
        ).drop_nulls()["usage_principal_1_txt"]


    return {
        u : df.filter(
            pl.col("usage_principal_1_txt")==u
            ).select("projet_id","batiment_index","sref").unique()["sref"].sum()
            for u in usages
            }

def create_reference_flow(usage, database_name,total_area_per_use):
    """
    Crée le flux de référence pour un archetype.

    Args:
        usage (str): usage dont l'archétype est créé.
        database_name (str): Nom de la base de données de bâtiments.

    Returns:
        dict: Dictionnaire représentant le flux de référence.
    """
    archetype_code = str(usage).lower().replace(' ',"_")

    amount = total_area_per_use[usage]

    return {
        'input': (database_name, archetype_code),
        'amount': amount,
        'type': 'production',
        'output': (database_name, archetype_code)
    }

def buildings_set(buildings_db_name) :
    return set([b['code'] for b in bd.Database(buildings_db_name)])

def create_technosphere_exchanges(
    df,
    usage,archetypes_db_name,
    buildings_db_name,
    remove_outliers = False
    ):
    """
    Crée les flux intermédiaires de l'archétype

    Args:
        df (_type_): _description_
        usage (_type_): _description_
        archetypes_db_name (_type_): _description_
        buildings_db_name (_type_): _description_
        buildings_set (_type_): _description_

    Returns:
        _type_: _description_
    """
    archetype_code = str(usage).lower().replace(' ',"_")

    df_filtered = (
        df.filter(
            pl.col("usage_principal_1_txt") == usage
            )
          .select(
            "projet_id",
            "batiment_index",
            "sref",
            'puissance_thermique_max_restituable_ch_1',
            'puissance_thermique_max_restituable_ch_2'
            ).unique()
    )
    df_filtered = pac_outliers(df_filtered)
    if remove_outliers : 
        df_filtered = df_filtered.filter(
            # pl.col("mild_outliers") == False,
            pl.col("extreme_outliers") == False
        )

    b_set = buildings_set(buildings_db_name)
    res=[]
    for (pid,bind,amount,p1,p2,p_tot,mo,eo) in tqdm(df_filtered.iter_rows(),desc=f"Ajout échanges {usage}"):
            code_tmp = "_".join([str(pid),str(bind)])
            if code_tmp in b_set :
                res.append({
                    'input': (buildings_db_name,code_tmp),
                    'amount': amount,
                    'type': 'technosphere',
                    'output': (archetypes_db_name, archetype_code)
                })
            
    return res



def get_exchanges(df, usage, archetypes_db_name, buildings_db_name,total_area_per_use,remove_outliers = False):
    """
    Crée l'ensemble des échanges du noeud archétype de l'usage.

    Args:
        df (_type_): _description_
        usage (_type_): _description_
        archetypes_db_name (_type_): _description_
        buildings_db_name (_type_): _description_
        buildings_set (_type_): _description_

    Returns:
        _type_: _description_
    """
    reference_flow = create_reference_flow(usage, archetypes_db_name,total_area_per_use)
    technosphere = create_technosphere_exchanges(
        df,usage,archetypes_db_name,buildings_db_name,remove_outliers
        )
    
    return [reference_flow] + technosphere


def create_archetype_node(df, usage, archetypes_db_name,buildings_db_name,total_area_per_use,remove_outliers=False):
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
    archetype_code = str(usage).lower().replace(' ',"_")
    
    key = (archetypes_db_name, archetype_code)
    value = {
        "name" : str(usage).replace(' ',"_"),
        "unit" : 'm2',
        "location" : "FR",
        "exchanges" : get_exchanges(
            df,
            usage,
            archetypes_db_name,
            buildings_db_name,
            total_area_per_use,
            remove_outliers
            )
    }
    
    return key, value


def create_nodes_dictionary(df, usages, archetypes_db_name,buildings_db_name,total_area_per_use,remove_outliers=False):
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
            create_archetype_node(df, usage, archetypes_db_name,buildings_db_name,total_area_per_use,remove_outliers)
            for usage in tqdm(usages, desc="Dictionnaire de nœuds complets")
        )
    }

def main():
    # Sélection des bases de données
    select_project()
    # eidb, eidb_name = select_database("Choix de la technosphère : ")
    # biodb, biodb_name = select_database("Choix de la biosphère : ")
    buildb, buildb_name = select_database("Choix de la base de bâtiments RE2020 : ")
    
    # Sélection du nom de la base à créer
    arch_bb_db_name = select_or_create_database("archetypes", "ARCHETYPES_BB")

    # Chargement des données

    df = load_parquet_data(INPUT_PATH)
    # df = add_sref_per_use(df)
    # Création de la base d'archétypes
    print("Création de la base de données d'archétypes...")
    if arch_bb_db_name in list(bd.databases):
        del bd.databases[arch_bb_db_name]

    arch_bb_db = bd.Database(arch_bb_db_name)
    usages = df.select(
        pl.col("usage_principal_1_txt").unique()
        ).drop_nulls()["usage_principal_1_txt"] 
    
    areas_dict = total_area_per_use(df)

    nodes = create_nodes_dictionary(df, usages, arch_bb_db_name,buildb_name,areas_dict,remove_outliers=False)
    arch_bb_db.write(nodes)


if __name__ == "__main__":
    main()