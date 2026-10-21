import polars as pl
import seaborn as sns
import matplotlib.pyplot as plt
from cmcrameri import cm
import numpy as np

plt.clf()
plt.rcParams.update({
    "text.usetex": True,
    "text.latex.preamble": r"\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.serif": "Computer Modern",
    "font.size": 10
})
cmap = cm.berlin



mapping = {'Generic LW Concrete' :'Generic LW Concrete',
'Enduit ciment 1 cm' : "Enduit ciment",
'EPDM' :'EPDM',
'plasterboard' : "Plaque de plâtre",
'water_use' : "Consommation d'eau",
'Gravier 5cm' : "Gravier",
'Water Systems' : "Consommations systèmes hydrauliques"  ,
'XPS 22cm' : "Polystyrène extrudé",
'Double vitrage U = 1.2' : "Fenêtre",
'Pare-Vapeur' : "Pare-vapeur",
'XPS 16cm' : "Polystyrène extrudé",
'mineral wool 3 cm' : "Laine minérale",
'mineral wool 15 cm': "Laine minérale",
'Electric Equipment' : "Consommations équipements",
'Generic Acoustic Tile' : 'Generic Acoustic Tile',
'Heating' : "Besoins de chauffage",
'Interior Lighting' : "Consommations éclairage",
'reinforced concrete 20 cm' : "Béton armé",
'Cooling' : "Besoins de climatisation"}



df = pl.concat(
    [
        pl.read_excel("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/tables/Castro - Portzamparc.xlsx"),
        pl.read_excel("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/tables/Huet - Portzamparc.xlsx"),
        pl.read_excel("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/tables/Portzamparc.xlsx")
    ]
        )

df = df.with_columns(
    pl.when(pl.col("material").str.contains("consommation",literal = True))
    .then(pl.col("type"))
    .otherwise(pl.col("material"))
    .alias("category")
)

df = df.with_columns(cat_replaced=pl.col("category").replace(mapping))

df = df.with_columns(
    pl.when(pl.col("type").str.contains_any(["composant", "water_use"]))
    .then(pl.col("mass_kg"))
    .otherwise(pl.col("energy_kWh"))
    .alias("valeur")
)

df = df.group_by(["variante","cat_replaced"]).agg(pl.col("valeur").sum())

df = df.with_columns(
    result=(
        pl.col("valeur")
        / pl.col("valeur").filter(pl.col("variante") == "Portzamparc").first().over("cat_replaced")
    )
)




# print(res)

n= len(df["variante"].unique())-1
palette = list(cmap(np.linspace(0.1,0.9,n)))

fig,ax = plt.subplots(figsize = (7,5))

to_graph = df.filter(
    pl.col("variante")!="Portzamparc",
    # ~pl.col("cat_replaced").str.contains_any(["Generic","Consommation"])
    pl.col("cat_replaced").str.contains_any(["Consommation","Besoin"])
    ).sort("cat_replaced")

hue_order = sorted(to_graph["variante"].unique().to_list())
sns.barplot(data = to_graph ,x="cat_replaced",y = "result",hue = "variante",palette = palette,hue_order = hue_order)

ax.grid(visible=True,which="both",axis = 'y',color = "lightgray", linestyle = "--",zorder=0)
ax.set_axisbelow(True)

ax.set_ylabel("Écart relatif au projet de Portzamparc")
# ax.set_xlabel("Matériaux")
ax.set_xlabel("Besoin ou consommation")
ax.legend(loc = "lower center",bbox_to_anchor=(0.5,1))
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
# plt.show()
plt.savefig("/home/thibault.chevilliet@enpc.fr/Documents/2607_acv_maquette/acv_from_maquette/report/figures/comparaison_ipps_consos.pdf",dpi =300)

