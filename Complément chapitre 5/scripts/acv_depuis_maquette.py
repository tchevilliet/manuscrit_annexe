import polars as pl
import os 
import bw2data as bd
import bw2io as bi
import bw2calc as bc
import numpy as np
from cmcrameri import cm
from pyarrow import string
from tqdm import tqdm
from datetime import datetime 

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

folder_ipp ="/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/ipps"

ipps = {}

for path,folders,files in os.walk(folder_ipp) :

    for file in files if folders else [] : # condition pour ne pas rentrer dans sous-dossiers
    # for file in files : 
        key = f"('{str(file).split("_")[1]}',{str(file).split("_")[-2]})"
        value = pl.read_csv(os.path.join(path,file),separator=";")
        ipps |= {key : value}

for k,v in ipps.items() :
    t = eval(k)
    variante = t[0]
    year = t[1]
    ipps[k] = v.with_columns(pl.lit(variante).alias("variante"), pl.lit(year).alias("year"))


ipps = pl.concat(list(ipps.values()))

# on uniformise manière de designer programmes
def replace_if_contains(df: pl.DataFrame, column: str, mapping: dict) -> pl.DataFrame:
    # For each key in the mapping, if the cell contains the key, replace the whole cell
    expr = pl.col(column)
    for key, value in mapping.items():
        expr = pl.when(pl.col(column).str.contains(key, literal=True)) \
                 .then(pl.lit(value)) \
                 .otherwise(expr)
    return df.with_columns(expr.alias(column))

mapping = {
    "MidriseApartment": "logement",
    "Office": "bureau",
}

ipps = replace_if_contains(ipps, "program", mapping)

map_path = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/mapping_materiaux.xlsx"
map_mater = pl.read_excel(map_path)

variantes = ipps["variante"].unique()

diff_ipps = ipps.join(ipps, on=["material","program","type"], suffix="_right").filter(
    pl.col("variante") < pl.col("variante_right")
    ).with_columns(
    variante=pl.col("variante") + " - " + pl.col("variante_right"),
    mass_kg=pl.col("mass_kg") - pl.col("mass_kg_right"),
    energy_kWh=pl.col("energy_kWh") - pl.col("energy_kWh_right")
    ).select("material","program","type","volume_m3","densities_kg_m3","mass_kg","energy_kWh","variante","year")

ipps = pl.concat([ipps,diff_ipps])


def create_demand(material, map_materiaux, mass,energy,PER =50 ):
    if "Air Gap" in str(material) :
        return [None,None,None]

    tmp = map_materiaux.filter(pl.col('material') == material)
    if str(material) == "consommation_eau" :
        qte = mass*PER
        print(tmp['conversion (masse-uf)'][0])
    elif "consommation" in str(material) :
        qte = energy*PER
    # elif "vitrage" in str(material) : # modife export IPP.....
    #     qte = area
    else :
        qte = mass
    
    
    db = tmp["database"][0]
    code = tmp["ecoinvent_process_code"][0]
    k = tmp['conversion (masse-uf)'][0]
    try:
        node = bd.get_node(database=db, code=code)
    except Exception:
        return [None, None, None]  
    return [code, node.id, qte*k]

ipps_no_lca = ipps

ipps = ipps.with_columns(
    pl.struct(["material", "mass_kg","energy_kWh"])
    .map_elements(
        lambda s: create_demand(s["material"], map_mater, s["mass_kg"],s["energy_kWh"])[0],
        return_dtype=pl.String
    )
    .alias("process_code"),
    pl.struct(["material", "mass_kg","energy_kWh"])
    .map_elements(
        lambda s: create_demand(s["material"], map_mater, s["mass_kg"],s["energy_kWh"])[1],
        return_dtype=pl.Int64
    )
    .alias("process_id"),
    pl.struct(["material", "mass_kg","energy_kWh"])
    .map_elements(
        lambda s: create_demand(s["material"], map_mater, s["mass_kg"],s["energy_kWh"])[2],
        return_dtype=pl.Float64
    )
    .alias("demand_amount")
    )



def make_lca(process_id,amount,method,use_distributions = False,n_mc = 30):

    if use_distributions:
        lca = bc.LCA(demand={ process_id : amount},method=method,use_distributions= True)
        lca.lci()
        lca.lcia()
        return [lca.score for _ in zip(lca,range(n_mc))]
    else :
        lca = bc.LCA(demand={ process_id : amount},method=method)
        lca.lci()
        lca.lcia()
        return [lca.score]


def lca_from_mc_runs(process_code,demand_amount,df_res_composant,indicator) :
    tmp = df_res_composant.filter(
        pl.col("demand")==process_code,
        pl.col("indicator") == indicator
        )
    return [demand_amount*score for score in tmp["score"].to_list()]

compo_res_path_1 = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-10-2h41_MC_runs/scores.parquet"
compo_res_path_2 = "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-11-21h23_MC_runs/scores.parquet"

df_composant = pl.concat([pl.read_parquet(compo_res_path_1),pl.read_parquet(compo_res_path_2)])


indicators_list = df_composant["indicator"].unique().to_list()

# dict_indicators_units = {}
# for ind in indicators_list :
#     splitted = ind.split(" | ")
#     key = tuple([e for e in splitted])
#     m = bd.Method(key)
#     dict_indicators_units[ind] = m.metadata["unit"]


for ind in tqdm(indicators_list) :
    ipps = ipps.drop_nulls(subset=["process_code", "demand_amount"]).with_columns(
        pl.struct(["process_code", "demand_amount"])
        .map_elements(
            lambda s: lca_from_mc_runs(s["process_code"], s["demand_amount"],df_composant,ind),
            return_dtype=pl.List(pl.Float64)
        )
        .alias(ind)
        )



ipps = ipps.with_columns(
    index=pl.col(indicators_list[0]).list.eval(
        pl.int_range(pl.len(), dtype=pl.Int64)
    )
).explode(*indicators_list,"index")

today = datetime.today()
horodatage = f"{today.year}-{today.month}-{today.day}-{today.hour}h{today.minute}"

ipps.write_parquet(f"/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/processed/Lcas/{horodatage}-maquettes_impacts.parquet")

