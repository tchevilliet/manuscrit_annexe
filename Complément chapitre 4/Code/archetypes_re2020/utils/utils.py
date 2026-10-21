
import pandas as pd
import openpyxl
from openpyxl.styles import Font, Side
from openpyxl.styles.borders import Border
import bw2data as bd
import math
from datetime import datetime

from translate import Translator
import questionary
translator = Translator(to_lang="en", from_lang="fr")

DELIMITER = " @ "
SPECIAL_OPTIONS = {
    "NONE": "Aucun",
    "CUSTOM_SEARCH": "Faire ma recherche",
    "MORE_OPTIONS": "Plus de propositions"
}

# Constantes pour les étapes du cycle de vie
LIFE_CYCLE_STAGES = {
    "PRODUCTION_ALL": "A1-A4",
    "PRODUCTION": "A1-A3",
    "TRANSPORT_TO_SITE": "A4",
    "RENEWAL": "B4",
    "RENEWAL_PRODUCTION": "B4-production",
    "RENEWAL_TRANSPORT": "B4-transport",
    "END_OF_LIFE_ALL": "C2-C4",
    "END_OF_LIFE": "C3-C4",
    "EVACUATION": "C2"
}

# Constantes pour les recherches par défaut
DEFAULT_TRANSPORT_PROCESS = 'market for transport, freight, lorry, unspecified'
DEFAULT_TRANSPORT_CONVERSION = 0.1  # 100 km pour 1kg par défaut


# Constantes pour les colonnes du DataFrame
EXCHANGE_COLUMNS = [
    "name", "amount", "unit", "database", "step", 
    "categories", "location", "type", "uncertainty type", 
    "loc", "scale", "shape", "minimum", "maximum"
]

PROCESS_FIELDS_TO_COPY = ["name", "unit", "database", "location", "type"]

DATABASE_NAME_PATTERNS = {
    "ARCHETYPES_BB": "{year}-{month}-{day}-{hour}h{minute}_archetypes_RE2020_BB",
    "ARCHETYPES_MI": "{year}-{month}-{day}-{hour}h{minute}_archetypes_RE2020_MIB",
    "ARCHETYPES_PR": "{year}-{month}-{day}-{hour}h{minute}_archetypes_RE2020_PRB",
    "BERNOULLI": "{year}-{month}-{day}-{hour}h{minute}_bernoulli_RE2020",
    "BUILDINGS": "{year}-{month}-{day}-{hour}h{minute}_buildings_RE2020",
    "BUILDINGS_CONS":"{year}-{month}-{day}-{hour}h{minute}_buildings_cons_RE2020",
    "PROCESSES": "{year}-{month}-{day}-{hour}h{minute}_processes_RE2020"
}

LOTS = {
    "1": "VRD (Voirie et Réseaux Divers)",
    "2": "Fondations et infrastructure",
    "3": "Superstructure Maçonnerie",
    "4": "Couverture Étanchéité Charpente – Zinguerie",
    "5": "Cloisonnement Doublage – Plafonds suspendus Menuiseries intérieures",
    "6": "Façades et menuiseries extérieures",
    "7": "Revêtements des sols, murs et plafonds – Chape – Peintures",
    "8": "CVC (Chauffage Ventilation Refroidissement – ECS)",
    "9": "Installations sanitaires",
    "10": "Réseaux d’énergie (courant fort)",
    "11": "Réseaux de communication (courant faible)",
    "12": "Appareils élévateurs et autres équipements de transport intérieur",
    "13": "Équipement de production locale d’électricité",
    "Consommations_bois" : "Consommations - Bois",
    "Consommations_gaz" : "Consommations - Gaz",
    "consommations_electricite" : "Consommations - Électricité",
    "consommations_eau" : "Consommations - Eau",
    "consommations_reseau_uve" : "Consommations - Réseau de chaleur"

}

SOUS_LOTS = {
    "1.1": "Réseaux (extérieurs, jusqu’au domaine public)",
    "1.2": "Stockage",
    "1.3": "Aires de stationnement extérieures",
    "2.1": "Fondations",
    "2.2": "Murs et structures enterrées (escalier de cave, parc de stationnement…)",
    "2.3": "Parcs de stationnement en superstructure (hors garages individuels)",
    "3.1": "Éléments horizontaux – Planchers, dalles, balcons",
    "3.2": "Éléments horizontaux – Poutres",
    "3.3": "Éléments verticaux – Façades",
    "3.4": "Éléments verticaux – Refends",
    "3.5": "Éléments verticaux – Poteaux",
    "3.6": "Escaliers et rampes",
    "3.7": "Éléments d’isolation",
    "3.8": "Maçonneries diverses (appuis de baie)",
    "4.1": "Toitures terrasses",
    "4.2": "Toitures en pente",
    "4.3": "Éléments techniques de toiture (cheminées, lanterneaux, etc.)",
    "5.1": "Cloisons et portes intérieures",
    "5.2": "Doublages mur, matériaux de protection, isolants et membranes",
    "5.3": "Plafonds suspendus",
    "5.4": "Planchers surélevés",
    "5.5": "Menuiseries, métalleries et quincailleries",
    "6.1": "Revêtement, isolation et doublage extérieur",
    "6.2": "Portes, fenêtres, fermetures, protections solaires",
    "6.3": "Habillages et ossatures",
    "7.1": "Revêtement des sols",
    "7.2": "Revêtement des murs et plafonds",
    "7.3": "Éléments de décoration et revêtements des menuiseries",
    "8.1": "Équipements de production (chaud/froid) – hors cogénération",
    "8.2": "Systèmes de cogénération",
    "8.3": "Systèmes d’émission",
    "8.4": "Traitement de l’air et éléments de désenfumage",
    "8.5": "Réseaux et conduits",
    "8.6": "Stockage (combustibles)",
    "8.7": "Fluides frigorigènes",
    "9.1": "Éléments sanitaires et robinetterie",
    "9.2": "Canalisations, réseaux et systèmes de traitement",
    "10.1": "Réseaux électriques",
    "10.2": "Ensemble de dispositifs pour la sécurité",
    "10.3": "Éclairage intérieur (général)",
    "10.4": "Éclairage extérieur",
    "10.5": "Systèmes d’automatisation et de contrôle",
    "10.6": "Tableaux et appareillages",
    "11.1": "Réseaux électriques et de communications",
    "11.2": "Systèmes de sécurité (personnes et biens)",
    "11.3": "Installations techniques et appareillages",
    "12.1": "Ascenseurs, monte‑charges, escaliers mécaniques, nacelles de nettoyage",
    "13.1": "Installation dédiée à la production d’électricité (panneaux, onduleur, etc.)",
}

def get_existing_databases(keyword):
    """
    Récupère les bases de données existantes contenant un mot-clé.

    Args:
        keyword (str): Mot-clé à rechercher (insensible à la casse).

    Returns:
        list: Liste des noms de bases de données correspondantes.
    """
    return [
        db for db in list(sorted(bd.databases))
        if keyword.lower() in str(db).lower()
    ]


def generate_database_name(pattern_key):
    """
    Génère un nom de base de données avec horodatage.

    Args:
        pattern_key (str): Clé du pattern dans DATABASE_NAME_PATTERNS.

    Returns:
        str: Nom de base de données formaté avec date et heure.
    """
    now = datetime.today()
    pattern = DATABASE_NAME_PATTERNS[pattern_key]
    return pattern.format(
        year=now.year,
        month=now.month,
        day=now.day,
        hour=now.hour,
        minute=now.minute
    )


def select_or_create_database(keyword, pattern_key):
    """
    Sélectionne une base de données existante ou en crée une nouvelle.

    Args:
        keyword (str): Mot-clé pour identifier les bases existantes.
        pattern_key (str): Clé du pattern de nom dans DATABASE_NAME_PATTERNS.

    Returns:
        str: Nom de la base de données à utiliser.
    """
    existing_dbs = get_existing_databases(keyword)
    
    if existing_dbs:
        choice = select_from_list(
            f"Les bdd {existing_dbs} existent déjà, en écraser une ?",
            existing_dbs + ["Non"]
        )
        if choice != "Non":
            return choice
    
    return generate_database_name(pattern_key)

def select_source_file(intensite = "matières"):
    """
    Demande à l'utilisateur de sélectionner le fichier source.

    Returns:
        str: Chemin vers le fichier.
    """
    return questionary.path(
        f"Quel fichier utiliser pour les intensités {intensite} ?"
    ).ask()


def calculate_base_amount(activity):
    """
    Calcule la quantité de base d'une activité (taux de conversion / production amount).

    Args:
        activity (dict): Dictionnaire avec 'process' et 'taux_conversion'.

    Returns:
        float: flux de référence calculée.=
    """
    return activity["taux_conversion"] / activity['process']['production amount']


def adjust_amount_by_lifecycle_stage(stage_key, base_amount, renew_amount):
    """
    Ajuste la quantité selon l'étape du cycle de vie.

    Args:
        stage_key (str): Étape(s) du cycle de vie (ex: "A1-A3", "B4", "C2").
        base_amount (float): Flux de référence à ajuster.
        renew_amount (float): Quantité de renouvellement.

    Returns:
        float: Quantité ajustée selon l'étape.
    """
    if stage_key.startswith("B"):
        # Renouvellement : multiplier par la quantité à renouveler
        return base_amount * renew_amount
    elif stage_key.startswith("C"):
        # Fin de vie : négatif * quantité totale sur cycle de vie
        return -base_amount * (1.0 + renew_amount)
    else:
        # Production : quantité de base inchangée
        return base_amount


def create_row_from_activity(stage_key, activity, adjusted_amount):
    """
    Crée une ligne de données à partir d'une activité et de sa quantité ajustée.

    Args:
        stage_key (str): Clé de l'étape du cycle de vie.
        activity (dict): Dictionnaire avec 'process' et 'taux_conversion'.
        adjusted_amount (float): Quantité ajustée pour cette étape.

    Returns:
        dict: Dictionnaire représentant une ligne du DataFrame.
    """
    process_dict = activity['process'].as_dict()
    row = {field: process_dict[field] for field in PROCESS_FIELDS_TO_COPY}
    row["amount"] = adjusted_amount
    row["step"] = stage_key
    
    return row


def datadict_to_df(prod_dict, db, per=50, **kw):
    """
    Crée un DataFrame des échanges d'un procédé pour toutes les étapes du cycle de vie.

    Args:
        prod_dict (dict): Nomenclature INIES avec unité de l'uf et dve.
        db: Base de données brightway.
        per (int, optional): Période d'étude de référence en années. Par défaut 50.
        **kw: Arguments supplémentaires pour get_lc_activities().

    Returns:
        pandas.DataFrame: DataFrame avec colonnes name, amount, unit, database, step, etc.
                         DataFrame vide si aucune activité n'est trouvée.
    """
    activities = get_lc_activities(prod_dict, db, per, **kw)
    
    if not activities or len(activities) == 0:
        return pd.DataFrame()
    
    renew_amount = get_renew_amount(prod_dict, per)
    result_df = pd.DataFrame(columns=EXCHANGE_COLUMNS)
    
    for stage_key, activity in activities.items():
        print(activity['process'])
        
        # Calcul de la quantité ajustée
        base_amount = calculate_base_amount(activity)
        adjusted_amount = adjust_amount_by_lifecycle_stage(
            stage_key, base_amount, renew_amount
            )
        
        # Création de la ligne
        row = create_row_from_activity(stage_key, activity, adjusted_amount)
        row_df = pd.DataFrame({k: [v] for k, v in row.items()})
        
        result_df = pd.concat([result_df, row_df], ignore_index=True)
    
    return result_df


def create_no_border_style():
    """
    Crée un style de bordure vide pour les cellules Excel.

    Returns:
        Border: Style de bordure sans lignes.
    """
    side = Side(border_style=None)
    return Border(left=side, right=side, top=side, bottom=side)


def apply_meta_format(worksheet, start_row, num_rows, num_cols):
    """
    Applique le formatage "meta" à un bloc de cellules.
    
    Première ligne et dernière ligne en gras 12pt, corps en normal 9pt.

    Args:
        worksheet: Feuille de travail openpyxl.
        start_row (int): Ligne de début du bloc (index Excel, 1-based).
        num_rows (int): Nombre de lignes du DataFrame.
        num_cols (int): Nombre de colonnes du DataFrame.
    """
    # Première ligne (en-tête du bloc meta)
    worksheet.cell(row=start_row + 1, column=1).font = Font(
        name="Arial", bold=True, size=12
        )
    worksheet.cell(row=start_row + 1, column=2).font = Font(
        name="Arial", bold=True, size=12
        )
    
    # Dernière ligne du bloc meta
    last_row = start_row + num_rows
    worksheet.cell(row=last_row, column=1).font = Font(
        name="Arial", bold=True, size=12
        )
    
    # Corps du bloc (tout sauf première et dernière ligne)
    for row in range(start_row + 2, last_row):
        for col in range(1, num_cols + 1):
            worksheet.cell(row=row, column=col).font = Font(
                name="Arial", bold=False, size=9
                )


def apply_data_format(worksheet, start_row, num_rows, num_cols):
    """
    Applique le formatage "data" à un bloc de cellules.
    
    En-tête en gras 10pt sans bordures, corps en normal 9pt.

    Args:
        worksheet: Feuille de travail openpyxl.
        start_row (int): Ligne de début du bloc (index Excel, 1-based).
        num_rows (int): Nombre de lignes du DataFrame.
        num_cols (int): Nombre de colonnes du DataFrame.
    """
    no_border = create_no_border_style()
    header_row = start_row + 1
    
    # Titres de colonnes
    for col in range(1, num_cols + 1):
        cell = worksheet.cell(row=header_row, column=col)
        cell.font = Font(name="Arial", bold=True, size=10)
        cell.border = no_border
    
    # Corps du tableau
    for row in range(header_row + 1, header_row + num_rows + 1):
        for col in range(1, num_cols + 1):
            worksheet.cell(row=row, column=col).font = Font(
                name="Arial", bold=False, size=9
                )


def append_df(path, df, sheet="Sheet1", gap=2, format=None, **kw):
    """
    Ajoute un DataFrame à la fin d'un fichier Excel existant avec un formatage optionnel.

    Args:
        path (str): Chemin vers le fichier Excel à modifier.
        df (pandas.DataFrame): DataFrame à ajouter.
        sheet (str, optional): Nom de la feuille Excel. Par défaut "Sheet1".
        gap (int, optional): Nombre de lignes vides à laisser avant l'ajout. Par défaut 2.
        format (str, optional): Type de formatage ("meta" ou "data"). Par défaut None.
        **kw: Arguments supplémentaires passés à DataFrame.to_excel().
    """
    # Déterminer la position d'insertion
    wb = openpyxl.load_workbook(path)
    ws = wb[sheet]
    last_row = ws.max_row
    print(last_row)
    start_row = last_row + gap
    
    # Écrire le DataFrame
    with pd.ExcelWriter(
        path, engine="openpyxl", mode="a", if_sheet_exists="overlay"
        ) as writer:
        df.to_excel(writer, sheet_name=sheet, startrow=start_row, **kw)
    
    # Appliquer le formatage si spécifié
    if format:
        wb = openpyxl.load_workbook(path)
        ws = wb[sheet]
        num_rows = len(df)
        num_cols = len(df.columns)
        
        if format == "meta":
            apply_meta_format(ws, start_row, num_rows, num_cols)
        elif format == "data":
            apply_data_format(ws, start_row, num_rows, num_cols)
        
        wb.save(path)


def get_name(prod_dict,nb_nom=1) :
    """
    Retourne le nom d'une nomenclature inies, plus ou moins long en fonction de nb_nom.

    Args:
        prod_dict (dict): nomenclature INIES dans un dictionnaire, avec unité de l'uf et dve
        nb_nom (int, optional): nombre de sous-nomenclature mise dans le nom. Defaults to 1.

    Returns:
        string : "nom" du produit, c'est à dire la sous-nomenclature la plus petite qui n'est pas None, 
            que précède les nomenclatures supérieures si nb_nom >1
    """
    tmp = [v for k,v in prod_dict.items() if v is not None and "nomenclature" in k]
    if tmp :
        return "_".join(tmp[-nb_nom:])

    else :
        return False

def metadict_to_df(prod_dict) :
    """
    Crée un dataframe qui correspond à la table de métadonnées dans les bases
    format excel de brightway.

    Args:
        prod_dict (dict): nomenclature INIES dans un dictionnaire, avec unité de l'uf et dve.

    Returns:
        pandas Dataframe : dataframe contenant l'en-tête du procédé.
    """
    name_tmp = get_name(prod_dict,2)
    if name_tmp :
        tmp = pd.DataFrame(columns=['metadata','value'])
        tmp['metadata'] = ['Activity','categories','code','comment',"location"] +[k for k in prod_dict.keys() if "nomenclature" in k] + ['production amount','type','unit', 'Exchanges']
        tmp['value'] = [name_tmp,"custom_process",name_tmp.lower(), "un commentaire","FR"]+[v for k, v in prod_dict.items() if "nomenclature" in k]+ ['1','process', prod_dict['unite_uf_txt'],""]
        return tmp
    else :
        return pd.DataFrame()

def get_renew_amount(prod_dict,per=50) :
    """
    Renvoie la quantité de produit nécessaire à son renouvellement sur la
    période d'étude de référence. 

    Args:
        prod_dict (dict): nomenclature INIES dans un dictionnaire, avec unité de l'uf et dve.
        per (int, optional): période d'étude de référence choisie. Defaults to 50.

    Returns:
        float: vaut 0 si le produit a une durée de vie plus longue que la période d'étude.
            vaut l'entier ad hoc sinon.
    """
    dve = prod_dict['dve']
    if dve>=per :
        res = 0 
    else : 
        res = math.ceil(per/dve - 1)
    return res

def get_search_words(prod_dict):
    """
    Traduit et formate le nom du produit pour la recherche.
    """
    tmp = translator.translate(get_name(prod_dict, 2))
    res = [
        elem for liste in [e.split(" ") for e in tmp.split("_")] 
        for elem in liste
        ]
    return f"{res[-1]} {res[0]}"


def format_activity_display(activity):
    """
    Formate une activité pour l'affichage dans le menu de sélection.
    """
    return f"{activity['name']}{DELIMITER}{activity['location']}{DELIMITER}{activity['unit']}"


def parse_selection(selection_string):
    """
    Parse une sélection formatée pour extraire nom, location et unité.
    """
    return selection_string.split(DELIMITER)


def create_selection_message(prod_dict, step):
    """
    Crée le message de sélection standardisé.
    """
    return f"Pour {get_name(prod_dict, 2)}, en {prod_dict['unite_uf_txt']}, étape de {step}, sélectionner un procédé :"


def find_activity_by_name_location(activities, name, location):
    """
    Trouve une activité par son nom et sa localisation.
    """
    return [
        act for act in activities 
        if act['name'] == name and act['location'] == location
        ][0]


def ask_conversion_rate(default_conv):
    """
    Demande le taux de conversion à l'utilisateur.
    """

    conv = questionary.text(
        "taux de conversion (unité_ecoinvent*taux = unité_inies):",
        validate=lambda text: isinstance(eval(text), (float, int)),
        default=str(default_conv)
    ).ask()
    return float(conv)


def create_result_dict(activity, conversion_rate):
    """
    Crée le dictionnaire de résultat avec le process et le taux de conversion.
    """
    return {"process": activity, "taux_conversion": conversion_rate}


def ask_custom_search_keywords():
    """
    Demande à l'utilisateur de saisir des mots-clés de recherche.
    """
    return questionary.text(
        "Quels mots chercher ? (en anglais, séparés par des espaces)"
    ).ask()


def present_activities_for_selection(
    activities, 
    prod_dict, 
    step, 
    additional_options
    ):

    """
    Présente une liste d'activités à l'utilisateur et retourne la sélection.
    
    Args:
        activities: Liste des activités à présenter
        prod_dict: Dictionnaire du produit
        step: Étape du processus
        additional_options: Options supplémentaires à ajouter au menu
    
    Returns:
        Liste contenant [nom, location, unité] ou une option spéciale
    """
    choices = [
        format_activity_display(act) for act in activities
        ] + additional_options
    message = create_selection_message(prod_dict, step)
    return parse_selection(select_process(choices, message))


def handle_process_selection(activities, prod_dict, step, default_conv):
    """
    Gère la sélection d'un procédé et demande le taux de conversion si nécessaire.
    
    Returns:
        dict ou None: Dictionnaire avec 'process' et 'taux_conversion' ou None
    """
    selection = present_activities_for_selection(
        activities,
        prod_dict,
        step,
        [SPECIAL_OPTIONS["NONE"]]
    )
    
    if selection == [SPECIAL_OPTIONS["NONE"]]:
        return None
    
    conv = ask_conversion_rate(default_conv)
    activity = find_activity_by_name_location(activities, selection[0], selection[1])
    return create_result_dict(activity, conv)


def search_database(db, prod_dict, sub, **kw):
    """
    Effectue une recherche dans la base de données.
    
    Args:
        db: Base de données brightway
        prod_dict: Dictionnaire du produit
        sub: Terme de recherche personnalisé (optionnel)
        **kw: Arguments supplémentaires pour la recherche
    
    Returns:
        Liste des résultats de recherche
    """
    if sub:
        return db.search(sub, **kw)
    
    # Recherche avec 2 mots-clés
    results = db.search(get_search_words(prod_dict), **kw)
    
    # Si aucun résultat, recherche élargie avec 1 mot-clé
    if not results:
        name_en = translator.translate(get_name(prod_dict, 1))
        results = db.search(name_en, **kw)
    
    return results


def get_ei_process(prod_dict, db, step='production', sub=None, default_conv=1.0, **kw):
    """
    Traduit le nom du produit en anglais, le cherche dans brightway et 
    fait sélectionner les procédés et les taux de conversion qui sont retournés.

    Args:
        prod_dict (dict or string): nomenclature INIES dans un dictionnaire, avec unité de l'uf et dve. Sinon chaine de caractères.
        db: base de donnée format brightway
        step (str, optional): indique une étape dans la question posée. Defaults to 'production'.
        sub: terme de recherche personnalisé (optionnel)
        default_conv: taux de conversion par défaut
        **kw: arguments supplémentaires pour la recherche

    Returns:
        dict ou None: dictionnaire contenant une activité brightway à la clé 'process' et un taux de 
            conversion à la clé 'taux_conversion', ou None si aucune sélection.
    """
    # Recherche initiale dans la base de données
    initial_results = search_database(db, prod_dict, sub, **kw)
    
    # Présentation des résultats initiaux avec options
    selection = present_activities_for_selection(
        initial_results,
        prod_dict,
        step,
        [
        SPECIAL_OPTIONS["CUSTOM_SEARCH"], 
        SPECIAL_OPTIONS["MORE_OPTIONS"], 
        SPECIAL_OPTIONS["NONE"]
        ]
    )
    
    # Cas 1: Aucune sélection
    if selection == [SPECIAL_OPTIONS["NONE"]]:
        return None
    
    # Cas 2: Recherche personnalisée
    if selection == [SPECIAL_OPTIONS["CUSTOM_SEARCH"]]:
        keywords = ask_custom_search_keywords()
        search_results = db.search(keywords, limit=50, **kw)
        return handle_process_selection(
            search_results, prod_dict, step, default_conv
            )
    
    # Cas 3: Plus de propositions
    if selection == [SPECIAL_OPTIONS["MORE_OPTIONS"]]:
        name_en = translator.translate(get_name(prod_dict, 1))
        expanded_results = db.search(name_en, limit=50, **kw)
        
        expanded_selection = present_activities_for_selection(
            expanded_results,
            prod_dict,
            step,
            [SPECIAL_OPTIONS["CUSTOM_SEARCH"], SPECIAL_OPTIONS["NONE"]]
        )
        
        # Sous-cas 3a: Aucune sélection
        if expanded_selection == [SPECIAL_OPTIONS["NONE"]]:
            return None
        
        # Sous-cas 3b: Recherche personnalisée depuis "Plus de propositions"
        if expanded_selection == [SPECIAL_OPTIONS["CUSTOM_SEARCH"]]:
            keywords = ask_custom_search_keywords()
            search_results = db.search(keywords, limit=50, **kw)
            return handle_process_selection(
                search_results, prod_dict, step, default_conv
                )
        
        # Sous-cas 3c: Sélection d'une activité
        conv = ask_conversion_rate(default_conv)
        activity = find_activity_by_name_location(
            expanded_results, expanded_selection[0], expanded_selection[1]
            )
        return create_result_dict(activity, conv)
    
    # Cas 4: Sélection directe d'une activité
    conv = ask_conversion_rate(default_conv)
    activity = find_activity_by_name_location(
        initial_results, selection[0], selection[1]
        )
    return create_result_dict(activity, conv)


def is_market_process(activity):
    """
    Vérifie si une activité est une donnée de marché (contient "market for").

    Args:
        activity (dict): Activité avec clé 'process'.

    Returns:
        bool: True si donnée de marché, False sinon.
    """
    process_name = str(activity['process'].as_dict()['name'].lower())
    return "market for" in process_name


def get_transport_process(prod_dict, db, step_description, **kw):
    """
    Récupère le procédé de transport par camion par défaut.

    Args:
        prod_dict (dict): Dictionnaire du produit INIES.
        db: Base de données brightway.
        step_description (str): Description de l'étape de transport.
        **kw: Arguments supplémentaires pour get_ei_process().

    Returns:
        dict ou None: Procédé de transport avec taux de conversion, ou None.
    """
    return get_ei_process(
        prod_dict,
        db,
        step=step_description,
        sub=DEFAULT_TRANSPORT_PROCESS,
        default_conv=DEFAULT_TRANSPORT_CONVERSION,
        **kw
    )


def add_production_activities(activities_dict, prod_dict, db, **kw):
    """
    Ajoute les activités de production (A1-A3 ou A1-A4) au dictionnaire.
    
    Si donnée de marché : A1-A4 (production + transport).
    Sinon : A1-A3 (production) + A4 (transport séparé).

    Args:
        activities_dict (dict): Dictionnaire des activités à enrichir (modifié en place).
        prod_dict (dict): Dictionnaire du produit INIES.
        db: Base de données brightway.
        **kw: Arguments supplémentaires pour get_ei_process().
    """
    production_activity = get_ei_process(
        prod_dict,
        db,
        step="production (et transport sur site si donnée de marché)",
        **kw
    )
    
    if not production_activity:
        return
    
    if is_market_process(production_activity):
        activities_dict[LIFE_CYCLE_STAGES["PRODUCTION_ALL"]] = production_activity
    else:
        activities_dict[LIFE_CYCLE_STAGES["PRODUCTION"]] = production_activity
        activities_dict[LIFE_CYCLE_STAGES["TRANSPORT_TO_SITE"]] = get_transport_process(
            prod_dict,
            db,
            step_description="transport sur site",
            **kw
        )


def add_renewal_activities(activities_dict, prod_dict, db, **kw):
    """
    Ajoute les activités de renouvellement (B4) au dictionnaire.
    
    Si donnée de marché : B4 (renouvellement + transport).
    Sinon : B4-production + B4-transport (séparés).

    Args:
        activities_dict (dict): Dictionnaire des activités à enrichir (modifié en place).
        prod_dict (dict): Dictionnaire du produit INIES.
        db: Base de données brightway.
        **kw: Arguments supplémentaires pour get_ei_process().
    """
    renewal_activity = get_ei_process(
        prod_dict,
        db,
        step="renouvellement (et transport sur site si donnée de marché)",
        **kw
    )
    
    if not renewal_activity:
        return
    
    if is_market_process(renewal_activity):
        activities_dict[LIFE_CYCLE_STAGES["RENEWAL"]] = renewal_activity
    else:
        activities_dict[LIFE_CYCLE_STAGES["RENEWAL_PRODUCTION"]] = renewal_activity
        activities_dict[LIFE_CYCLE_STAGES["RENEWAL_TRANSPORT"]] = get_transport_process(
            prod_dict,
            db,
            step_description="transport sur site",
            **kw
        )


def add_end_of_life_activities(activities_dict, prod_dict, db, **kw):
    """
    Ajoute les activités de fin de vie (C2-C4) au dictionnaire.
    
    Si donnée de marché : C2-C4 (évacuation + traitement).
    Sinon : C3-C4 (traitement) + C2 (évacuation séparée).

    Args:
        activities_dict (dict): Dictionnaire des activités à enrichir (modifié en place).
        prod_dict (dict): Dictionnaire du produit INIES.
        db: Base de données brightway.
        **kw: Arguments supplémentaires pour get_ei_process().
    """
    end_of_life_activity = get_ei_process(
        prod_dict,
        db,
        step="fin de vie (et évacuation depuis le site si donnée de marché)",
        **kw
    )
    
    if not end_of_life_activity:
        return
    
    if is_market_process(end_of_life_activity):
        activities_dict[LIFE_CYCLE_STAGES["END_OF_LIFE_ALL"]] = end_of_life_activity
    else:
        activities_dict[LIFE_CYCLE_STAGES["END_OF_LIFE"]] = end_of_life_activity
        activities_dict[LIFE_CYCLE_STAGES["EVACUATION"]] = get_transport_process(
            prod_dict,
            db,
            step_description="évacuation",
            **kw
        )


def get_lc_activities(prod_dict, db, per=50, **kw):
    """
    Construit un dictionnaire des activités brightway pour le cycle de vie complet du produit.
    
    Collecte interactivement les procédés pour les étapes A1-A4 (production/transport),
    B4 (renouvellement) et C2-C4 (fin de vie/évacuation).

    Args:
        prod_dict (dict): Nomenclature INIES avec 'unite_uf_txt' et données pour get_name().
        db: Base de données brightway.
        per (int, optional): Période d'étude de référence en années. Par défaut 50.
        **kw: Arguments supplémentaires pour get_ei_process().

    Returns:
        dict ou None: Dictionnaire avec clés = étapes de vie (ex: "A1-A3", "B4") 
                     et valeurs = dict{'process': activité, 'taux_conversion': float}.
                     Retourne None si le nom du produit est vide.
    """
    product_name = get_name(prod_dict, 2)
    print(product_name)
    
    if not product_name:
        return None
    
    activities = {}
    
    # Étapes A1-A4 : Production et transport sur site
    add_production_activities(activities, prod_dict, db, **kw)
    
    # Étape B4 : Renouvellement
    add_renewal_activities(activities, prod_dict, db, **kw)
    
    # Étapes C2-C4 : Fin de vie et évacuation
    add_end_of_life_activities(activities, prod_dict, db, **kw)
    
    return activities



def select_process(list_process, message="Sélectionner un process :"):
    """
    Permet de sélectionner un texte parmi ceux proposés.

    Args:
        list_process (list): liste de strings.
        message (str, optional): Question posée. Defaults to "Sélectionner un process :".

    Returns:
        string: la chaine de caractère sélectionnée
    """
    answer = questionary.select(
        message,
        choices=list_process,
        use_arrow_keys=True,
        qmark="?",
        pointer=">"
    ).ask()
    return answer


def select_from_list(message, choices):
    """
    Affiche un menu de sélection interactif.

    Args:
        message (str): Message de sélection.
        choices (list): Liste des choix disponibles.

    Returns:
        str: Choix sélectionné par l'utilisateur.
    """
    return questionary.select(
        message,
        choices=choices,
        use_arrow_keys=True,
        qmark="?",
        pointer=">"
    ).ask()

def select_database(message = "Select Database"):
    """
    Sélectionne une base de données brightway.

    Args:
        message (str): Message de sélection.

    Returns:
        bd.Database: Base de données brightway sélectionnée.
    """
    db_name = select_from_list(message, list(sorted(bd.databases)))
    return bd.Database(db_name), db_name


def select_project():
    """
    Sélectionne un projet brightway et le définit comme projet courant.

    Returns:
        str: Nom du projet sélectionné.
    """
    project_name = select_from_list(
        "Select project",
        [p.name for p in list(bd.projects)]
    )
    bd.projects.set_current(project_name)
    return project_name
