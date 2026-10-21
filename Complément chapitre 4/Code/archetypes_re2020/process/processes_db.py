#brightway25 packages
import bw2data as bd
import bw2io as bi
import bw2calc as bc
import bw2analyzer as bwa

# custom functions for brightway
from archetypes_re2020.utils import bw25_utils as bw25u
from archetypes_re2020.utils.utils import *

#useful packages
import openpyxl
from datetime import datetime
import questionary
from tqdm import tqdm
import polars as pl
from collections import defaultdict
from rapidfuzz import fuzz, process


# Constantes
CONCRETE_SEARCH = "market for concrete, 30MPa, RoW"
STEEL_SEARCH = "market for reinforcing steel, GLO"
CONCRETE_SLAB_SEARCH = "market for concrete slab, RoW"
DEFAULT_STEEL_RATE = '100'  # kg/m³
CONCRETE_SLAB_THICKNESS = 0.2  # m pour dalles et prédalles

GLASS_SEARCH = "market for glazing, double, U<1.1 W/m2K"
WASTE_GLASS_SEARCH = "market for used double glazing, U<1.1W/m2K"
DEFAULT_GLASS_RATE = 0.8

HEAT_PUMP_SEARCH = "market for heat pump, brine-water, 10kW, GLO"
WASTE_HEAT_PUMP_SEARCH = "market for used refrigeration machine, R134a as refrigerant, GLO"

REF_PATH = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/external/2026-2-4_process_to_model_grouped.xlsx"


def get_existing_process_databases():
    """
    Récupère les bases de données existantes contenant 'procede' ou 'procédé'.

    Returns:
        list: Liste des noms de bases de données de procédés existantes.
    """
    return [
        db for db in list(bd.databases)
        if ("procede" in db.lower()) or ("procédé" in db.lower()) or ("process" in db.lower())
    ]


def select_or_create_process_database(pattern_key):
    """
    Sélectionne une base de données de procédés existante ou en crée une nouvelle.

    Returns:
        str: Nom de la base de données à utiliser.
    """
    existing_dbs = get_existing_process_databases()
    
    if existing_dbs:
        choice = select_from_list(
            f"Les bdd {existing_dbs} existent déjà, en écraser une ?",
            existing_dbs + ["Non"]
        )
        if choice != "Non":
            return choice
    
    return generate_database_name(pattern_key)


def select_source_file():
    """
    Demande à l'utilisateur de sélectionner le fichier Excel source.

    Returns:
        str: Chemin vers le fichier Excel.
    """
    return questionary.path(
        "Quel fichier excel utiliser pour la base de donnée produits ?"
    ).ask()


def update_excel_database_name(excel_path, database_name):
    """
    Met à jour le nom de la base de données dans le fichier Excel (cellule B2).

    Args:
        excel_path (str): Chemin vers le fichier Excel.
        database_name (str): Nom de la base de données à inscrire.
    """
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.worksheets[0]
    ws['B2'] = database_name
    wb.save(excel_path)


def clean_node_exchanges(node):
    """
    Nettoie les échanges d'un nœud: ajoute flux de référence, supprime les nuls,
    et convertit les types d'échanges.

    Args:
        node: Nœud brightway à nettoyer.

    Returns:
        bool: True si le nœud est conservé, False s'il doit être supprimé.
    """
    if len(list(node.exchanges())) == 0:
        node.delete()
        return False
    
    # Ajout du flux de référence
    node.new_edge(
        input=node,
        unit=node['unit'],
        database=node['database'],
        amount=1.0,
        type="production"
    ).save()
    
    # Suppression des échanges nuls
    null_exchanges = [e for e in node.edges() if e['amount'] == 0]
    for exc in null_exchanges:
        exc.delete()
    
    # Conversion des types d'échanges
    processwithref_exchanges = [
        e for e in node.edges() if e['type'] == 'processwithreferenceproduct'
        ]
    for exc in processwithref_exchanges:
        exc['type'] = 'technosphere'
        exc.save()

    return True


def find_dve(data, excel_path):

    def node_to_str_dict(node,with_unit = True) :
        attrs = [
            'nomenclature_inies_1', 'nomenclature_inies_2', 'nomenclature_inies_3',
            'nomenclature_inies_4', 'nomenclature_inies_5', 'unit'
            ]
        tmp = {attr : node[attr] for attr in attrs}
        if with_unit :
            tmp["unite_uf_txt"] = tmp["unit"]
        else :
            del tmp['unit']
            
        return str(tmp)

    def ratio_to_node(node, col_nom) :
        s = node_to_str_dict(node)
        tmp = eval(col_nom)
        tmp.popitem()
        return fuzz.ratio(s,str(tmp))
    
    df = pl.read_excel(excel_path)
    # # Parse the JSON/dict column once and expand it
    df = df.with_columns(
        pl.col("nomenclatures_UF_dve")
        .map_elements(lambda x: eval(x), return_dtype=pl.Object)
        .alias("parsed_dict")
    )
    # Filter out rows where all values (except last) are None
    df = df.with_columns(
        pl.col("parsed_dict")
        .map_elements(
            lambda x: all([e is None for e in list(x.values())[:-1]]),
            return_dtype=pl.Boolean
        )
        .alias("to_drop")
    )
    df = df.filter(pl.col('to_drop') == False).drop("to_drop")
    # Extract dve value
    df = df.with_columns(
        pl.col("parsed_dict")
        .map_elements(lambda x: x.get("dve"), return_dtype=pl.Float64)
        .alias("dve")
    )

    df = df.drop("parsed_dict")

    # Counter to track how many times each combination has been seen
    combination_counter = defaultdict(int)
    no_match_counter = defaultdict(int)
    exhausted_counter = defaultdict(int)
    
    for idx, node in enumerate(data):
        df = df.with_columns(
            pl.col("nomenclatures_UF_dve")
            .map_elements(
                lambda x: ratio_to_node(node,x),
                return_dtype = pl.Float64
            ).alias("dist_to_node")
        )
        filters = (
            # (pl.col("dist_to_node")>95) 
            # & 
            (pl.col("dist_to_node")==pl.col("dist_to_node").max())
            )

        tmp = df.filter(filters)
        # print(f"\n--- Node {idx}: {node.get('name')} | {node.get('unit')} ---")
        # print(f"Matches found: {len(tmp)}")
        # if len(tmp) > 0:
        #     print(f"Max similarity score: {tmp['dist_to_node'].max()}")
        

        if len(tmp) > 0:
            # Create a hashable key from the combination of filter attributes
            combo_key = node_to_str_dict(node,with_unit=True)
            
            # Get the current counter for this combination
            a = combination_counter[combo_key]
            # print(f"Combo key: {combo_key}")
            # print(f"Counter value (a): {a}, Available matches: {len(tmp)}")

            # Assign the dve value at index a (with bounds checking)
            if a < len(tmp):
                node["dve"] = tmp["dve"][a]
                # print(f"✓ Using match #{a}")
                dve_str = str(node["dve"])
                # Remove decimal part if it ends with .0
                if dve_str.endswith('.0'):
                    dve_str = dve_str[:-2]

                node["code"] = "_".join([
                        str(node['name']).lower(),
                        str(node['unit']),
                        dve_str
                    ])

            else:
                # Handle case where we've exhausted all matches
                node["dve"] = tmp["dve"][-1]
                exhausted_key = (str(node.get('name', '')).lower(), str(node.get('unit', '')))
                exhausted_count = exhausted_counter[exhausted_key]
                exhausted_counter[exhausted_key] += 1
                print(f"\n--- Node {idx}: {node.get('name')} | {node.get('unit')} ---")
                print(f"Matches found: {len(tmp)}")
                print(f"Max similarity score: {tmp['dist_to_node'].max()}")
                print(f"Combo key: {combo_key}")
                print(f"Counter value (a): {a}, Available matches: {len(tmp)}")
                print(f"⚠ Exhausted matches! Using last match. Exhausted count: {exhausted_count}")

                node["code"] = "_".join([
                        str(node['name']).lower(),
                        str(node['unit']),
                        f"exhausted_{str(exhausted_counter)}"
                    ])

            # Increment the counter for this combination
            combination_counter[combo_key] += 1
        
        else:
            # No match found - create a unique code without DVE
            print(f"✗ NO MATCH FOUND")
            node["dve"] = f"no_match_{idx}"
            node["code"] = "_".join([
                str(node['name']).lower(),
                str(node['unit']),
                str(node["dve"])
            ])



    print(f"\n=== SUMMARY ===")
    print(f"Unique combinations matched: {len(combination_counter)}")
    print(f"Total matches used: {sum(list(combination_counter.values()))}")
    print(f"Unique no-match keys: {len(no_match_counter)}")
    print(f"Total no-matches: {sum(list(no_match_counter.values()))}")
    print(f"Unique exhausted keys: {len(exhausted_counter)}")
    print(f"Total exhausted: {sum(list(exhausted_counter.values()))}")
    return data

# def update_nodes_codes(excel_imp, excel_ref_path):
#     """
#     Met à jour les codes de tous les nœuds au format 'nom_unité_dve'.
#     Puisque la dve n'a pas été reporté aux noeuds au moment de la création de 
#     l'excel, le gros de la fonction sert à retrouver cette dve à partir du 
#     fichier excel_ref_path

#     Args:
#         excel_imp (bi.ExcelImporter): excelimporter de brightway 2.5.
#         excel_ref_path (string) : chemin vers le fichier excel de référence
#     """
#     data = find_dve(getattr(excel_imp, "data"),excel_ref_path)


#     for node in data:
#         node['code'] = "_".join(
#             [str(node['name']).lower(), str(node['unit']),str(node["dve"])]
#             )
    
#     setattr(excel_imp,"data",data)
    
#     return excel_imp

from functools import partial

def import_excel_to_database(
    fg_path, *db_to_match, excel_ref_path = REF_PATH, 
    parameters = False, fields_to_match = ('name', 'unit', 'location')
    ):
    """
    Importe les données Excel dans une base de données brightway.

    Args:
        excel_path (str): Chemin vers le fichier Excel.
        techno_db_name (str): Nom de la base de données technosphère.
        bio_db_name (str): Nom de la base de données biosphère.
        excel_ref_path (str) : chemin vers fichier avec dve pour correction code
    """
    imp = bi.ExcelImporter(fg_path)
    imp.apply_strategy(partial(find_dve,excel_path = REF_PATH))
    # print([f"dve : {a["dve"]}, code : {a["code"]}"] for a in getattr(imp,"data")) 
    # data_tmp = update_nodes_codes(imp, excel_ref_path)
    # setattr(imp, "data",data_tmp)
    # apply strategies
    imp.apply_strategies()
    # match fg_db to itself
    imp.match_database(fields=fields_to_match)
    # match fg_db to db_to_match
    for db in db_to_match :
    	imp.match_database(db,fields=fields_to_match) 
    # print stats on the import
    imp.statistics()
    # create the excel_file with the matched fg_db
    imp.write_excel()
    #write project parameters if needed and write the database in bd.Database:
    if parameters :
        imp.write_project_parameters()
        imp.write_database(activate_parameters=True)
    else :
        imp.write_database(activate_parameters=False)
    return None

def select_activity_from_search(search_results, message):
    """
    Sélectionne une activité dans les résultats de recherche.

    Args:
        search_results (list): Liste d'activités brightway.
        message (str): Message de sélection.

    Returns:
        bd.Activity: Activité sélectionnée.
    """
    selection = select_process(
        [f"{act['name']} @ {act['location']} @ {act['unit']}" for act in search_results],
        message=message
    ).split(' @ ')
    
    return [
        act for act in search_results 
        if act['name'] == selection[0] and act['location'] == selection[1]
    ][0]


def ask_steel_rate():
    """
    Demande le taux de ferraillage moyen à l'utilisateur.

    Returns:
        int: Taux de ferraillage en kg/m³.
    """
    steel_rate = questionary.text(
        message='Quel taux de ferraillage moyen (80 kg/m3 considéré dans concrete slab) ?',
        default=DEFAULT_STEEL_RATE,
        validate=lambda x: isinstance(eval(x), int)
    ).ask()
    return eval(steel_rate)


def replace_concrete_slab_in_node(
    node, concrete_activity, steel_activity, steel_rate, database_name):
    """
    Remplace les échanges 'concrete slab' par béton + ferraillage dans un nœud.

    Args:
        node: Nœud brightway à modifier.
        concrete_activity: Activité béton de remplacement.
        steel_activity: Activité ferraillage de remplacement.
        steel_rate (float): Taux de ferraillage en kg/m³.
        database_name (str): Nom de la base de données de procédés.
    """
    concrete_slab_exchanges = [
        e for e in list(node.technosphere()) 
        if "market for concrete slab" in str(e)
    ]
    
    if not concrete_slab_exchanges:
        return
    
    for exc in concrete_slab_exchanges:
        target_node = bd.get_node(code=exc['output'][1], database=database_name)
        
        # Ajout du béton
        target_node.new_edge(
            input=concrete_activity,
            unit=concrete_activity['unit'],
            database=concrete_activity['database'],
            amount=exc['amount'],
            type="technosphere"
        ).save()
        
        # Ajout du ferraillage
        target_node.new_edge(
            input=steel_activity,
            unit=steel_activity['unit'],
            database=steel_activity['database'],
            amount=exc['amount'] * steel_rate,
            type="technosphere"
        ).save()
        
        # Suppression de l'échange concrete slab
        exc.delete()


def replace_concrete_slab_in_database(database, concrete_activity, steel_activity, steel_rate, database_name):
    """
    Remplace tous les échanges 'concrete slab' dans une base de données.

    Args:
        database (bd.Database): Base de données de procédés.
        concrete_activity: Activité béton de remplacement.
        steel_activity: Activité ferraillage de remplacement.
        steel_rate (float): Taux de ferraillage en kg/m³.
        database_name (str): Nom de la base de données.
    """
    for process in tqdm(database, desc="Remplacement concrete slab"):
        replace_concrete_slab_in_node(
            process,
            concrete_activity,
            steel_activity,
            steel_rate,
            database_name
        )


def fix_slab_conversion(database_name, steel_rate):
    """
    Corrige les conversions pour les dalles et prédalles en m².

    Args:
        database_name (str): Nom de la base de données.
        steel_rate (float): Taux de ferraillage en kg/m³.
    """
    try:
        node_slabs = bd.get_node(
            database=database_name,
            code='dalles et prédalles_béton plein armé_m²'
        )
        
        for exc in node_slabs.edges():
            input_node = bd.get_node(
                database=exc['input'][0], code=exc['input'][1]
                )
            
            if 'concrete' in input_node['name']:
                exc['amount'] = CONCRETE_SLAB_THICKNESS
            elif 'steel' in input_node['name']:
                exc['amount'] = CONCRETE_SLAB_THICKNESS * steel_rate
            
            exc.save()
    except Exception as e:
        print(
            f"Avertissement: impossible de corriger les dalles et prédalles: {e}"
            )

def check_reference_product(db) : 
    for node in db : 
        if "reference product" in node.as_dict().keys() :
            continue
        else :
            node["reference product"] = node["code"]
            node.save()
    print("Reference product for each node.")
    return db

def check_waste_flows(db) :
    for node in tqdm(db) :

        for e in node.technosphere():
            try :
                step = e["step"]
            except KeyError : 
                print(f"Exchange {e["input"]} without step")
                continue
            
            if "C" not in step :
                continue
            else :
                if e["amount"]<=0 :
                    continue
                else :
                    e["amount"] = -e["amount"]
                    e.save()


def add_glass_to_windows(db,eidb) : 

    glass_prod_input = eidb.search(GLASS_SEARCH)[0]
    waste_glass_input = eidb.search(WASTE_GLASS_SEARCH)[0]

    glass_prod_exch = {
        "input" : (glass_prod_input["database"],glass_prod_input["code"]),
        "type" : "technosphere",
        "amount" : 0, #quantité définie après
        "step" : "A1-A4" ,
        "unit" : "square meter"
    }
    glass_renew_exch = {
        "input" : (glass_prod_input["database"],glass_prod_input["code"]),
        "type" : "technosphere",
        "amount" : 0, #quantité définie après
        "step" : "B4" ,
        "unit" : "square meter"
    }

    waste_glass_exch = {
        "input" : (waste_glass_input["database"],waste_glass_input["code"]),
        "type" : "technosphere",
        "amount" : 0, #quantité définie après
        "step" : "C2-C4" ,
        "unit" : "square meter"
    }

    for node in [p for p in db if "fenêtre" in str(p["name"]).lower()] : 
        inputs = []
        for e in node.technosphere() :
            node_db, node_code = e["input"]
            inputs.append(bd.get_node(database = node_db,code = node_code))

        cond = any("window" in p["name"] for p in inputs) and (
            not any("glazing" in p["name"] for p in inputs)
            )
        if  cond :
            prod_exch = [
                e for e in node.technosphere() if e["step"]=="A1-A4"
                ][0] # hypothèse que le seul écahnge est le cadre ATTENTION
            renew_exch = [
                e for e in node.technosphere() if e["step"]=="B4"
                ][0] # hypothèse que le seul échange est le cadre ATTENTION
            eol_exch = [
                e for e in node.technosphere() if e["step"]=="C2-C4"
                ][0] # hypothèse que le seul échange est le cadre ATTENTION
            
            if prod_exch["amount"] < 1 :
                glass_prod_exch["amount"] = 1-prod_exch["amount"]
                glass_renew_exch["amount"] = 1-renew_exch["amount"]
                waste_glass_exch["amount"] = 1-eol_exch["amount"]
            elif prod_exch["amount"] == 1 :
                glass_prod_exch["amount"] = DEFAULT_GLASS_RATE
                glass_renew_exch["amount"] = renew_exch["amount"]*DEFAULT_GLASS_RATE
                waste_glass_exch["amount"] = eol_exch["amount"]*DEFAULT_GLASS_RATE     
                prod_exch["amount"] = 1-DEFAULT_GLASS_RATE
                prod_exch.save()
                renew_exch["amount"] = (1-DEFAULT_GLASS_RATE)*renew_exch["amount"]
                renew_exch.save()           
                eol_exch["amount"] = (1-DEFAULT_GLASS_RATE)*eol_exch["amount"]
                eol_exch.save()

            prod_edge = node.new_edge(**glass_prod_exch)
            prod_edge.save()
            renew_edge = node.new_edge(**glass_renew_exch)
            renew_edge.save()
            eol_edge = node.new_edge(**waste_glass_exch)
            eol_edge.save()


def heat_pump_unit_process(db,eidb,per=50) :
    hp_prod_input = eidb.search(HEAT_PUMP_SEARCH)[0]
    hp_eol_input =  eidb.search(WASTE_HEAT_PUMP_SEARCH)[0]

    hp_prod_exch = {
        "input" : (hp_prod_input["database"],hp_prod_input["code"]),
        "type" : "technosphere",
        "amount" : 0.1,
        "step" : "A1-A4" ,
    }
    hp_renew_exch = {
        "input" : (hp_prod_input["database"],hp_prod_input["code"]),
        "type" : "technosphere",
        "amount" : 0.1,
        "step" : "B4" ,
    }

    hp_eol_exch = {
        "input" : (hp_eol_input["database"],hp_eol_input["code"]),
        "type" : "technosphere",
        "amount" : 0, #quantité définie après
        "step" : "C2-C4" ,
    }
    for node in tqdm(db,desc = "Changement des procédés PAC") :
        if "pompes à chaleur" in str(node["name"]).lower() :
            dve = node["dve"]
            if dve>=per :
                renew_ratio = 0
            else :
                renew_ratio = math.ceil(per/dve - 1)

            for e in node.technosphere() :
                e.delete()

            new_prod_exc = node.new_edge(**hp_prod_exch)
            new_prod_exc.save()
            tmp1 = hp_renew_exch.copy()
            tmp1['amount'] = tmp1["amount"]*renew_ratio
            new_renew_exc = node.new_edge(**tmp1)
            new_renew_exc.save()
            tmp2 = hp_eol_exch.copy()
            tmp2['amount'] = tmp1["amount"] + hp_prod_exch["amount"]
            new_eol_exc = node.new_edge(**tmp2)
            new_eol_exc.save()
           
def main():
    """
    Création et  nettoyage de la base de données de procédés RE2020.
    "INIES homemade"
    """
    # Sélection des bases de données
    select_project()
    eidb, eidb_name = select_database("Choix de la technosphère : ")
    biodb, biodb_name = select_database("Choix de la biosphère : ")
    
    # Sélection ou création de la base de données de procédés
    name_db = select_or_create_process_database("PROCESSES")
    
    # Sélection du fichier source
    source_proc = select_source_file()
    print(source_proc)
    # Mise à jour du nom dans le fichier Excel
    update_excel_database_name(source_proc, name_db)
    
    # Suppression de la base si elle existe déjà
    if name_db in list(bd.databases):
        del bd.databases[name_db]
    
    # Import depuis Excel
    print("Import des données Excel...")
    import_excel_to_database(source_proc, eidb_name, biodb_name)
    
    fgdb = bd.Database(name_db)
    
    # Nettoyage des échanges
    print("Nettoyage des échanges...")
    for node in tqdm(fgdb, desc="Nettoyage des nœuds"):
        clean_node_exchanges(node)

    
    # Remplacement de concrete slab
    print("Sélection des procédés de remplacement pour concrete slab...")
    concrete_results = eidb.search(CONCRETE_SEARCH)
    concrete = select_activity_from_search(
        concrete_results,
        "Quel procédé béton pour remplacer concrete slab ?"
    )
    
    steel_results = eidb.search(STEEL_SEARCH)
    steel = select_activity_from_search(
        steel_results,
        "Quel procédé ferraillage pour remplacer concrete slab ?"
    )
    
    steel_rate = ask_steel_rate()
    
    print("Remplacement de concrete slab...")
    replace_concrete_slab_in_database(fgdb, concrete, steel, steel_rate, name_db)
    
    # Correction des dalles et prédalles
    print("Correction des dalles et prédalles...")
    fix_slab_conversion(name_db, steel_rate)

    print("Ajout des reference products...")
    check_reference_product(fgdb)

    print("Ajout des vitres aux fenêtres ...")
    add_glass_to_windows(fgdb,eidb)

    print("Pompes à chaleurs modifiées et flux de référence à 1 kW ...")
    heat_pump_unit_process(fgdb,eidb)

    ## BIEN LAISSER EN DERNIER
    print("Vérification de valeurs négatives pour flux fin de vie ...")
    check_waste_flows(fgdb)

    print(f"Import terminé. Base de données '{name_db}' créée avec succès.")


if __name__ == "__main__":
    main()