"""
Recale les archétypes process_based avec la nouvelle bdd de procédés et
ajuste les valeurs d'échange à partir de la dve de cahque produit pour
coller au calcul dynamique RE2020

Permet analyse de contribution à égale valeur normalement...

"""



from tqdm import tqdm
from datetime import datetime
import bw2data as bd
import bw2io as bi
import math
from tqdm import tqdm
import polars as pl

PER =50

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

arch_db_to_copy = bd.Database("2026-4-23-18h10_archetypes_RE2020_PRB")
process_db_to_copy = bd.Database("2026-8-9_composants_yc_consos")

fco2 =  {k: v[0] for k, v in pl.read_excel(
    "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/external/fco2.xlsx"
    ).rows_by_key(key="Année", unique=True).items()}

new_process_db_name = "2026-8-9_composants_yc_consos_dynRE2020"

new_process_db = process_db_to_copy.copy(new_process_db_name)

for node in tqdm(new_process_db,desc="Parcours noeuds") :
    try : 
        dve = node["dve"]
    except KeyError :
        continue

    if dve >= PER :
        continue

    prod_exc = [e.as_dict() for e in node.technosphere() if "A" in e["step"]]
    renew_exc = [e.as_dict() for e in node.technosphere() if "B" in e["step"]]
    eol_exc = [e.as_dict() for e in node.technosphere() if "C" in e["step"]]

    for exc in [e for e in node.technosphere() if "A" not in e["step"]] :
        exc.delete()
    
    nb_renew = math.floor(PER/dve)

    for e in renew_exc :
        amount = e["amount"]/nb_renew
        for i in range(1,nb_renew+1):
            fpond = fco2[i*dve]
            attributes = e
            attributes["amount"] = fpond*amount
            attributes["fpond"] = fpond
            edge = node.new_edge(**attributes)
            edge.save()

    for e in eol_exc :
        amount = e["amount"]/(nb_renew+1)
        for i in range(1,nb_renew+1):
            fpond = fco2[i*dve]
            attributes = e
            attributes["amount"] = fpond*amount
            attributes["fpond"] = fpond
            edge = node.new_edge(**attributes)
            edge.save()
        fpond = fco2[50]
        attributes = e
        attributes["amount"] = fpond*amount
        attributes["fpond"] = fpond
        edge = node.new_edge(**attributes)
        edge.save()





# new_arch_db_name = "2026-4-23-18h10_archetypes_RE2020_PRB_dynRE2020"

# new_arch_db = arch_db_to_copy.copy(new_arch_db_name)

# for arch in new_arch_db :
#     for edge in arch.technosphere() :
#         tmp = edge["input"]
#         tmp[0] = new_process_db_name
#         edge['input'] = tmp
#         edge.save()


    
        



