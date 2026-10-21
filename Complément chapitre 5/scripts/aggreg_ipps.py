import polars as pl
import os

folder_ipp ="/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/ipps"

output_folder = "/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/data/processed"

ipps = {}

for path,folders,files in os.walk(folder_ipp) :

    for file in files if folders else [] : # condition pour ne pas rentrer dans sous-dossiers
    # for file in files : 
        df = (
            pl.read_csv(os.path.join(path, file), separator=";")
            .group_by(["material", "type"])
            .agg(
                pl.col("volume_m3", "mass_kg", "energy_kWh").sum()
            )
        )
        df.write_excel(f"{output_folder}/{file}_aggregated.xlsx")

#         key = f"('{str(file).split("_")[1]}',{str(file).split("_")[-2]})"
#         value = pl.read_csv(os.path.join(path,file),separator=";")
#         ipps |= {key : value}

# for k,v in ipps.items() :
#     t = eval(k)
#     variante = t[0]
#     year = t[1]
#     ipps[k] = v.with_columns(pl.lit(variante).alias("variante"), pl.lit(year).alias("year"))


# ipps = pl.concat(list(ipps.values()))

