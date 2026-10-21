import polars as pl
import bw2data as bd
import numpy as np

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

compdb = bd.Database("2026-8-9_composants_yc_consos")
eidb  = bd.Database("ecoinvent-3.11-cutoff")

df = pl.read_parquet(
    "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/processed/Lcas/2026-8-20-14h15-maquettes_impacts.parquet"
    )

df = df.unique(
    subset=["variante", "demand_amount", "process_code"], 
    keep="first", 
    maintain_order=True
    )

result={k : {} for k in df["variante"]}

process_array = np.array(df["process_code"])
amount_array =  np.array(df["demand_amount"])
variante_array = np.array(df["variante"])

compo_dict = {k : {} for k in df["process_code"].unique()}

for k in compo_dict.keys() :
    node = bd.get_node(database = compdb.name,code = k )
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

df_res.write_excel("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/processed/ipps_pour_comparaison.xlsx")