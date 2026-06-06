import requests
import json
import time
from datetime import datetime
from pathlib import Path

# ==============================================================================
# CONFIGURATION FLASH WFM50
# ==============================================================================

# ==============================================================================
# ⚠️ FUTURE MIGRATION NOTE - PLAN D'ADAPTATION V1 EN V2 (STATISTIQUES)
# ==============================================================================
#
# CONTEXTE :
# Actuellement, ce script utilise la route V1 pour récupérer l'historique des prix
# et les volumes (`/v1/items/{slug}/statistics`) car Warframe Market n'a pas encore
# déployé l'équivalent en V2.
#
# LORSQUE WFM TERMINERA SA MIGRATION ET SORTIRA LA ROUTE V2 DES STATISTIQUES :
#
# 1. MODIFICATION DES URLS (Lignes ~13) :
#    - Supprimer la variable `BASE_URL_V1`.
#    - Modifier les appels de statistiques pour pointer vers la V2 :
#      Ancien : f"{BASE_URL_V1}/items/{slug}/statistics"
#      Nouveau : f"{BASE_URL_V2}/items/{slug}/statistics" (ou la nouvelle structure V2 définie par WFM)
#
# 2. ADAPTATION DE LA FONCTION DE CALCUL `calculate_economic_indicators` :
#    - La fonction importée de `wfm_scraper.py` lit un payload au format V1 :
#      `payload["statistics_closed"]["48hours"]` et `["90days"]`.
#    - En V2, la structure du JSON va changer (WFM standardise ses réponses sous la clé `"data"`).
#    - Il faudra donc modifier l'extraction dans cette fonction pour cibler les nouvelles clés
#      V2 correspondantes aux données des dernières 48h et 90j.
#
# 3. CONSERVATION DE LA LOGIQUE SECURISEE :
#    - La logique de vérification de version au démarrage (`/v2/versions`) restera
#      identique et protégera toujours le script si une rupture de structure survient.
#
# ==============================================================================

BASE_URL_V2 = "https://api.warframe.market/v2"
BASE_URL_V1 = "https://api.warframe.market/v1"
DELAY = 0.4  # Vitesse de scraping courtoise

HEADERS_EN = {"Accept": "application/json", "Language": "en", "User-Agent": "WF-PriceCheck-Top50Hourly"}

BASE_DIR = Path(".")
DATA_DIR = BASE_DIR / "data"
VERSION_PATH = DATA_DIR / "api_version.json"
WFM50_TABLE_PATH = DATA_DIR / "wfm50_table.json"
WFM50_DETAILS_PATH = DATA_DIR / "wfm50_details.json"

# Import de la fonction de calcul partagée depuis ton script principal
from wfm_scraper import calculate_economic_indicators

def safe_requests(url, headers, max_retries=3, backoff_factor=1.5):
    """Exécute une requête GET avec mécanisme de Retry exponentiel."""
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                return res
            elif res.status_code in [429, 502, 503, 504]:
                time.sleep(backoff_factor * (attempt + 1))
            else:
                return res
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            time.sleep(backoff_factor * (attempt + 1))
    try:
        return requests.get(url, headers=headers, timeout=10)
    except:
        return None

def main():
    print("🚀 Démarrage de la mise à jour horaire flash WFM50...")
    today = datetime.utcnow()

    # 1. VERIFICATION STRICTE DE LA VERSION DE L'API
    if not VERSION_PATH.exists():
        print("❌ Fichier api_version.json introuvable. Le script principal doit tourner d'abord.")
        return

    with open(VERSION_PATH, 'r', encoding='utf-8') as f:
        version_data = json.load(f)
    
    local_api_version = version_data.get("version")

    # Requête rapide pour voir si WFM a changé de version
    res_ver = safe_requests(f"{BASE_URL_V2}/versions", headers=HEADERS_EN)
    remote_api_version = None
    if res_ver and res_ver.status_code == 200:
        try:
            remote_api_version = res_ver.json().get("data", {}).get("version")
        except:
            pass

    if remote_api_version and local_api_version and remote_api_version != local_api_version:
        print(f"⚠️ L'API WFM a changé de version ({local_api_version} -> {remote_api_version}).")
        print("🛑 Annulation de la mise à jour horaire. En attente de la resynchronisation du script principal.")
        return

    # ==============================================================================
    # 2. CHARGEMENT DES FICHIERS WFM50 EXISTANTS
    # ==============================================================================
    if not WFM50_TABLE_PATH.exists() or not WFM50_DETAILS_PATH.exists():
        print("❌ Fichiers WFM50 introuvables. Le script principal doit tourner d'abord.")
        return

    with open(WFM50_TABLE_PATH, 'r', encoding='utf-8') as f:
        wfm50_table = json.load(f)
    with open(WFM50_DETAILS_PATH, 'r', encoding='utf-8') as f:
        wfm50_details = json.load(f) # C'est désormais un dictionnaire {"slug": {...}}

    # ==============================================================================
    # 3. MISE À JOUR HORAIRE DES STATISTIQUES (Top 50)
    # ==============================================================================
    print(f"📊 Actualisation des indicateurs économiques pour les {len(wfm50_table)} items majeurs...")
    
    for item in wfm50_table:
        slug = item.get("id")
        if not slug:
            continue

        # Récupération des statistiques de l'item parent (V1 Statistics API)
        time.sleep(DELAY)
        res_stats = safe_requests(f"{BASE_URL_V1}/items/{slug}/statistics", headers=HEADERS_EN)
        if res_stats and res_stats.status_code == 200:
            indicators = calculate_economic_indicators(res_stats.json().get("payload", {}))
            
            # Mise à jour dans le dictionnaire en protégeant la structure
            if slug in wfm50_details and isinstance(wfm50_details[slug], dict):
                wfm50_details[slug].update(indicators)
                
                # S'il y a des composants enfants, on met aussi à jour leurs statistiques individuelles
                components = wfm50_details[slug].get("components", [])
                if isinstance(components, list) and components:
                    for comp in components:
                        comp_slug = comp.get("slug")
                        if not comp_slug:
                            continue
                        
                        time.sleep(DELAY)
                        res_comp_stats = safe_requests(f"{BASE_URL_V1}/items/{comp_slug}/statistics", headers=HEADERS_EN)
                        if res_comp_stats and res_comp_stats.status_code == 200:
                            comp_indicators = calculate_economic_indicators(res_comp_stats.json().get("payload", {}))
                            comp.update(comp_indicators)

    # ==============================================================================
    # 4. SAUVEGARDE DES FICHIERS WFM50
    # ==============================================================================
    print("💾 Enregistrement des fichiers WFM50 mis à jour...")
    with open(WFM50_TABLE_PATH, 'w', encoding='utf-8') as f:
        json.dump(wfm50_table, f, ensure_ascii=False, separators=(',', ':'))
        
    with open(WFM50_DETAILS_PATH, 'w', encoding='utf-8') as f:
        # On sauvegarde le dictionnaire avec une indentation propre
        json.dump(wfm50_details, f, ensure_ascii=False, indent=2)

    # 5. MISE À JOUR DU FICHIER VERSION (Heure de l'update horaire)
    version_data["last_wfm50_hourly_update"] = today.isoformat()
    with open(VERSION_PATH, 'w', encoding='utf-8') as f:
        json.dump(version_data, f, ensure_ascii=False, indent=2)

    print(f"✅ Opération réussie. WFM50 actualisé à {today.strftime('%H:%M:%S')} UTC.")

if __name__ == "__main__":
    main()
