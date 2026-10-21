import bw2data as bd
import bw2calc as bc
import numpy as np
import polars as pl
from scipy.sparse.linalg import splu
from tqdm import tqdm

bd.projects.set_current("2026-01-13-ecoinvent-3.11-cutoff")

batdb = bd.Database("2026-9-20-18h28_buildings_RE2020_dynRE2020")

indicators = [
    m for m in bd.methods if (
        "gwp" in str(m).lower() 
        and "no LT" not in str(m) 
        and "EF v3.1" in str(m) 
        and "fossil" not in str(m) 
        and "biogenic" not in str(m) 
        and "land" not in str(m))]

lca = bc.LCA({next(iter(batdb)): 1}, indicators[0])
lca.lci()
B = lca.biosphere_matrix.tocsc()
A = lca.technosphere_matrix.tocsc()

# One column of W per method
cols = []
for m in indicators:
    lca.switch_method(m)
    lca.lcia()
    c = lca.characterization_matrix.diagonal()
    cols.append(B.T @ c)
W = np.column_stack(cols)



# Factorize once, solve for all methods
X = splu(A.T.tocsc()).solve(W)                    # (n_products x n_methods)

# Map matrix index -> activity metadata, single pass over the database
id_to_act = {a.id: a for a in batdb}
idx_to_id = {v: k for k, v in lca.dicts.product.items()}

rows = [id_to_act.get(idx_to_id[i]) for i in range(X.shape[0])]
df = pl.DataFrame(
    {
        "database": [a["database"] if a else None for a in rows],
        "code":     [a["code"] if a else None for a in rows],
        "name":     [a.get("name") if a else None for a in rows],
        "location": [a.get("location") if a else None for a in rows],
        **{"|".join(m): X[:, j] for j, m in enumerate(indicators)},
    }
)

# Drop rows belonging to other databases (e.g. biosphere or dependencies)
df = df.filter(pl.col("database") == batdb.name)
df.write_parquet("/home/thibault.chevilliet@enpc.fr/Documents/2601_archetypes_re2020/data/processed/bat_composant_only_dynRE2020.parquet")