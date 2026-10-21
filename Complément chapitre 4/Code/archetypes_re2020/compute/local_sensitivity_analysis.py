import bw2data as bd
import bw2calc as bc


import polars as pl
import numpy as np

from tqdm import tqdm
from datetime import datetime
import questionary

from archetypes_re2020.utils.utils import select_from_list,select_database,select_project
from archetypes_re2020.config import PROCESSED_DATA_DIR
from archetypes_re2020.compute.contribution_analysis import select_process

def select_indicators(default_indicators, default_length = 20) : 
    indicators_list = questionary.checkbox(
        'Quels indicateurs ? ',
        choices=[
        str(m) for m,_ in zip(bd.methods,range(default_length))
        ]+["Faire ma recherche","tout EF v3.1"]
        ).ask()
    
    if indicators_list == ['tout EF v3.1'] :
        indicators_list = default_indicators
    
    elif indicators_list == ["Faire ma recherche"] : 
        keyword = questionary.text(message="mot-clé pour chercher les indicateurs ?").ask()
        choices = [str(m) for m in bd.methods if keyword.lower() in str(m).lower()]
        indicators_list = questionary.checkbox(
            message="Quels indicateurs ?",
            choices= choices
            ).ask()       

    return indicators_list


def OAT_LSA_composants(
    archetype, # doit être de type process based
    indicators_list) :

    lcas_tilde = []

    edges = [exc for exc in archetype.edges() if exc['type'] != 'production']
    
    for indicator in indicators_list:

        lca = bc.LCA(demand={archetype.id: 1.0}, method=indicator)
        lca.lci()
        lca.lcia()
        lcas_tilde.append(lca)

    lca_inventaire = lcas_tilde[0]

    # vec inventaire de ref
    g_tilde = np.array(lca_inventaire.inventory.sum(axis=1)).flatten() 
    # vec score d'impact de ref
    h_tilde = [lca.score for lca in lcas_tilde]

    EF_names = {v: bd.get_node(id=v)['name'] for v, _ in lca_inventaire.dicts.biosphere.items()}

    rows = []

    for exc in tqdm(edges) :
        input_node  = bd.Database(exc['input'][0]).get(exc['input'][1])
        output_node = bd.Database(exc['output'][0]).get(exc['output'][1])

        IF_code = input_node['code']

        col = lca_inventaire.dicts.activity[output_node.id]
        row = lca_inventaire.dicts.activity[input_node.id]
        
        # On stocke la valeur du coefficient de la matrice A
        nominal_value = lca_inventaire.technosphere_matrix[row,col] 
        var_value = nominal_value*1.1

        # on change valeur de l'IF
        lca_inventaire.technosphere_matrix[row,col] =  var_value
        lca_inventaire.redo_lci() # on refait l'inventaire

        g_modif = np.array(lca_inventaire.inventory.sum(axis=1)).flatten()
        
        for lca in lcas_tilde :
            lca.inventory = lca_inventaire.inventory
            lca.lcia()

        # on ajoute résultats à la liste de lignes du tableau final
        # sensibilité inventaire
        for EF_id, EF_idx in lca_inventaire.dicts.biosphere.items():
            rows.append({
                'type': 'inventory',
                'procédé_concerné': IF_code,
                'indicator_or_ef': EF_names[EF_id],
                'xj_tilde': abs(nominal_value),
                'xj_modif': abs(var_value),
                'y_tilde': float(g_tilde[EF_idx]),
                'y_modif': float(g_modif[EF_idx]),
                'lot': exc["lot_ref"],
                'sous_lot' : exc["sous_lot_ref"]
            })
        # sensibilité indicateurs
        for lca, indicator, s in zip(lcas_tilde, indicators_list, h_tilde):
            rows.append({
                'type': 'impact',
                'procédé_concerné': IF_code,
                'indicator_or_ef': str(indicator),
                'xj_tilde': abs(nominal_value),
                'xj_modif': abs(var_value),
                'y_tilde': float(s),
                'y_modif': float(lca.score),
                'lot': exc["lot_ref"],
                'sous_lot' : exc["sous_lot_ref"]
            })

        #on restaure la matrice A
        lca_inventaire.technosphere_matrix[row,col] = nominal_value
    
    res =pl.DataFrame(rows, infer_schema_length=None)
    delta_y = pl.col("y_modif") - pl.col("y_tilde")
    delta_xj = pl.col("xj_modif") - pl.col("xj_tilde")
    sensibilite = delta_y / delta_xj
    
    return res.with_columns(
        delta_y=delta_y,
        delta_xj=delta_xj,
        sensibilite=sensibilite,
        elasticite=sensibilite * pl.col("xj_tilde") / pl.col("y_tilde"),
    )

def multi_OAT_LSA_composants(
    archetypes_list, # doit être de type process based
    indicators_list) :
    arch_init = archetypes_list[0]

    lcas_tilde = []
    
    for indicator in indicators_list:

        lca = bc.LCA(demand={arch_init.id: 1.0}, method=indicator)
        lca.lci()
        lca.lcia()
        lcas_tilde.append(lca)

    lca_inventaire = lcas_tilde[0]

    EF_data = {}
    for flow_id, _ in lca_inventaire.dicts.biosphere.items():
        node = bd.get_node(id=flow_id)
        EF_data[flow_id] = {
            'name': node.get('name', ''),
            'unit': node.get('unit', ''),
            'type': node.get('type', ''),
            'categories': ' :: '.join(node.get('categories', [])),
        }

    indicator_units = { 
        str(indicator): bd.methods[indicator].get('unit', '')
        for indicator in indicators_list
        }

    rows = []

    for archetype in tqdm(archetypes_list, desc="Archetypes"):
        # on change la demande sans toucher aux matrices
        lca_inventaire.lci(demand={archetype.id: 1.0})

        for lca in lcas_tilde:
            lca.lci(demand={archetype.id: 1.0})
            lca.lcia()

        # vec inventaire de ref
        g_tilde = np.array(lca_inventaire.inventory.sum(axis=1)).flatten() 
        # vec score d'impact de ref
        h_tilde = [lca.score for lca in lcas_tilde]

 
        edges = [exc for exc in archetype.edges() if exc['type'] != 'production']

        for exc in tqdm(edges) :
            input_node  = bd.Database(exc['input'][0]).get(exc['input'][1])
            output_node = bd.Database(exc['output'][0]).get(exc['output'][1])

            IF_code = input_node['code']

            try:
                col = lca_inventaire.dicts.activity[output_node.id]
                row = lca_inventaire.dicts.activity[input_node.id]
            except KeyError:
                print(f"Problème pour trouver {IF_code} ou {output_node["code"]}")
                continue
            
            # On stocke la valeur du coefficient de la matrice A
            nominal_value = lca_inventaire.technosphere_matrix[row,col] 
            var_value = nominal_value*1.1

            # on change valeur de l'IF
            lca_inventaire.technosphere_matrix[row,col] =  var_value
            lca_inventaire.lci() # on refait l'inventaire

            g_modif = np.array(lca_inventaire.inventory.sum(axis=1)).flatten()
            
            for lca in lcas_tilde :
                lca.inventory = lca_inventaire.inventory
                lca.lcia()

            # on ajoute résultats à la liste de lignes du tableau final
            # sensibilité inventaire
            for EF_id, EF_idx in lca_inventaire.dicts.biosphere.items():
                data = EF_data[EF_id]
                rows.append({
                    'archetype' : archetype["name"],
                    'type': 'inventory',                    
                    'procédé_concerné': IF_code,
                    'indicator_or_ef': data["name"],
                    'unit' : data["unit"],
                    'EF_type' : data["type"],
                    "EF_categories" : data["categories"], 
                    'xj_tilde': abs(nominal_value),
                    'xj_modif': abs(var_value),
                    'y_tilde': float(g_tilde[EF_idx]),
                    'y_modif': float(g_modif[EF_idx]),
                    'lot': exc["lot_ref"],
                    'sous_lot' : exc["sous_lot_ref"]
                })
            # sensibilité indicateurs
            for lca, indicator, s in zip(lcas_tilde, indicators_list, h_tilde):
                rows.append({
                    'archetype' : archetype["name"],
                    'type': 'impact',
                    'procédé_concerné': IF_code,
                    'indicator_or_ef': str(indicator),
                    'unit' : indicator_units[str(indicator)],
                    'EF_type' : '',
                    "EF_categories" : '',
                    'xj_tilde': abs(nominal_value),
                    'xj_modif': abs(var_value),
                    'y_tilde': float(s),
                    'y_modif': float(lca.score),
                    'lot': exc["lot_ref"],
                    'sous_lot' : exc["sous_lot_ref"]
                })

            #on restaure la matrice A
            lca_inventaire.technosphere_matrix[row,col] = nominal_value
    
    res =pl.DataFrame(rows, infer_schema_length=None)
    delta_y = pl.col("y_modif") - pl.col("y_tilde")
    delta_xj = pl.col("xj_modif") - pl.col("xj_tilde")
    sensibilite = delta_y / delta_xj
    
    return res.with_columns(
        delta_y=delta_y,
        delta_xj=delta_xj,
        sensibilite=sensibilite,
        elasticite=sensibilite * pl.col("xj_tilde") / pl.col("y_tilde"),
    )


def main() :

    select_project()

    DEFAULT_INDICATORS = [m for m in bd.methods if "no LT" not in str(m) and "EF v3.1" in str(m) and "EN15804+A2" not in str(m)]

    db,db_name = select_database("Choix de la base de données : ")

    # archetype = select_process(db)

    indicators_list = select_indicators(default_indicators=DEFAULT_INDICATORS)
    # print(indicators_list)

    archetypes_list = [a for a in db if "Enseignement" in a["name"]]

    # df = OAT_LSA_composants(archetype,indicators_list)
    df = multi_OAT_LSA_composants(archetypes_list,indicators_list)
    
    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"
    output_path = PROCESSED_DATA_DIR/f"Sensibilite/{horodatage}_OAT_LSA_{archetypes_list[0]["name"]}.parquet"
    # output_path = PROCESSED_DATA_DIR/f"Sensibilite/{horodatage}_OAT_LSA_all.parquet"

    df.write_parquet(output_path)


if __name__ == "__main__":
    main()