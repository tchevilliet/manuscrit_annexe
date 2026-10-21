
from archetypes_re2020.utils.utils import *

from archetypes_re2020.config import INTERIM_DATA_DIR, EXTERN_DATA_DIR
from pathlib import Path

import pandas as pd
from datetime import date

# # création d'un projet à la date du jour
today = date.today()

INPUT_PATH = EXTERN_DATA_DIR / "2026-1-19-11h32_process_to_model.xlsx"

new_out = questionary.confirm("Create a new output file ?").ask()

if new_out :
    OUTPUT_PATH = INTERIM_DATA_DIR / f"{today}_bdd_interim_procedes_RE2020.xlsx"
    start = 0
else : 
    OUTPUT_PATH = questionary.path(
        "Which existing output file ?"
        ).ask()
    start = (pd.read_excel(OUTPUT_PATH).iloc[:,0]=='Activity').sum()


select_project()
eidb, eidb_name = select_database(
    message= "Technosphere Database ?"
    )
biodb, biodb_name = select_database(
    message= "Biosphere Database ?"
    )

todo = pd.read_excel(INPUT_PATH)
process_todo = [eval(d) for d in list(todo['nomenclatures_UF_dve'])]

def ensure_excel(path: str) -> str:
    """
    Ensure an Excel file exists at "path" and return the absolute path.

    """
    p = Path(path).expanduser().resolve()       
    if not p.suffix.lower() in {".xlsx", ".xls"}:  
        raise ValueError("Only .xlsx or .xls files are supported")

    if not p.exists():
        # Create a minimal Excel file – an empty DataFrame saved as a sheet named "Sheet1"
        pd.DataFrame().to_excel(p, index=False)

    return str(p)


# Initialisation fichier excel
path = ensure_excel(OUTPUT_PATH)
# db_name = "procedes_RE2020"
# nb_cutoff = 20

# pd.DataFrame({
#     1 : ['cutoff','Database','format','date'],
#     2 : [
#         nb_cutoff,
#         db_name,
#         'Excel spreadsheet',
#         f"{today}_{datetime.now().hour}h{datetime.now().minute}"]
#         }).to_excel(path,header=None,index=None)


for p in process_todo[(start+1):] :
    # On crée le dataframe du noeud
    node_tmp = metadict_to_df(p)
    # On crée le dataframe des arêtes et on les ajoute au fichier excel si les métadonnées ne sont pas vides
    if len(node_tmp)>0 :
        exc_tmp = datadict_to_df(p,eidb)
        append_df(path,node_tmp,sheet="Sheet1",gap=1, header=False,index=False,format="meta") #en sautant une ligne
        append_df(path,exc_tmp,sheet="Sheet1",gap=0,index=False,format="data") #sans sauter de ligne, avec les noms de colonnes
