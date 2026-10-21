import bw2data as bd
import bw2calc as bc
from bw2data import database
import bw2io as bi

import polars as pl

from tqdm import tqdm
from datetime import datetime
import questionary

from archetypes_re2020.utils.utils import select_from_list,select_database,select_project
from archetypes_re2020.config import PROCESSED_DATA_DIR

def select_process(db,default_length = 10 ) :
    choices = [
        str(p) for p,_ in zip(db,range(default_length))
        ] + ["Faire ma recherche"]
    process_name = select_from_list(
        message="Quel procédé analyser ?",
        choices= choices
        )
    
    if process_name == "Faire ma recherche" :
        keyword = questionary.text(message="Nom du procédé ?").ask()
        choices = [str(p) for p in db if keyword.lower() in str(p[1]).lower()]
        process_name = select_from_list(
            message="Quel procédé analyser ?",
            choices= choices
            )
    
    return [p for p in db if process_name == str(p)][0]

def select_indicator(default_length =10):
    choices = [
        str(m) for m,_ in zip(bd.methods,range(default_length))
        ]+ ["Faire ma recherche","Aucun"]
    indicator_name = select_from_list(
        message="Quel indicateur ?",
        choices = choices
        )
    
    if indicator_name =="Faire ma recherche" :
        keyword = questionary.text(message="Nom de l'indicateur ?").ask()
        choices = [str(m) for m in bd.methods if keyword.lower() in str(m).lower()]
        indicator_name = select_from_list(
            message="Quel indicateur ?",
            choices= choices
            )
    elif indicator_name=="Aucun":
        return "Aucun"
    
    return [m for m in bd.methods if str(m) == indicator_name][0]

def contribution_analysis_build(process, ind = (
        'ecoinvent-3.11',
        'EF v3.1',
        'climate change',
        'global warming potential (GWP100)'
        )
        ) :
    """Analyse de contribution généralisée des produits de constructions 
    avec les lots et sous-lots auxquels ils appartiennent aux différents 
    flux élémentaires et à l'indicateur entré en argument.


    Args:
        process (bw node): procédé de type bâtiment, ie un noeud dont 
        les échanges pointent vers la base de produits de construction 
        ou de conso (build_db ou archétypes process based)
        ind (tuple, optional): _description_. Defaults to ( 'ecoinvent-3.11', 'EF v3.1', 'climate change', 'global warming potential (GWP100)' ).

    Returns:
        polars dataframe: Table avec les valeurs d'inventaires et d'inventaire
        caractérisé pour chaque lot et ses produits de construction
    """

    lca = bc.LCA(demand = {process : 1.0}, method = ind)
    lca.lci()
    lca.lcia()


    EF_nodes = [str(bd.get_node(id = i)) for i in lca.dicts.biosphere.keys()] # On crée la liste des noeuds (flux élémentaires) à partir de leurs indices
    total_inv_array = lca.inventory.sum(axis=1).A1 # A1 applatit la matrice : ça va plus vite
    total_inventaire = dict(zip(EF_nodes, total_inv_array))
    s = lca.score

    #Conv en strings avant la boucle
    process_str = str(process)
    ind_str = str(ind)

    exchanges = [exc for exc in process.edges() if exc["type"] != "production"]

    dfs = []

    for e in tqdm(exchanges) :
        input_node = e["input"]
        a = bd.get_node(database = input_node[0],code = input_node[1])

        amount = e["amount"]
        lca.redo_lcia(demand={a.id : amount})


        dfs.append(pl.DataFrame({
            "process": process_str,
            "contrib_to_ef": EF_nodes,
            "contrib_to_ind": ind_str,
            "contrib_of": str(a),
            "lot": str(e["lot_ref"]),
            "sous-lot":str(e["sous_lot_ref"]),
            "inventory_value":lca.inventory.sum(axis=1).A1,
            "charac_inventory_value": lca.characterized_inventory.sum(axis=1).A1,
        }))
    
    res = pl.concat(dfs, rechunk=False)
    
    # on divise les résultats par la valeur de flux de référence

    phi = list(process.production())[0]["amount"]
    res = res.with_columns(
        (pl.col("inventory_value", "charac_inventory_value") / phi))
    res = res.with_columns(
        (pl.col("inventory_value") / pl.col("contrib_to_ef").replace_strict(
            total_inventaire, default=0
        )).alias("relativ_inventory_value"),
        (pl.col("charac_inventory_value") / s).alias("relativ_charac_inventory_value"),
    )
    return res


def main() :
    select_project()

    db,db_name = select_database("Choix de la base de données : ")

    process = select_process(db)

    indicator = select_indicator()

    if indicator == "Aucun" :
        df = contribution_analysis_build(process) # utilisation de l'indicateur par défaut
    else :
        df = contribution_analysis_build(process, ind=indicator)
    
    today = datetime.today()
    horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"
    output_path = PROCESSED_DATA_DIR/f"Contribution/{horodatage}_AC_{process["name"]}.parquet"

    df.write_parquet(output_path)

if __name__ == "__main__":
    main()