import polars as pl
import bw2data as bd
import numpy as np

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")



compdb = bd.Database("archetypes_metabo")
eidb  = bd.Database("ecoinvent-3.11-cutoff")

df = pl.read_ods("/home/thibault.chevilliet@enpc.fr/Documents/2609_comparaisons_inventaires/IPPS/ipps_metabo.ods",sheet_name="ipps")

df = df.filter(~pl.col("materiau").str.contains("Surface"))
df = df.unpivot(index = ["materiau","unit"],variable_name="variante")



result={k : {} for k in df["variante"]}

process_array = np.array(df["materiau"])
amount_array =  np.array(df["value"])
variante_array = np.array(df["variante"])

compo_dict = {k : {} for k in df["materiau"].unique()}

for k in compo_dict.keys() :
    node = bd.get_node(database = compdb.name,name = k )
    for e in node.technosphere() :
        input_tuple = e["input"]
        subnode = bd.get_node(database = input_tuple[0],code = input_tuple[1])
        subkey = (subnode["name"],subnode["unit"])
        compo_dict[k][subkey] = compo_dict[k].get(subkey, 0) + e["amount"]


for code, amount, var in zip(process_array,amount_array,variante_array) :
    if amount != 0 :
        for k, v in compo_dict[code].items() :
            result[var][k] = result[var].get(k,0) + v*amount

rows = [
    {"variante": var, "materiau": name, "unite": unite, "amount": val}
    for var, comps in result.items()
    for (name, unite), val in comps.items()
]

df_res = pl.DataFrame(rows)

df_res.write_excel("/mnt/ef432d92-e906-4d66-b70a-bdda12ad48be/2609_archetypes_metabo/data/processed/ipps_pour_comparaison.xlsx")