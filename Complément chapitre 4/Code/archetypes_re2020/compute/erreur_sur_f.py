"""
Script pour calculer les erreurs résiduels archétypes vs bâtiments

e_{i,j} = q_{i,j} - S theta_{i, archetype de j}



"""

import polars as pl
import bw2data as bd
from tqdm import tqdm


PER =50

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")
arch_db = bd.Database("2026-4-23-18h10_archetypes_RE2020_PRB")
bat_db = bd.Database("2026-4-22-16h7_buildings_cons_RE2020")
df_bat = pl.read_csv("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/raw/202505_export_batiments_daact.csv",ignore_errors=True)


def get_theta_dict(arch_db) : 
    res = {}
    for arch in arch_db :
        flux_ref = list(arch.production())[0]["amount"]

        theta_dict = {}
        for exc in arch.technosphere() :
            code_composant = exc["input"][1]
            if code_composant not in theta_dict:
                theta_dict[code_composant] = 0.0
            theta_dict[code_composant] += exc["amount"] / flux_ref
        
        res[arch["code"]] = theta_dict

    return res   

def get_bat_surf_dict(df_bat,bat_db) :
    df_bat = df_bat.with_columns(
        key = (pl.col("projet_id").cast(pl.Int64).cast(pl.String)) + "_" + 
              (pl.col("batiment_index").cast(pl.Int64).cast(pl.String))
    )

    surf_dict = dict(zip(df_bat["key"],df_bat["sref"]))

    return surf_dict



def get_theta(archetype_db,usage, composant_code) :
    a = [a for a in archetype_db if a["code"] == "_".join(usage.lower().split(" "))]
    if a : 
        arch = a[0]
    else : 
        print(f"pas d'archetype {usage}")
        return None
    flux_ref = list(arch.production())[0]["amount"]
    theta = 0.
    for exc in [e for e in arch.technosphere() if e['input'][1]==composant_code] :
        theta += exc["amount"]/flux_ref

    return theta

# res = pl.DataFrame(schema={"code_bat": pl.String, "usage" : pl.String,"code_composant": pl.String, "q":pl.Float64,"theta" : pl.Float64, "error":pl.Float64})

rows = []

arch_theta_dicts = get_theta_dict(arch_db)
surf_dict = get_bat_surf_dict(df_bat,bat_db)
for bat in tqdm(bat_db) : 
# for bat in tqdm([a for _,a in zip(range(2),bat_db)]) :
    usage = bat["usage"]
    if usage is None : 
        continue
    code = bat["code"]

    theta_dict = arch_theta_dicts["_".join(usage.lower().split(" "))]
    S = surf_dict.get(code,0.0)
    conso_elec = 0
    for exc in bat.technosphere() :
        code_composant = exc["input"][1]
        if "consommations_elec" in code_composant :
            conso_elec += exc["amount"]
        else :
            q = exc["amount"]
            theta = theta_dict.get(code_composant,0.0)
            rows.append(
                {
                    "code_bat": code,
                    "usage" : usage,
                    "code_composant": code_composant,
                    "q" : q,
                    "S" : S,
                    "theta" : theta,
                }
            )
    rows.append(
    {
        "code_bat": code,
        "usage" : usage,
        "code_composant": "consommations_elec",
        "q" : conso_elec,
        "S" : S,
        "theta" : theta_dict.get("consommations_elec",0.0),
    }
)



res= pl.DataFrame(rows)
# On somme les quantités des même composant, mais on garde le même theta et S, qui est unique
res = res.group_by("code_bat", "code_composant").agg(
    pl.col("q").sum(),
    pl.col("theta").first(),
    pl.col("usage").first(),
    pl.col("S").first()
)

res = res.with_columns(
    error = pl.col("S")*pl.col("q") - pl.col("S")*pl.col("theta")
)

res.write_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/Erreurs/final_demand_vector_error.parquet")
