import polars as pl
import numpy as np
from pathlib import Path

from tqdm import tqdm
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.decomposition import PCA, KernelPCA

from datetime import datetime

from archetypes_re2020.config import PROCESSED_DATA_DIR
from archetypes_re2020.data.remove_extreme_outliers import outliers


# on construit la matrice E avec les erreurs sur tous les composants (colonnes), pour tous le bâtiments(lignes)

df_erreurs =  pl.read_parquet(f"{PROCESSED_DATA_DIR}/Erreurs/final_demand_vector_error.parquet")

usage = "Logement collectif"

df = df_erreurs.filter(pl.col("usage")==usage)
df = df.with_columns(
    normalized_error = pl.col("error")/pl.col("theta")
)
df = outliers(df,"normalized_error").filter(
    pl.col("extreme_outliers")==False,
    pl.col("mild_outliers")==False
    )

composants = df["code_composant"].unique()
batiments = df["code_bat"].unique()
df_E = df_E.with_columns(

)
df_E = df.pivot("code_composant", index="code_bat", values="error").fill_null(0.)

import polars.selectors as cs

df_E_cent_red = df_E.with_columns(
    (cs.numeric() - cs.numeric().mean()) / cs.numeric().std()
)

row_labels = df_E_cent_red["code_bat"].to_list()
col_labels = df_E_cent_red.columns[1:]

E = df_E_cent_red.drop("code_bat").to_numpy()

pca = PCA(n_components=250,svd_solver='arpack').fit(E)
cumsum = np.cumsum(pca.explained_variance_ratio_)
thres = [0.9,0.95]
n_components = {t: next(i+1 for i,v in enumerate(cumsum) if v>=t) for t in thres}

E_cr_proj = pca.transform(E)
df_E_cr_proj = pl.DataFrame(E_cr_proj)


# fig, ax = plt.subplots()

# sns.pairplot(df_E_cr_proj.to_pandas())



