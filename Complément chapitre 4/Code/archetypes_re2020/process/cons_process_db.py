#brightway25 packages
import bw2data as bd
import bw2io as bi
import bw2calc as bc
import bw2analyzer as bwa

# custom functions for brightway
from archetypes_re2020.utils import bw25_utils as bw25u
from archetypes_re2020.utils.utils import *

def import_excel_to_database_normal(
    fg_path, *db_to_match, 
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

    imp.apply_strategies()

    imp.match_database(fields=fields_to_match)

    for db in db_to_match :
    	imp.match_database(db,fields=fields_to_match)
    
    imp.statistics()

    imp.write_excel()
    #write project parameters if needed and write the database in bd.Database:
    if parameters :
        imp.write_project_parameters()
        imp.write_database(activate_parameters=True)
    else :
        imp.write_database(activate_parameters=False)
    return None

def main() :

    select_project()
    eidb, eidb_name = select_database("Choix de la technosphère : ")
    biodb, biodb_name = select_database("Choix de la biosphère : ")
    
    excel_path = questionary.path(
        "Quel fichier excel utiliser pour la base de donnée consommations ?"
    ).ask()

    # Import depuis Excel
    print("Import des données Excel...")
    import_excel_to_database_normal(excel_path, eidb_name, biodb_name)


if __name__ == "__main__":
    main()


