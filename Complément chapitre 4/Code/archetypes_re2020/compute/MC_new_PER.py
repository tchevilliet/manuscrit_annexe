
import polars as pl
import math
from tqdm import tqdm

def new_impact(old_impact, process_code, new_PER) :
    if "consommation" in str(process_code) : 
        return old_impact*new_PER/50
    else : 
        try : 
            DVE = float(process_code.split("_")[-1])
            n = math.ceil(50/DVE)
            new_n = math.ceil(new_PER/DVE)
            return old_impact*new_n/n
        except :
            return old_impact*new_PER/50


def main(input_file,new_PER_list) :

    output_folder = "/".join(input_file.split("/")[:-1])
    
    comp_scores = pl.read_parquet(input_file)

    for new_PER in tqdm(new_PER_list,desc = "Parcours des PER",leave=False):

        res = comp_scores.with_columns(
            pl.struct(
                [pl.col("demand"),pl.col("score")]
                ).map_elements(
                    lambda s : new_impact(s["score"],s["demand"],new_PER),
                    return_dtype=pl.Float64
                ).alias("score")
        )

        res.write_parquet(f"{output_folder}/scores_{new_PER}.parquet")


if __name__ == "__main__":
    input_files = [
        "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-10-2h41_MC_runs/scores.parquet",
        "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-11-21h23_MC_runs/scores.parquet",
        "/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/MC_runs/2026-8-25-23h5_MC_runs/scores.parquet"
    ]

    for i in tqdm(input_files) :
        main(i,list(range(60,160,10)))