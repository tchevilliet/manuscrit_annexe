import polars as pl
from tqdm import tqdm

from archetypes_re2020.config import RAW_DATA_DIR, INTERIM_DATA_DIR

# Constantes pour les chemins de fichiers
INPUT_PATHS = {
    "COMPONENTS": RAW_DATA_DIR / "composant_open_data_0525.parquet",
    "BUILDINGS":  RAW_DATA_DIR / "202505_export_batiments_daact.csv"
}

OUTPUT_PATHS = {
    "AUGMENTED_QUANTITIES": INTERIM_DATA_DIR / "quantites_augmentees.parquet",
    "BUILDINGS_WO_EXTREME_OUTLIER" : INTERIM_DATA_DIR / "buidings_wo_extreme_outlier.csv"
}

# Colonnes de nomenclature INIES
NOMENCLATURE_COLUMNS = [
    'nomenclature_inies_1',
    'nomenclature_inies_2', 
    'nomenclature_inies_3',
    'nomenclature_inies_4',
    'nomenclature_inies_5'
]

# Colonnes pour les jointures
JOIN_KEYS = ['projet_id', 'batiment_index']

BUILDINGS_FIELDS_TO_JOIN = [
    'usage_principal_1_txt',
    'sref',
    'puissance_thermique_max_restituable_ch_1',
    'puissance_thermique_max_restituable_ch_2'
    ]

UNIT_REPLACEMENT = {"ml": "m"}
DEFAULT_BUILDING_UNIT = "m2"
DEFAULT_LOCATION = "FR"
DATABASE_NAME_PATTERN = "{year}-{month}-{day}-{hour}h{minute}_batiments_RE2020"


def load_parquet_data(path):
    """
    Charge les données depuis un fichier parquet.

    Args:
        path (str): Chemin vers le fichier parquet.

    Returns:
        pl.DataFrame: DataFrame Polars avec les données.
    """
    lazy_df = pl.scan_parquet(path)
    return lazy_df.collect()


def load_building_data(path):
    """
    Charge les données de bâtiments depuis un fichier CSV.

    Args:
        path (str): Chemin vers le fichier CSV des bâtiments.

    Returns:
        pl.DataFrame: DataFrame Polars avec les données de bâtiments.
    """
    return pl.read_csv(source=path, ignore_errors=True)


def get_non_compliant_building_ids(df_buildings):
    """
    Récupère les IDs des bâtiments non conformes RE2020.

    Args:
        df_buildings (pl.DataFrame): DataFrame des bâtiments.

    Returns:
        pl.Series: Série contenant les IDs structurés des bâtiments non conformes.
    """
    non_compliant = df_buildings.filter(
        pl.col("batiment_conforme_re2020") == False
    )
    return non_compliant.with_columns(
        pl.struct(JOIN_KEYS).alias('ID')
    )['ID']


def remove_non_compliant_buildings(df_quantities, df_buildings, non_compliant_ids):
    """
    Supprime les bâtiments non conformes des deux DataFrames.

    Args:
        df_quantities (pl.DataFrame): DataFrame des quantités.
        df_buildings (pl.DataFrame): DataFrame des bâtiments.
        non_compliant_ids (pl.Series): IDs des bâtiments non conformes.

    Returns:
        tuple: (df_quantities_filtered, df_buildings_filtered)
    """
    for building_id in tqdm(non_compliant_ids, desc="Removing non-compliant buildings"):
        df_buildings = df_buildings.filter(
            pl.struct(JOIN_KEYS) != building_id
        )
        df_quantities = df_quantities.filter(
            pl.struct(JOIN_KEYS) != building_id
        )
    
    return df_quantities, df_buildings


def add_nomenclature_struct(df_quantities):
    """
    Ajoute une colonne structurée contenant toutes les nomenclatures INIES.

    Args:
        df_quantities (pl.DataFrame): DataFrame des quantités.

    Returns:
        pl.DataFrame: DataFrame avec colonne 'nomenclatures' ajoutée.
    """
    return df_quantities.with_columns(
        nomenclatures=pl.struct(NOMENCLATURE_COLUMNS)
    )


def join_building_fields(df_quantities, df_buildings, fields_to_join):
    """
    Joint les champs sélectionnés du DataFrame bâtiments au DataFrame quantités.

    Args:
        df_quantities (pl.DataFrame): DataFrame des quantités.
        df_buildings (pl.DataFrame): DataFrame des bâtiments.
        fields_to_join (list): Liste des colonnes à joindre (en plus des clés de jointure).

    Returns:
        pl.DataFrame: DataFrame des quantités enrichi.
    """
    result = df_quantities
    
    for field in fields_to_join:
        columns_to_select = JOIN_KEYS + [field]
        result = result.join(
            df_buildings.select(columns_to_select),
            on=JOIN_KEYS,
            how='left'
        )
    
    return result


def calculate_material_intensity(df_quantities):
    """
    Crée une colonne avec l'intensité matière 
    (quantité par surface de référence).

    Args:
        df_quantities (pl.DataFrame): DataFrame des quantités 
        avec colonnes 'quantite' et 'sref'.

    Returns:
        pl.DataFrame: DataFrame avec colonne 'quant_surf' ajoutée.
    """
    return df_quantities.with_columns(
        quant_surf=pl.col('quantite') / pl.col('sref')
    )

def standardize_units(df):
    """
    Standardise les unités fonctionnelles (remplace 'ml' par 'm').

    Args:
        df (pl.DataFrame): DataFrame avec colonne 'unite_uf_txt'.

    Returns:
        pl.DataFrame: DataFrame avec unités standardisées.
    """
    return df.with_columns(
        unite_uf_txt = pl.col("unite_uf_txt").replace(UNIT_REPLACEMENT)
        )


def add_nomenclature_with_unit_and_dve(df):
    """
    Ajoute deux colonnes : l'une combinant nomenclatures et unité et
    l'autre combinant nomenclatures, unité et durée de vie estimée (dve).

    Args:
        df (pl.DataFrame): DataFrame avec colonnes 'nomenclatures' et
            'unite_uf_txt'.

    Returns:
        pl.DataFrame:  DataFrame avec colonnes 
        "nomenclatures_UF" et "nomenclatures_UF_dve" ajoutées.
    """
    return df.with_columns(
        nomenclatures_UF=pl.col("nomenclatures").struct.with_fields(
            unite_uf_txt=pl.col("unite_uf_txt")
            ),
        nomenclatures_UF_dve=pl.col("nomenclatures").struct.with_fields(
            unite_uf_txt=pl.col("unite_uf_txt"),
            dve=pl.col("dve").cast(pl.Float64)
            )
        )


def fill_null_quantities(df):
    """
    Remplace les valeurs None par 0 dans la colonne des quantités surfaciques.

    Args:
        df (pl.DataFrame): DataFrame avec colonne 'quant_surf'.

    Returns:
        pl.DataFrame: DataFrame avec valeurs nulles remplacées.
    """
    return df.with_columns(
        pl.col("quant_surf").fill_null(0)
    )

def process_building_data():
    """
    1. Charge les données de composants et bâtiments
    2. Identifie et supprime les bâtiments non conformes RE2020
    3. Joint les champs d'usage et surface de référence
    4. Ajoute une colonne avec nomenclatures regroupées en Struct
    5. Ajoute une colonne avec l'intensité matière
    6. Standardise les unités
    7. Ajoute des colonnes avec unite et dve adjoint à la nomenclature
    8. Sauvegarde le résultat
    """
    # Chargement des données
    df_quantities = load_parquet_data(INPUT_PATHS["COMPONENTS"])
    df_buildings = pl.read_csv(
        source=INPUT_PATHS["BUILDINGS"], ignore_errors=True
        )
    
    # Filtrage des bâtiments non conformes
    non_compliant_ids = get_non_compliant_building_ids(df_buildings)
    df_quantities, df_buildings = remove_non_compliant_buildings(
        df_quantities, 
        df_buildings, 
        non_compliant_ids
    )
    
    # Enrichissement des quantités avec les données bâtiments
    df_quantities = add_nomenclature_struct(df_quantities)
    df_quantities = join_building_fields(
        df_quantities,
        df_buildings,
        BUILDINGS_FIELDS_TO_JOIN
    )
    
    # Calcul et ajout de l'intensité matière
    df_quantities = calculate_material_intensity(df_quantities)
    
    #Standardisation unités
    df_quantities = standardize_units(df_quantities)

    #Ajouts des colonnes d'identification
    df_quantities = add_nomenclature_with_unit_and_dve(df_quantities)

    #Remplacement des None par valeurs nulles
    df_quantities = fill_null_quantities(df_quantities)

    # Sauvegarde
    df_quantities.write_parquet(OUTPUT_PATHS["AUGMENTED_QUANTITIES"])
    
    return df_quantities



if __name__ == "__main__":
    df_result = process_building_data()
    print(f"Traitement terminé. {len(df_result)} lignes sauvegardées.")