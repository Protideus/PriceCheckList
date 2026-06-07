import os
import json
import re
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
DATA_DIR = "./data"
# Tes 7 vraies listes PCL
CATEGORIES = ["warframes", "armes", "mods", "arcanes", "equipements", "reliques", "ressources"]

def load_all_pcl_items():
    """
    Étape 1 : Lit les 7 fichiers _table.json pour reconstituer 
    la liste globale des items affichés sur PCL.
    """
    all_items = []
    for cat in CATEGORIES:
        file_path = os.path.join(DATA_DIR, f"{cat}_table.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                items_liste = json.load(f)
                for item in items_liste:
                    all_items.append({
                        "id": item.get("id", ""),
                        "n_fr": item.get("n_fr", ""),
                        "n_en": item.get("n_en", ""),
                        "categorie": cat
                    })
    return all_items

def load_google_sheet_tips():
    """
    Étape 2 : Connexion sécurisée au Sheets via le compte de service.
    """
    try:
        credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if not credentials_json:
            print("❌ Erreur : Le secret GOOGLE_SERVICE_ACCOUNT_JSON est introuvable.")
            return []
            
        creds_dict = json.loads(credentials_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        
        client = gspread.authorize(creds)
        sheet = client.open_by_key("1uvpQvU_ctXYY0bSdNmdptaw8NpyQwB8wj-XUPsfDAw4").sheet1
        
        all_rows = sheet.get_all_values()
        return all_rows[5:] # Ligne 6+
    except Exception as e:
        print(f"❌ Échec de la récupération du Google Sheets : {str(e)}")
        return []

def extraire_filtre_et_nom(saisie_expert):
    """
    Étape 3 : Sépare le nom de l'item et traduit le mot entre parenthèses
    vers l'une des 7 vraies catégories de PCL au pluriel.
    """
    match_parenthese = re.search(r'\((.*?)\)', saisie_expert)
    
    cat_cible = None
    if match_parenthese:
        mot_expert = match_parenthese.group(1).lower().strip()
        
        # Dictionnaire de correspondance nettoyé et sans conflit
        correspondances = {
            "warframe": "warframes", "warframes": "warframes",
            "arme": "armes", "armes": "armes", "principal": "armes", "secondaire": "armes", "mêlée": "armes", "melee": "armes",
            "mod": "mods", "mods": "mods", "riven": "mods", "rivens": "mods",
            "arcane": "arcanes", "arcanes": "arcanes",
            "equipement": "equipements", "équipement": "equipements", "equipements": "equipements", "équipements": "equipements", 
            "sentinelle": "equipements", "sentinelles": "equipements", "archwing": "equipements", "archwings": "equipements", 
            "necramech": "equipements", "nécramech": "equipements",
            "relique": "reliques", "reliques": "reliques", "lith": "reliques", "meso": "reliques", "neo": "reliques", "axi": "reliques", "requiem": "reliques",
            "ressource": "ressources", "ressources": "ressources", "sculpture": "ressources", "sculptures": "ressources", "ayatan": "ressources", "lentille": "ressources", "lentilles": "ressources", "cle": "ressources", "clé": "ressources", "composant": "ressources", "composants": "ressources"
        }
        
        if mot_expert in correspondances:
            cat_cible = correspondances[mot_expert]
        else:
            print(f"⚠️ Catégorie inconnue entre parenthèses : '{mot_expert}'. Le robot cherchera partout.")

    nom_nettoye = re.sub(r'\(.*?\)', '', saisie_expert).replace("-", " ").strip().lower()
    return nom_nettoye, cat_cible

def match_mots(saisie_nettoyee, item_pcl):
    """Vérifie si les mots de l'expert matchent le slug, le nom FR ou le nom EN."""
    mots_expert = set(re.findall(r'\b\w+\b', saisie_nettoyee))
    
    texte_item = f"{item_pcl['id']} {item_pcl['n_fr']} {item_pcl['n_en']}".lower().replace("-", " ")
    mots_item = set(re.findall(r'\b\w+\b', texte_item))
    
    return mots_expert.issubset(mots_item) if mots_expert else False

def main():
    print("🚀 Démarrage du script de synchronisation des astuces du clan...")
    
    # 1. Reconstituer le catalogue de référence PCL
    pcl_catalog = load_all_pcl_items()
    if not pcl_catalog:
        print("🛑 Impossible de charger les fichiers de référence PCL. Fin du script.")
        return

    # 2. Récupérer les données du Sheets
    sheet_rows = load_google_sheet_tips()
    if not sheet_rows:
        print("🛑 Aucune ligne récupérée depuis le Sheets. Fin du script.")
        return

    # 3. Charger les fichiers de détails existants à modifier
    details_database = {}
    for cat in CATEGORIES:
        file_path = os.path.join(DATA_DIR, f"{cat}_details.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                details_database[cat] = json.load(f)
        else:
            details_database[cat] = {}

        # 🟢 MUTATION SÉCURISÉE : On ne détruit rien, on nettoie uniquement la clé cible.
        for slug in list(details_database[cat].keys()):
            if isinstance(details_database[cat][slug], dict):
                details_database[cat][slug]['expert_tips'] = []
                # Sécurité : Si le scraper n'a pas encore créé la liste des composants, on initialise proprement
                if 'components' not in details_database[cat][slug]:
                    details_database[cat][slug]['components'] = []

    # Date actuelle pour la péremption
    aujourd_hui = datetime.now()

    # 4. Parcourir et traiter le Sheets
    for idx, row in enumerate(sheet_rows, start=6):
        if not row or len(row) < 1 or not row[0].strip():
            continue
            
        saisie_expert = row[0].strip()
        auteur = row[1].strip() if len(row) > 1 and row[1].strip() else "Expert Anonyme"
        astuce_texte = row[2].strip() if len(row) > 2 else ""
        date_texte = row[3].strip() if len(row) > 3 else ""

        if not astuce_texte:
            continue

        # Vérification de la date de péremption
        if date_texte:
            try:
                date_peremption = datetime.strptime(date_texte, "%d/%m/%Y")
                if date_peremption < aujourd_hui:
                    print(f"🗑️ Ligne {idx} : Astuce pour '{saisie_expert}' périmée, ignorée.")
                    continue
            except ValueError:
                print(f"⚠️ Ligne {idx} : Date '{date_texte}' mal formatée (Attendu: JJ/MM/AAAA).")

        nom_nettoye, cat_cible = extraire_filtre_et_nom(saisie_expert)

        # Recherche des correspondances dans le catalogue PCL
        match_trouve = False
        for item in pcl_catalog:
            if cat_cible and item['categorie'] != cat_cible:
                continue

            if match_mots(nom_nettoye, item):
                slug = item['id']
                if slug in details_database[item['categorie']]:
                    if 'expert_tips' not in details_database[item['categorie']][slug]:
                        details_database[item['categorie']][slug]['expert_tips'] = []
                    
                    details_database[item['categorie']][slug]['expert_tips'].append({
                        "author": auteur,
                        "text": astuce_texte
                    })
                    match_trouve = True
                    print(f"🔗 Ligne {idx} : Astuce de {auteur} liée à [{slug}] ({item['categorie']})")

        if not match_trouve:
            print(f"❓ Ligne {idx} : Aucun item trouvé sur PCL pour '{saisie_expert}'")

    # 5. Sauvegarde finale des 7 fichiers détails mis à jour
    print("💾 Sauvegarde des modifications dans les fichiers JSON...")
    for cat in CATEGORIES:
        if details_database[cat]:
            file_path = os.path.join(DATA_DIR, f"{cat}_details.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                # Écriture indentée propre qui préserve l'intégralité du dictionnaire
                json.dump(details_database[cat], f, ensure_ascii=False, indent=2)

    # ==============================================================================
    # 🟢 DUPLICATION ET MISE À JOUR SYNCHRONE DU TOP 50 (WFM50) — VERSION OPTIMISÉE
    # ==============================================================================
    wfm50_path = os.path.join(DATA_DIR, "wfm50_details.json")
    if os.path.exists(wfm50_path):
        print("⚡ Synchronisation des astuces d'experts dans wfm50_details.json...")
        try:
            with open(wfm50_path, 'r', encoding='utf-8') as f:
                wfm50_data = json.load(f)
            
            # 1. 🗑️ LA LOGIQUE : On efface TOUTES les astuces existantes du Top 50 d'un coup
            for slug in wfm50_data.keys():
                if "expert_tips" in wfm50_data[slug]:
                    del wfm50_data[slug]["expert_tips"]

            # 2. ✍️ Ré-injection propre des astuces fraîches et valides
            wfm50_modifie = False
            for slug in wfm50_data.keys():
                for cat in CATEGORIES:
                    if slug in details_database[cat] and "expert_tips" in details_database[cat][slug]:
                        wfm50_data[slug]["expert_tips"] = details_database[cat][slug]["expert_tips"]
                        wfm50_modifie = True
                        break # Item trouvé dans cette catégorie, on passe au suivant
            
            # 3. Sauvegarde si le fichier a reçu de nouvelles astuces (ou s'il a été vidé)
            # On sauvegarde systématiquement pour valider le nettoyage complet
            with open(wfm50_path, 'w', encoding='utf-8') as f:
                json.dump(wfm50_data, f, ensure_ascii=False, indent=2)
            print("💾 Fichier wfm50_details.json synchronisé et nettoyé avec succès !")
                
        except Exception as e:
            print(f"⚠️ Erreur lors de la synchronisation du Top 50 : {e}")
    
    print("✅ Fin du traitement.")

if __name__ == "__main__":
    main()
