import polars as pl
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from cmcrameri import cm


import questionary
from tqdm import tqdm
from archetypes_re2020.data.source import load_parquet_data, OUTPUT_PATHS
from archetypes_re2020.config import FIGURES_DIR, TABLES_DIR

#pour gestion des dates
from datetime import datetime, date, time 

### Import du fichier parquet résultatnt de creation_source.py
df_source = load_parquet_data(OUTPUT_PATHS["AUGMENTED_QUANTITIES"])

### Quelques modifications sur le df

print('On remplace ml par m')
df_modif = df_source.with_columns(
    pl.when(pl.col("unite_uf_txt") == "ml")
      .then(pl.lit("m")) # pl.lit sinon "m" est pris pour une colonne
      .otherwise(pl.col("unite_uf_txt"))
      .alias("unite_uf_txt")
)
print(
    "On crée une colonne nomenclatures_UF",
    "\n","qui ajoute au dictionnaire l'unité"
    )

df_modif = df_modif.with_columns(
    nomenclatures_UF=pl.col("nomenclatures").struct.with_fields(
        unite_uf_txt=pl.col("unite_uf_txt"),
    ),
    nomenclatures_UF_dve=pl.col("nomenclatures").struct.with_fields(
        unite_uf_txt=pl.col("unite_uf_txt"),
        dve=pl.col("dve").cast(pl.Float64),
    ),
)

print(
    "On remplace les None par 0",
    "\n","dans la colonne de quantitées surfaciques"
    )
df_modif = df_modif.with_columns(
    pl.col("quant_surf").fill_null(0)
)

print(
    "On crée les listes d'usages","\n",
    "et de produits à partir du dataframe"
    )
# On donne le choix de ne garder qu'une partie des usages
usages = df_modif.select(
    pl.col("usage_principal_1_txt").unique()
    ).drop_nulls()["usage_principal_1_txt"]

usages_to_keep = questionary.checkbox(
    "Quels usages sont à considérer ?",
    choices = list(usages)
).ask()
usages = usages.filter(usages.is_in(usages_to_keep))

#On filtre le dataframe pour ne garder que les usages choisis
df_modif = df_modif.filter(
    pl.col("usage_principal_1_txt").is_in(usages)
)

produits = df_modif.select(
    pl.col("nomenclatures_UF_dve").unique()
    ).drop_nulls()["nomenclatures_UF_dve"]
# Conversion des produits en str
# La version optimisée produits.cast(pl.String) ne marche pas ici
produits = produits.map_elements(
    lambda x : str(x),return_dtype=pl.String
    ) 


print("Création des listes pour le tracé")

# seuils en Serie
X = pl.Series(
    "Seuil_apparition_en_nb_de_batiments",
    [a / 1000 for a in range(0, 200, 2)]
    )

# décompte du nombre de bâtiments pour chaque usage
nb_bat_per_usage = (
    df_modif
    .group_by("usage_principal_1_txt")
    .agg(
        nb_bat=pl.struct("projet_id", "batiment_index").n_unique()
    )
)

# décompte du nombre d'apparition de chaque produits pour chaque usage
counts_per_usage_prod = (
    df_modif
    .group_by(["usage_principal_1_txt", "nomenclatures_UF_dve"])
    .agg(
        nb_bat_prod=pl.struct("projet_id", "batiment_index").n_unique()
    )
)

# regroupement des dataframes
df_counts = counts_per_usage_prod.join(
    nb_bat_per_usage,
    on="usage_principal_1_txt",
    how="left",
)
# Pour chaque usage, et chaque seuil s, décompte du nombre de produits
# qui apparaissent plus de s fois
res = (
    df_counts
    .join(X.to_frame(), how="cross")
    .filter(
        pl.col("nb_bat_prod") 
        >= pl.col("Seuil_apparition_en_nb_de_batiments")*pl.col("nb_bat")
    )
    .group_by(
        ["usage_principal_1_txt", "Seuil_apparition_en_nb_de_batiments"]
    )
    .agg(
        Nombre_de_procedes=pl.len()
    )
    .rename({"usage_principal_1_txt": "Usage"})
)

###### Fonction qui donne le y pour un x donné
def y_at_x(
        x, df, usage, col_x="Seuil_apparition_en_nb_de_batiments",
        col_y="Nombre_de_procedes",col_usage = "Usage") :

    tmp = df.filter(pl.col(col_usage) == usage)
    Xlist = tmp.get_column(col_x).to_numpy()
    Ylist = tmp.get_column(col_y).to_numpy()

    sort_indices = np.argsort(Xlist)
    X_sorted = Xlist[sort_indices]
    Y_sorted = Ylist[sort_indices]

    return np.interp(x,X_sorted,Y_sorted)


##### On demande la part acceptable de bâtiments manqués
seuil_bat = questionary.text(
    message='Quel pourcentage de bâtiments manqués est acceptable ?',
    default= '5',
    validate = lambda x: isinstance(eval(x), int)
    ).ask()
seuil_bat = eval(seuil_bat)/100


#####Tracé et export du tableau
now = datetime.today()
today = f"{now.year}-{now.month}-{now.day}-{now.hour}h{now.minute}"

nb_procedes_to_model = {u : y_at_x(seuil_bat,res,u) for u in usages}

df_counts_filtered = df_counts.filter(pl.col("nb_bat_prod") >= seuil_bat*pl.col("nb_bat"))


df_counts_filtered["nomenclatures_UF_dve"].value_counts().write_excel(f"{TABLES_DIR}/{today}_process_to_model.xlsx")

print(nb_procedes_to_model)

plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
})

fig, ax = plt.subplots()
cmap = cm.berlin

# On fait en sorte de pouvoir éviter la zone centrale de la colormap si besoin (genre vik)
N = len(nb_procedes_to_model.keys())

if N%2 == 0 :
    n_left = N // 2
else :
    n_left = N // 2 +1


left_range = np.linspace(0.1, 0.5, n_left)
right_range = np.linspace(0.5, 0.9, n_left -1 )

colors = cmap(np.concatenate([left_range, right_range]))

colors = cmap(np.linspace(0.1,0.9,N))
to_graph = res.filter(
   pl.col("Seuil_apparition_en_nb_de_batiments") < 0.1
)
sns.lineplot(
    data = to_graph,
    x="Seuil_apparition_en_nb_de_batiments",
    y="Nombre_de_procedes",
    hue="Usage",
    #hue_order= ["Maison individuelle ou accolée", "Bureau","Logement collectif", "Enseignement primaire","Enseignement secondaire (partie jour)"],
    hue_order= ["Maison individuelle ou accolée", "Bureau","Logement collectif"],
    palette= sns.color_palette(colors)
    ) 

ax.set_ylim(bottom = 0)
# ax.set_xlim(left=0)
yticks = [100*i for i in range(16)]
ax.set_yticks(yticks)
ax.set_yticklabels(yticks)
xticks = [0.01*i for i in range(10)]
ax.set_xticks(xticks)
ax.set_xticklabels(xticks)

ax.grid(color = "0.9",linewidth = 0.5)
ax.vlines(
   x=seuil_bat,
   ymin = 0,
   ymax = np.max(list(nb_procedes_to_model.values())),
   colors="black",linestyles= ":"
   )
ax.set_ylabel("Nombre de composants \n utilisé par un nombre de bâtiments supérieur au seuil")
ax.set_xlabel("Seuil d'occurence du composant")
fig.savefig(f"{FIGURES_DIR}/{today}_nb_procedes_a_modeliser_graph.pdf",dpi=300)
plt.clf()
