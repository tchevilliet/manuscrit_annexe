
from bw2data.errors import DuplicateNode
import numpy as np
import pandas as pd
import polars as pl

import math

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

import archetypes_re2020.utils.bw25_utils as bw25u
from archetypes_re2020.utils.utils import *

from archetypes_re2020.buildings.add_consumptions import get_consumptions_codes

# Constantes

UNCERTAINTY_TYPES = {
    "LOGNORMAL": 2,
    "BERNOULLI": 6
}

SHAPE_THRESHOLD = 10**(-4) # Pas d'incertitudes lorsque shape (scipy) sous ce seuil
DEFAULT_LOCATION = "FR"
DEFAULT_ARCHETYPE_UNIT = "m2"



def load_material_intensities(filepath):
    """
    Charge les données d'intensités matières depuis un fichier Excel.

    Args:
        filepath (str): Chemin vers le fichier Excel.

    Returns:
        pd.DataFrame: DataFrame avec les intensités matières.
    """
    return pd.read_excel(filepath)


def create_product_code(product_dict, product_database):
    """
    Crée le code d'un produit et vérifie s'il existe dans la base.

    Args:
        product_dict (dict): Dictionnaire contenant nomenclatures et unité.
        product_database (bd.Database): Base de données des produits RE2020.

    Returns:
        str ou None: Code du produit si valide et existant, None sinon.
    """
    product_name = get_name(product_dict, 2)
    # print(product_name)
    if not product_name:
        return None
    
    product_unit = product_dict.get('unite_uf_txt')
    if product_unit is None:
        return None

    product_dve = product_dict.get("dve")
    if product_dve is None :
        print("Problème de dve dans product_dict")

    
    code = "_".join([product_name.lower(), product_unit,str(product_dve)[:-2]])
    product_codes = [a['code'] for a in product_database]
    # print(code in product_codes, "code : ", code,"\n","liste codes : ",product_codes)

    return code if code in product_codes else None


def create_bernoulli_node_name(usage, product_name, product_unit):
    """
    Crée le nom d'un nœud Bernoulli relay.

    Args:
        usage (str): Usage du bâtiment.
        product_name (str): Nom du produit.
        product_unit (str): Unité du produit.

    Returns:
        str: Nom formaté du nœud Bernoulli.
    """
    base_name = "_".join(["bernoulli", usage.lower(), product_name])
    return "_".join([base_name.lower(), product_unit])


def create_lognormal_edge(node, input_node, scale, shape):
    """
    Crée un échange avec distribution lognormale.
    
    Note: scipy et stats_array utilisent des conventions différentes.
    scipy: scale = médiane, shape = écart-type du log
    stats_array: loc = log(médiane), scale = écart-type du log

    Args:
        node: Nœud brightway source.
        input_node: Nœud brightway destination.
        scale (float): Paramètre scale de scipy (médiane).
        shape (float): Paramètre shape de scipy (écart-type du log).

    Returns:
        Edge: Échange créé et sauvegardé.
    """
    edge = node.new_edge(
        input=input_node,
        unit=input_node['unit'],
        database=input_node['database'],
        amount=scale,
        type="technosphere"
    )
    if shape < SHAPE_THRESHOLD :
        # sous le seuil, pas d'incertitudes
        edge.save()
    else : 
        edge['uncertainty type'] = UNCERTAINTY_TYPES["LOGNORMAL"]
        edge['loc'] = np.log(scale)  # Conversion scipy -> stats_array
        edge['scale'] = shape  # Même paramètre
        edge.save()
    return edge


def create_reference_flow(node):
    """
    Crée le flux de référence d'un nœud.

    Args:
        node: Nœud brightway.

    Returns:
        Edge: Flux de référence créé et sauvegardé.
    """
    return node.new_edge(
        input=node,
        unit=node['unit'],
        database=node['database'],
        amount=1.0,
        type="production"
    ).save()


def create_bernoulli_relay_nodes(df, prodb, prodb_name, bernoulli_db_name):
    """
    Crée tous les nœuds Bernoulli relay dans la base de données.

    Args:
        df (pd.DataFrame): DataFrame avec les intensités matières.
        prodb (bd.Database): Base de données des produits RE2020.
        prodb_name (str): Nom de la base de produits.
        bernoulli_db_name (str): Nom de la base Bernoulli à créer.
    """
    bernoudb = bd.Database(bernoulli_db_name)
    bernoudb.write({})
    
    for i in tqdm(df.index, desc="Création relais de Bernoulli"):
        product_dict = eval(df.at[i, 'produit'])
        product_code = create_product_code(product_dict, prodb)
        # print(product_code)

        if product_code is None:
            continue
        
        # Récupération des données
        usage = df.at[i, 'usage']
        shape = df.at[i, 'shape']
        loc = df.at[i, 'loc']
        scale = df.at[i, 'scale']
        
        product_name = get_name(product_dict, 2)
        product_unit = product_dict['unite_uf_txt']
        
        # Création du nœud Bernoulli
        node_name = create_bernoulli_node_name(usage, product_name, product_unit)
        prod_node = bd.get_node(database=prodb_name, code=product_code)
        
        node_attributes = {
            "name": node_name,
            "code": prod_node["code"],
            "unit": prod_node['unit'],
            "location": prod_node['location'],
            "comment": f"Bernoulli relay of {prod_node['name']}",
            "code_prod_db": "_".join([usage, prod_node['code']])
        }
        try :
            bernoulli_node = bernoudb.new_node(**node_attributes)
            bernoulli_node.save()
        except DuplicateNode :
            print(f"DuplicateNode : Using unusual code for {node_name}")
            node_attributes["code"] = "_".join([node_attributes["code"],str(i)])
            bernoulli_node = bernoudb.new_node(**node_attributes)
            bernoulli_node.save()

        
        # Création des échanges
        bernoulli_node = bd.get_node(
            database=bernoulli_db_name,
            code=node_attributes["code"]
            )
        create_lognormal_edge(bernoulli_node, prod_node, scale, shape)
        create_reference_flow(bernoulli_node)


def add_consumptions_to_bernoulli_db(df,consumptions_db,bernoulli_db_name) :

    bernoudb = bd.Database(bernoulli_db_name)

    cons_codes_dict = get_consumptions_codes(consumptions_db)
    cons_db_name = consumptions_db.name

    for i in tqdm(df.index, desc="Création relais de Bernoulli pour consommations"):
        cons = df.at[i, 'produit']
        usage = df.at[i, 'usage']
        shape = df.at[i, 'shape']
        loc = df.at[i, 'loc']
        scale = df.at[i, 'scale']
        vecteur = cons.split("_")[1]
        destination = cons.split("_")[2]


        if any([math.isnan(p) for p in [shape,loc,scale]]) :
            continue
        
        # Création du nœud Bernoulli
        
        prod_code = cons_codes_dict[vecteur]
        # print(prod_code)
        prod_node = bd.get_activity(prod_code)
        node_name = f"bernoulli_{usage}_{prod_node['code']}"
        
        node_attributes = {
            "name": node_name,
            "code": prod_node["code"],
            "unit": prod_node['unit'],
            "location": prod_node['location'],
            "comment": f"Bernoulli relay of {prod_node['name']}",
            "code_prod_db": "_".join([usage, prod_node['code'],destination])
        }
        try :
            bernoulli_node = bernoudb.new_node(**node_attributes)
            bernoulli_node.save()
        except DuplicateNode :
            print(f"DuplicateNode : Using unusual code for {node_name}")
            node_attributes["code"] = "_".join([node_attributes["code"],str(i)])
            bernoulli_node = bernoudb.new_node(**node_attributes)
            bernoulli_node.save()

        
        # Création des échanges
        bernoulli_node = bd.get_node(
            database=bernoulli_db_name,
            code=node_attributes["code"]
            )
        create_lognormal_edge(bernoulli_node, prod_node, scale, shape)
        create_reference_flow(bernoulli_node)




def create_archetype_nodes(usages, archetype_db_name):
    """
    Crée les nœuds d'archétypes pour chaque usage.

    Args:
        usages (list): Liste des usages de bâtiments.
        archetype_db_name (str): Nom de la base de données d'archétypes.

    Returns:
        bd.Database: Base de données d'archétypes créée.
    """
    nodes = {
        (archetype_db_name, str(usage).lower().replace(' ', "_")): {
            "name": str(usage).replace(' ', "_"),
            "unit": DEFAULT_ARCHETYPE_UNIT,
            "location": DEFAULT_LOCATION,
            "exchanges": []
        }
        for usage in usages
    }
    
    archdb = bd.Database(archetype_db_name)
    archdb.write(nodes)
    
    # Création des flux de référence
    for node in archdb:
        create_reference_flow(node)
    
    return archdb


def create_bernoulli_edge(node, input_node, bernoulli_param):
    """
    Crée un échange avec distribution de Bernoulli.
    
    Note: stats_array utilise loc = 1-p (Wikipedia utilise p).

    Args:
        node: Nœud brightway source.
        input_node: Nœud brightway destination.
        bernoulli_param (float): Paramètre p de Bernoulli.

    Returns:
        Edge: Échange créé et sauvegardé.
    """
    if 1-bernoulli_param == 0 :
        #Si le paramètre vaut 1, c'est que tout le monde est concerné, donc pas d'incertitude, valeur 1
        edge = node.new_edge(
            input=input_node,
            unit=input_node['unit'],
            database=input_node['database'],
            amount=1,
            type="technosphere"
        )
        edge['uncertainty type'] = 1 # pas d'incertitudes
        edge['loc'] = 1
        edge.save()
    
    else : 
        edge = node.new_edge(
            input=input_node,
            unit=input_node['unit'],
            database=input_node['database'],
            amount=1 - bernoulli_param,
            type="technosphere"
        )
        edge['uncertainty type'] = UNCERTAINTY_TYPES["BERNOULLI"]
        edge['loc'] = 1 - bernoulli_param  # Conversion Wikipedia -> stats_array
        edge['minimum'] = 0
        edge['maximum'] = 1
        edge.save()
    return edge


def add_exchanges_to_archetypes(df, prodb, archetype_db_name, bernoulli_db_name):
    """
    Ajoute les échanges aux archétypes depuis les données d'intensités matières.

    Args:
        df (pd.DataFrame): DataFrame avec les intensités matières.
        prodb (bd.Database): Base de données des produits RE2020.
        archetype_db_name (str): Nom de la base d'archétypes.
        bernoulli_db_name (str): Nom de la base Bernoulli.
    """
    for i in tqdm(df.index, desc="Ajout des échanges aux archétypes"):
        product_dict = eval(df.at[i, 'produit'])
        product_code = create_product_code(product_dict, prodb)
        
        if product_code is None:
            continue
        
        usage = df.at[i, 'usage']
        bernoulli_param = df.at[i, 'param_bernoulli']
        
        # Récupération des nœuds
        archetype_node = bd.get_node(
            database=archetype_db_name,
            name=str(usage).replace(' ', "_")
        )
        
        bernoulli_node = bd.get_node(
            database=bernoulli_db_name,
            code_prod_db="_".join([str(usage), product_code])
        )
        
        # Création de l'échange avec distribution de Bernoulli
        create_bernoulli_edge(archetype_node, bernoulli_node, bernoulli_param)

def add_exchanges_to_archetypes_consumptions(df, conso_db, archetype_db_name, bernoulli_db_name):
    """
    Ajoute les échanges aux archétypes depuis les données d'intensités matières.

    Args:
        df (pd.DataFrame): DataFrame avec les intensités consos.
        conso_db (bd.Database): Base de données des de consommations RE2020.
        archetype_db_name (str): Nom de la base d'archétypes.
        bernoulli_db_name (str): Nom de la base Bernoulli.
    """
    cons_codes_dict = get_consumptions_codes(conso_db)

    for i in tqdm(df.index, desc="Ajout des échanges aux archétypes"):
        shape = df.at[i, 'shape']
        loc   = df.at[i, 'loc']
        scale = df.at[i, 'scale']
        if any([math.isnan(p) for p in [shape, loc, scale]]):
            continue
        
        conso_name = df.at[i, 'produit'].split("_")
        
        vecteur = conso_name[1]
        destination = conso_name[2]

        prod_code = cons_codes_dict[vecteur]
        # print(prod_code)
        prod_node = bd.get_activity(prod_code)

        usage = df.at[i, 'usage']
        bernoulli_param = df.at[i, 'param_bernoulli']
        
        # Récupération des nœuds
        archetype_node = bd.get_node(
            database=archetype_db_name,
            name=str(usage).replace(' ', "_")
        )
        
        # bernoulli_node = bd.get_activity((bernoulli_db_name, cons_codes_dict[vecteur][1]))
        bernoulli_node = bd.get_node(
            database = bernoulli_db_name,
            code_prod_db = "_".join([usage, prod_node["code"],destination])
            )
        # Création de l'échange avec distribution de Bernoulli
        create_bernoulli_edge(archetype_node, bernoulli_node, bernoulli_param)


def main():
    """
    Pipeline principal de création des bases de données d'archétypes RE2020.
    """
    # Sélection des bases de données
    select_project()
    eidb, eidb_name = select_database("Choix de la technosphère : ")
    biodb, biodb_name = select_database("Choix de la biosphère : ")
    prodb, prodb_name = select_database("Choix de la base de procédés RE2020 : ")
    conso_db, conso_db_name = select_database("Choix de la base de procédés de consommations RE2020 : ")
    
    # Sélection des noms de bases de données
    archetype_db_name = select_or_create_database("archetypes", "ARCHETYPES_MI")
    bernoulli_db_name = select_or_create_database("bernoulli", "BERNOULLI")
    
    # Chargement des données
    source_file = select_source_file()
    df_intensities = load_material_intensities(source_file)
    usages = bw25u.unique_list(df_intensities['usage'])

    source_file_conso = select_source_file("consommations")
    df_intensities_conso = pd.read_excel(source_file_conso)
    
    # Création de la base Bernoulli
    print("Création de la base de données Bernoulli...")
    if bernoulli_db_name in list(bd.databases):
        del bd.databases[bernoulli_db_name]
    
    create_bernoulli_relay_nodes(df_intensities, prodb, prodb_name, bernoulli_db_name)
    add_consumptions_to_bernoulli_db(df_intensities_conso,conso_db,bernoulli_db_name)
    # Création de la base d'archétypes
    print("Création de la base de données d'archétypes...")
    if archetype_db_name in list(bd.databases):
        del bd.databases[archetype_db_name]
    
    archdb = create_archetype_nodes(usages, archetype_db_name)
    
    # Ajout des échanges aux archétypes
    print("Ajout des échanges aux archétypes...")
    add_exchanges_to_archetypes(df_intensities, prodb, archetype_db_name, bernoulli_db_name)
    add_exchanges_to_archetypes_consumptions(df_intensities_conso, conso_db, archetype_db_name, bernoulli_db_name)
    
    print(f"Bases de données créées avec succès:")
    print(f"  - Bernoulli: {bernoulli_db_name}")
    print(f"  - Archétypes: {archetype_db_name}")


if __name__ == "__main__":
    main()
    # select_project()
    # eidb, eidb_name = select_database("Choix de la technosphère : ")
    # biodb, biodb_name = select_database("Choix de la biosphère : ")
    # prodb, prodb_name = select_database("Choix de la base de procédés RE2020 : ")
    # conso_db, conso_db_name = select_database("Choix de la base de procédés de consommations RE2020 : ")
    
    # # Sélection des noms de bases de données
    # archetype_db_name = select_or_create_database("archetypes", "ARCHETYPES_MI")
    # bernoulli_db_name = select_or_create_database("bernoulli", "BERNOULLI")

    # add_exchanges_to_archetypes_consumptions(df_intensities_conso, conso_db, archetype_db_name, bernoulli_db_name)