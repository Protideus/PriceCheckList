import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# ==============================================================================
# API ARCHITECTURE NOTE - HYBRID V1/V2 (As of June 2026)
# ==============================================================================
# 
# CONTEXT:
# The Warframe Market API is currently in transition from V1 to V2. This script
# uses a hybrid approach to work around incomplete V2 migration:
#
# CURRENT STATE (June 2026):
#   - V2 IMPLEMENTED: /v2/items (manifest), /v2/items/{slug} (details), /v2/orders
#   - V1 ONLY: /v1/items/{slug}/statistics (90-day price history) - NO V2 equivalent yet
#
# SCRIPT SECTIONS AFFECTED:
#   1. Line ~193: Manifest fetch → V2 /items (CONFIRMED STABLE)
#   2. Line ~207-240: Item details fetch → V2 /items/{slug} with i18n (CONFIRMED STABLE)
#   3. Line ~258-262: Statistics fetch → V1 /items/{slug}/statistics (TEMPORARY - WILL CHANGE)
#   4. Line ~46-115: calculate_economic_indicators() parses V1 response format
#
# FUTURE MIGRATION PLAN:
# When WFM API completes V2 migration and releases /v2/items/{slug}/statistics:
#
#   STEP 1: Update BASE_URL references
#     - Remove: BASE_URL_V1 variable
#     - Update statistics endpoint: BASE_URL_V1/items/{slug}/statistics → BASE_URL_V2/items/{slug}/statistics
#
#   STEP 2: Update response parsing in calculate_economic_indicators()
#     - Current: Expects {payload: {statistics_live: {90days: [...]}}} (V1 format)
#     - Future: Will likely return {data: {statistics: {90days: [...]}}} (V2 format)
#     - Action: Extract 90days from response structure matching new V2 response format
#
#   STEP 3: Update datetime parsing if needed
#     - Current: Parses "2026-03-04T00:00:00.000+00:00" → "2026-03-04"
#     - Verify: V2 format may differ; adjust string slicing if needed
#
# TESTING CHECKLIST FOR MIGRATION:
#   □ Fetch one item with /v2/items/{slug}/statistics
#   □ Print raw response structure (keys, nesting)
#   □ Compare with current V1 format and adjust parsing
#   □ Test on 3-5 items to confirm consistency
#   □ Run full RESET mode and verify output files are populated
#
# ==============================================================================
# 💡 WFM API V2 ARCHITECTURE & BEHAVIOR
# ==============================================================================
#
# 1. THE '/set' ENDPOINT REQUIREMENT
#    - Standard `/v2/items/{slug}` requests only return the item itself.
#    - To get a Set AND all its components, you MUST use the dedicated endpoint:
#      👉 GET https://api.warframe.market/v2/item/{slug}/set
#
# 2. FLAT LIST STRUCTURE (data.items)
#    - The response returns a flat list of objects inside `data.items`.
#    - The main item (the Set) has `"setRoot": true`.
#    - The craftable components have `"setRoot": false` (and a `"component"` tag).
#
# 3. CONCRETE JSON EXAMPLE (Chroma Prime Set):
#    {
#      "data": {
#        "items": [
#          { "slug": "chroma_prime_set", "setRoot": true, "i18n": { "fr": { "name": "Chroma Prime - Set" }, "en": { ... } } },
#          { "slug": "chroma_prime_blueprint", "setRoot": false, "quantityInSet": 1 },
#          { "slug": "chroma_prime_chassis_blueprint", "setRoot": false, "quantityInSet": 1 }
#        ]
#      }
#    }
#
# 4. OPTIMIZED LANGUAGE HEADERS (i18n)
#    - Sending `{"Language": "fr"}` returns BOTH "fr" and "en" translations 
#      simultaneously inside the "i18n" block.
#    - No need for two separate API calls (saves 50% request time and prevents rate limits).
# 
# ==============================================================================
# CONFIGURATION
# ==============================================================================

BASE_URL_V2 = "https://api.warframe.market/v2"
BASE_URL_V1 = "https://api.warframe.market/v1"
DELAY = 0.4 

#The WFM api answers diferently according to header. If language is not EN then it gives data for both EN and the desired language.
HEADERS_EN = {"Accept": "application/json", "Language": "en", "User-Agent": "WF-PriceCheck-Scraper"}
HEADERS_FR = {"Accept": "application/json", "Language": "fr", "User-Agent": "WF-PriceCheck-Scraper"}

BASE_DIR = Path(".") # Racine du projet
DATA_DIR = BASE_DIR / "data"
BLACKLIST_PATH = DATA_DIR / "ignored_slugs.json"
VERSION_PATH = DATA_DIR / "api_version.json"

CATEGORIES = ["warframes", "armes", "equipements", "reliques", "mods", "arcanes", "ressources"]

# ==============================================================================
# FONCTIONS UTILITAIRES & MATHÉMATIQUES
# ==============================================================================

def get_fusion_ratio(max_rank: int) -> int:
    """
    Calcule le nombre total d'arcanes rang 0 nécessaires pour atteindre 'max_rank'.
    Valide pour les arcanes standards (max rank 5) et ceux limités à rank 3.
    """
    if max_rank < 0:
        return 0
    
    total = 1  # On commence avec 1 arcane R0
    for r in range(1, max_rank + 1):
        total += (r + 1)   # +2, +3, +4, +5, +6...
    
    return total

def safe_requests(url, headers, max_retries=3, backoff_factor=1.5):
    """
    Exécute une requête GET de manière sécurisée avec un mécanisme de tentative (Retry).
    En cas d'échec ou de timeout, elle attend un peu avant de réessayer.
    """
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            # Si c'est un code de succès, on renvoie la réponse immédiatement
            if res.status_code == 200:
                return res
            # Si le serveur nous dit explicitement qu'il est surchargé (ex: Code 429 Too Many Requests)
            elif res.status_code in [429, 502, 503, 504]:
                time.sleep(backoff_factor * (attempt + 1))
            else:
                # Pour les autres codes d'erreur (404, etc.), inutile de s'acharner
                return res
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            # En cas de Timeout ou coupure réseau, on attend de plus en plus longtemps (Backoff)
            time.sleep(backoff_factor * (attempt + 1))
            
    # Si toutes les tentatives ont échoué, on fait une dernière requête brute qui lèvera l'erreur ou sera interceptée
    try:
        return requests.get(url, headers=headers, timeout=10)
    except:
        return None

def categorize_item(tags, url_name):
    """Filtre l'objet selon ses VRAIS tags de l'API avec support Necramech."""
    is_set = url_name.endswith("_set")
    
    # 1. WARFRAMES
    if "warframe" in tags: 
        return "warframes" if is_set else "ignore"
        
    # 2. ARMES (Inclus les armes normales et les armes lourdes/necramech)
    if "weapon" in tags or "necramech_weapon" in tags: 
        return "armes" if is_set else "ignore"
        
    # 3. EQUIPEMENTS (Sentinelles, Archwings, Compagnons, et désormais les Sets Necramech)
    if any(t in tags for t in ["sentinel", "archwing", "kubrow", "kavat", "necramech"]): 
        return "equipements" if is_set else "ignore"
        
    # 4. RELIQUES
    if "relic" in tags: 
        return "reliques"
        
    # 5. MODS
    if "mod" in tags: 
        return "mods"
        
    # 6. ARCANES
    if "arcane_enhancement" in tags: 
        return "arcanes"
        
    # 7. RESSOURCES (Uniquement les objets utilitaires bruts, jamais de structures '_set')
    if any(t in tags for t in ["lens", "ayatan_star", "ayatan_sculpture", "fusion core"]): 
        return "ignore" if is_set else "ressources"
        
    return "ignore"

def calculate_economic_indicators(stats_data):
    """
    Calcule les indicateurs économiques avancés de PriceCheckList.
    Sépare strictement le Rang 0 (base) et le Rang > 0 (max).
    Optimisé pour ne pas inclure les clés '_max' sur les objets sans rang.
    """
    # 1. Extraction des listes brutes de l'API
    hours_48 = []
    if "statistics_closed" in stats_data:
        hours_48 = stats_data["statistics_closed"].get("48hours", [])
    elif "statistics_live" in stats_data:
        hours_48 = stats_data["statistics_live"].get("48hours", [])

    days_90 = []
    if "statistics_closed" in stats_data:
        days_90 = stats_data["statistics_closed"].get("90days", [])
    if not days_90 and "statistics_live" in stats_data:
        days_90 = stats_data["statistics_live"].get("90days", [])

    # On vérifie si l'objet possède des données avec un rang > 0 (Mods, Arcanes)
    has_ranks = any((e.get("rank", e.get("mod_rank", 0)) > 0) for e in hours_48 + days_90)

    # FONCTION INTERNE : Calcule les 6 métriques pour un groupe d'entrées filtré
    def _process_metrics(h48_filtered, d90_filtered):
        total_volume_48h = 0
        weighted_price_sum = 0.0

        for entry in h48_filtered:
            vol = entry.get("volume", 0)
            wa_price = entry.get("wa_price", entry.get("median", 0))
            total_volume_48h += vol
            weighted_price_sum += (wa_price * vol)

        p_actuel = 0.0
        if total_volume_48h > 0:
            p_actuel = round(weighted_price_sum / total_volume_48h, 1)
        elif h48_filtered:
            medians = [e.get("median", 0) for e in h48_filtered if e.get("median", 0) > 0]
            p_actuel = round(sum(medians) / len(medians), 1) if medians else 0.0

        vl = total_volume_48h

        if not d90_filtered:
            return p_actuel, 0.0, vl, 0.0, 50.0, 0 # Pas d'historique = Fiabilité 0

        raw_data_90j = {}
        for entry in d90_filtered:
            dt_str = entry.get("datetime", "")
            if dt_str:
                date_key = dt_str[:10]
                if date_key in raw_data_90j:
                    raw_data_90j[date_key]["volume"] += entry.get("volume", 0)
                else:
                    raw_data_90j[date_key] = {
                        "volume": entry.get("volume", 0),
                        "moving_avg": entry.get("moving_avg", entry.get("median", 0)),
                        "median": entry.get("median", 0),
                        "avg_price": entry.get("avg_price", entry.get("median", 0)),
                        "min_price": entry.get("min_price", entry.get("median", 0)),
                        "max_price": entry.get("max_price", entry.get("median", 0)),
                        "has_real_data": True
                    }

        today_dt = datetime.now()
        start_date = today_dt - timedelta(days=89)
        filled_90j = []
        last_valid = None

        for i in range(90):
            current_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            has_data = current_date in raw_data_90j
            if has_data:
                last_valid = raw_data_90j[current_date]

            if last_valid:
                filled_90j.append({
                    "date": current_date,
                    "volume": raw_data_90j[current_date]["volume"] if has_data else 0,
                    "moving_avg": last_valid["moving_avg"],
                    "median": last_valid["median"],
                    "avg_price": last_valid["avg_price"],
                    "min_price": last_valid["min_price"],
                    "max_price": last_valid["max_price"],
                    "has_real_data": has_data
                })

        if p_actuel == 0.0 and filled_90j:
            p_actuel = filled_90j[-1]["moving_avg"]

        p_90j = filled_90j[0]["moving_avg"] if filled_90j else 0.0
        p90_delta = 0.0
        if p_90j > 0:
            p90_delta = round(((p_actuel - p_90j) / p_90j) * 100, 1)

        # CORRECTION 1: Le volume moyen journalier doit inclure les jours à 0 vente (divisé par 90)
        vol_24h_recent = vl / 2.0
        total_volume_90j = sum(d["volume"] for d in filled_90j)
        avg_vol_journalier_90j = total_volume_90j / 90.0
        
        vr = 0.0
        if avg_vol_journalier_90j > 0:
            vr = round(vol_24h_recent / avg_vol_journalier_90j, 2)

        real_medians = [d["median"] for d in filled_90j if d["has_real_data"] and d["median"] > 0]
        ds = 50.0
        donch_bot, donch_top = 0.0, 0.0
        if real_medians:
            donch_bot = min(real_medians)
            donch_top = max(real_medians)
            if donch_top > donch_bot:
                ds = round(((p_actuel - donch_bot) / (donch_top - donch_bot)) * 100, 1)
                ds = max(0.0, min(100.0, ds))

        # --- CALCUL CORRIGÉ DE LA FIABILITÉ (F) ---
        f = 3
        
        # 1. Alerte Illiquidité : Calcul du taux de jours "morts" sur les 90 derniers jours
        days_with_data = sum(1 for d in filled_90j if d["has_real_data"])
        if days_with_data < 15:  # Moins de 15 jours actifs sur 90 = Marché fantôme
            f -= 1
        elif total_volume_90j < 45: # Seuil global rehaussé (moins de 0.5 vente / jour)
            f -= 1

        # 2. Alerte Volatilité / Spéculation (Donchian instable)
        # Au lieu de prendre uniquement les hauts historiques du tableau 90j on :
        donch_top_reel = max(donch_top, p_actuel)

        # Si le prix max historique est 5x supérieur au prix minimum sur 90j, danger imminent.
        if donch_bot > 0 and (donch_top_reel / donch_bot) > 5.0:
            f -= 1
        

        # 3. Alerte manipulation des prix récents (Écart Prix Moyen / Médiane)
        # On regarde STRICTEMENT les 7 derniers jours calendaires (avec ou sans données)
        recent_7_days = filled_90j[-7:]
        recent_ratios = [d["avg_price"] / d["median"] for d in recent_7_days if d["has_real_data"] and d["median"] > 0]
        
        if recent_ratios:
            avg_ratio = sum(recent_ratios) / len(recent_ratios)
            if avg_ratio > 1.2: 
                f -= 1

        f = max(0, f)
        return p_actuel, p90_delta, vl, vr, ds, f

    # --- SÉPARATION DES FLUX (Vision simple et robuste) ---
    h48_r0 = [e for e in hours_48 if e.get("rank", e.get("mod_rank", 0)) == 0]
    d90_r0 = [e for e in days_90 if e.get("rank", e.get("mod_rank", 0)) == 0]
    
    p0, p90_0, v0, vr_0, ds_0, f_0 = _process_metrics(h48_r0, d90_r0)
    
    output = {
        "p": p0, "p90": p90_0, "v": v0, "vr": vr_0, "ds": ds_0, "f": f_0
    }

    # Si l'objet possède des rangs, on traite le lot restant (> 0) pour le bloc max
    if has_ranks:
        h48_rmax = [e for e in hours_48 if e.get("rank", e.get("mod_rank", 0)) > 0]
        d90_rmax = [e for e in days_90 if e.get("rank", e.get("mod_rank", 0)) > 0]
        
        pm, p90_m, vm, vr_m, ds_m, f_m = _process_metrics(h48_rmax, d90_rmax)
        output.update({
            "p_max": pm, "p90_max": p90_m, "v_max": vm, "vr_max": vr_m, "ds_max": ds_m, "f_max": f_m
        })

    return output

def load_cache():
    """Charge le cache local et valide s'il contient de vraies données."""
    cache = {cat: {"table": {}, "details": {}} for cat in CATEGORIES}
    has_valid_cache = True
    total_items_found = 0
    
    for cat in CATEGORIES:
        table_path = DATA_DIR / f"{cat}_table.json"
        details_path = DATA_DIR / f"{cat}_details.json"
        
        if not table_path.exists() or not details_path.exists():
            has_valid_cache = False
            continue
            
        try:
            with open(table_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
                if not content: # Si le tableau est vide []
                    has_valid_cache = False
                for item in content:
                    cache[cat]["table"][item["id"]] = item
                    total_items_found += 1
        except: 
            has_valid_cache = False
            
        try:
            with open(details_path, 'r', encoding='utf-8') as f:
                cache[cat]["details"] = json.load(f)
                if not cache[cat]["details"]: # Si le dictionnaire est vide {}
                    has_valid_cache = False
        except: 
            has_valid_cache = False
            
    # Si aucun objet n'a été chargé dans l'ensemble des fichiers, le cache est invalide
    if total_items_found == 0:
        has_valid_cache = False
        
    return cache, has_valid_cache

# ==============================================================================
# BOUCLE PRINCIPALE
# ==============================================================================

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.utcnow()
    
    # Initialisation des variables de contrôle
    current_api_version = "unknown"
    current_items_hash = None
    
    # 1. RECUPERATION INTELLIGENTE DU HASH ET DE L'API VERSION (V2 /versions)
    try:
        res = safe_requests(f"{BASE_URL_V2}/versions", headers=HEADERS_EN)
        if res.status_code == 200:
            payload = res.json()
            current_api_version = payload.get("apiVersion", "unknown") # Version technique
            api_data = payload.get("data", {})
            
            if isinstance(api_data, dict):
                # La pépite : Le hash qui change dès qu'un objet est ajouté/modifié en jeu
                current_items_hash = api_data.get("collections", {}).get("items")
    except Exception as e: 
        print(f"⚠️ Impossible de joindre le endpoint des versions ({e}), repli sur sauvegarde.")
        pass

    # Fallback si l'API ou le réseau a un raté
    if not current_items_hash:
        current_items_hash = f"fallback_{today.strftime('%Y_%m_%d')}"

    # 2. LECTURE DE LA CONFIGURATION SAUVEGARDÉE
    saved_api_version = None
    saved_items_hash = None
    last_reset = None
    
    if VERSION_PATH.exists():
        try:
            with open(VERSION_PATH, 'r', encoding='utf-8') as f:
                v_data = json.load(f)
                saved_api_version = v_data.get("api_version")
                saved_items_hash = v_data.get("items_hash") # Comparaison sur le hash
                last_reset = datetime.fromisoformat(v_data.get("last_full_reset", "2000-01-01"))
        except Exception as e: 
            print(f"⚠️ Erreur lecture api_version.json : {e}")
            pass

    # Chargement et validation stricte du Cache
    cache, has_valid_cache = load_cache()
    
    blacklist = set()
    if VERSION_PATH.exists() and BLACKLIST_PATH.exists():
        try:
            with open(BLACKLIST_PATH, 'r', encoding='utf-8') as f:
                blacklist = set(json.load(f))
        except:
            pass

    # 3. DÉTERMINATION DU MODE DE RUN (LA LOGIQUE LOGICIELLE LOGIQUE)
    run_type = "PARTIAL"
    
    # Cas 1 : Pas de reset depuis 90j ou le cache local est corrompu/absent -> RESET complet
    if not last_reset or (today - last_reset).days >= 90 or not has_valid_cache:
        run_type = "RESET"
        blacklist = set() # On vide la blacklist pour tout réanalyser proprement
        
    # Cas 2 : Le hash de la collection d'items a changé ! (Nouveau contenu ou modification)
    # On passe en mode UPDATE pour forcer la mise à jour des structures de données
    elif current_items_hash != saved_items_hash:
        run_type = "UPDATE"

    print(f"🚀 Démarrage du Scraper V3 | Mode : {run_type} (Cache valide : {has_valid_cache})")
    print(f"📊 API Version: {current_api_version} | Items Hash: {current_items_hash}")

    new_data = {cat: {"table": [], "details": {}} for cat in CATEGORIES}
    
    if run_type == "PARTIAL":
        for cat in CATEGORIES:
            new_data[cat]["details"] = cache[cat]["details"]

    res_manifest = safe_requests(f"{BASE_URL_V2}/items", headers=HEADERS_EN)
    if res_manifest.status_code != 200:
        raise RuntimeError(f"❌ Échec du manifeste global ({res_manifest.status_code}) : {res_manifest.text[:200]}")
        return

    all_items = res_manifest.json().get("data", [])
    if not isinstance(all_items, list):
        print(f"❌ Le manifeste global n'est pas une liste valide : {type(all_items).__name__}")
        return

    print(f"📋 {len(all_items)} objets trouvés dans le manifeste global. Filtrage...")

    item_id_map = {item.get("id"): item.get("slug") for item in all_items if item.get("id") and item.get("slug")}

    # Boucle Principale
    for index, item in enumerate(all_items):
        slug = item.get("slug") or item.get("url_name") or ""
        if not slug or slug in blacklist:
            continue

        # On initialise TOUJOURS la liste de composantsà vide pour cet item précis
        components_blueprint = []

        found_category = None
        if run_type != "RESET":
            for cat in CATEGORIES:
                if slug in cache[cat]["table"] or slug in cache[cat]["details"]:
                    found_category = cat
                    break

        try:
            # SCÉNARIO A : L'objet est totalement inconnu ou mode RESET
            if not found_category or run_type == "RESET":
                time.sleep(DELAY)
                
                # 🟢 UNE SEULE REQUÊTE : L'endpoint V2 '/set' avec header FR contient tout
                url_set = f"https://api.warframe.market/v2/item/{slug}/set"
                res_fr = safe_requests(url_set, headers=HEADERS_FR)
                
                if res_fr and res_fr.status_code == 200:
                    json_fr = res_fr.json().get("data", {})
                    
                    # Récupération de la liste plate d'items retournée par la V2
                    items_list = json_fr.get("items", [])
                    if not items_list:
                        continue
                        
                    # L'item principal (le Set) possède 'setRoot': True
                    main_item = next((item for item in items_list if item.get("setRoot") is True), items_list[0])
                    
                    # Extraction des tags depuis l'item principal
                    tags = main_item.get("tags", [])
                    cat = categorize_item(tags, slug)
                    
                    if cat == "ignore":
                        blacklist.add(slug)
                        continue
                    
                    # Extraction linguistique (Le bloc 'fr' embarque aussi le 'en' en V2)
                    i18n_en = main_item.get("i18n", {}).get("en", {})
                    i18n_fr = main_item.get("i18n", {}).get("fr", {})
                    
                    n_en = i18n_en.get("name") or slug
                    n_fr = i18n_fr.get("name") or slug
                    
                    # 🟢 EXTRACTION SÉCURISÉE DES COMPOSANTS (V2 COMPATIBLE)
                    components_blueprint = []
                    
                    # Sécurité : On extrait les composants UNIQUEMENT si l'objet principal est un Set
                    main_tags = main_item.get("tags", [])
                    if "set" in main_tags:
                        for sub_item in items_list:
                            # On ignore le Set lui-même
                            if sub_item == main_item:
                                continue
                                
                            if isinstance(sub_item, dict):
                                comp_slug = sub_item.get("slug")
                                if not comp_slug or comp_slug == slug:
                                    continue
                                    
                                # Récupération de la quantité
                                qty = sub_item.get("quantityInSet") or sub_item.get("quantity") or 1
                                
                                # EXTRACTION DES TRADUCTIONS DES COMPOSANTS
                                comp_i18n_en = sub_item.get("i18n", {}).get("en", {})
                                comp_i18n_fr = sub_item.get("i18n", {}).get("fr", {})
                                comp_n_en = comp_i18n_en.get("name") or comp_slug
                                comp_n_fr = comp_i18n_fr.get("name") or comp_slug
                                
                                if not any(c["slug"] == comp_slug for c in components_blueprint):
                                    components_blueprint.append({
                                        "slug": comp_slug,
                                        "qty": int(qty),
                                        "n_fr": comp_n_fr,  
                                        "n_en": comp_n_en   
                                    })

                    # Calcul du ratio de fusion (uniquement si c'est une arcane)
                    fusion_ratio = None
                    if cat == "arcanes":
                        # On calcule le ratio dynamiquement selon le maxRank
                        max_rank = main_item.get("maxRank", 5)
                        # Logique : 1 + somme(2^(r-1) pour r de 1 à max_rank)
                        fusion_ratio = 1 + sum(2**(r-1) for r in range(1, max_rank + 1))

                    # Initialisation de la structure des détails
                    new_data[cat]["details"][slug] = {
                        "desc_fr": i18n_fr.get("description", ""),
                        "desc_en": i18n_en.get("description", ""),
                        "wiki_en": i18n_en.get("wikiLink", ""),
                        "icon": i18n_en.get("icon", ""),
                        "components": [], # Sera peuplé juste après
                        "fusion_ratio": fusion_ratio # 🆕 Stockage du ratio calculé
                    }
                    found_category = cat
                else:
                    continue

            # SCÉNARIO B : L'objet est connu
            else:
                old_entry = cache[found_category]["table"].get(slug, {})
                n_fr = old_entry.get("n_fr", slug)
                n_en = old_entry.get("n_en", slug)
                
                if run_type == "UPDATE" and slug not in new_data[found_category]["details"]:
                    new_data[found_category]["details"][slug] = cache[found_category]["details"].get(slug, {})

                # En mode UPDATE, on récupère le blueprint depuis le cache
                old_details = cache[found_category]["details"].get(slug, {})
                old_components = old_details.get("components", [])
                for comp in old_components:
                    components_blueprint.append({
                        "slug": comp.get("slug"),
                        "qty": comp.get("qty", 1),
                        "n_fr": comp.get("n_fr", comp.get("slug")), # 🆕 Récupération nom FR
                        "n_en": comp.get("n_en", comp.get("slug"))  # 🆕 Récupération nom EN
                    })

            # 🔄 MIGRATION POINT: Statistics endpoint - Currently V1 ONLY
            # TODO: When /v2/items/{slug}/statistics becomes available, replace:
            #   OLD: f"{BASE_URL_V1}/items/{slug}/statistics"
            #   NEW: f"{BASE_URL_V2}/items/{slug}/statistics"
            # And update calculate_economic_indicators() to parse V2 response format
            time.sleep(DELAY)
            res_stats = safe_requests(f"{BASE_URL_V1}/items/{slug}/statistics", headers=HEADERS_EN)
            
            # Valeurs de secours si les statistiques sont manquantes ou en erreur
            indicators = {"p": 0.0, "p90": 0.0, "v": 0, "vr": 0.0, "ds": 50.0, "f": 0}
            
            if res_stats.status_code == 200:
                # V1 returns {"payload": {"statistics_live": {"90days": [...]}, "statistics_closed": {...}}}
                # V2 will likely return {"data": {"statistics": {"90days": [...]}}} - parser will need update
                stats_payload = res_stats.json().get("payload", {})
                indicators = calculate_economic_indicators(stats_payload)
            else:
                print(f"  ⚠️ Statut anormal ({res_stats.status_code}) pour {slug}, indicateurs mis à zéro.")

            set_components_data = []
            
            # Cette boucle ne s'exécute QUE si 'components_blueprint' contient des éléments
            for comp in components_blueprint:
                comp_slug = comp.get("slug")
                comp_qty = comp.get("qty", 1)
                comp_n_fr = comp.get("n_fr", comp_slug) # 🆕 Extraction
                comp_n_en = comp.get("n_en", comp_slug) # 🆕 Extraction
                
                if not comp_slug:
                    continue
                    
                # Aspiration Courtoise : Pause obligatoire avant chaque sous-requête
                time.sleep(DELAY)
                
                try:
                    res_comp_stats = safe_requests(
                        f"{BASE_URL_V1}/items/{comp_slug}/statistics", 
                        headers=HEADERS_EN
                    )
                    
                    comp_indicators = {"p": 0.0, "v": 0} # Valeurs de secours (fallback)
                    
                    if res_comp_stats.status_code == 200:
                        comp_payload = res_comp_stats.json().get("payload", {})
                        if comp_payload and isinstance(comp_payload, dict):
                            comp_calc = calculate_economic_indicators(comp_payload)
                            if isinstance(comp_calc, dict):
                                comp_indicators = comp_calc
                    else:
                        print(f"   ⚠️ Code {res_comp_stats.status_code} sur les stats de {comp_slug}, fallback à 0.")
                        
                except Exception as e:
                    print(f"   ❌ Erreur sur le composant {comp_slug} : {e}")
                    comp_indicators = {"p": 0.0, "v": 0}
                    
                set_components_data.append({
                    "slug": comp_slug,
                    "n_fr": comp_n_fr, # 🆕 Injection du nom FR
                    "n_en": comp_n_en, # 🆕 Injection du nom EN
                    "qty": comp_qty,
                    **comp_indicators
                })
                
            # Injection sécurisée dans le dictionnaire de détails du Set principal
            if found_category and found_category in new_data:
                # 1. On peuple les composants si nécessaire
                if slug in new_data[found_category]["details"]:
                    new_data[found_category]["details"][slug]["components"] = set_components_data

                # 2. CALCUL ET STOCKAGE DU RATIO
                ratio_to_add = None
                if found_category == "arcanes":
                    max_rank = main_item.get("maxRank", 5) if 'main_item' in locals() else 5
                    ratio_to_add = get_fusion_ratio(max_rank)

                # 3. AJOUT À LA TABLE
                row = {
                    "id": slug, 
                    "n_fr": n_fr, 
                    "n_en": n_en, 
                    "fusion_ratio": ratio_to_add, 
                    **indicators
                }
                new_data[found_category]["table"].append(row)
           
        except Exception as e:
            print(f"⚠️ Erreur sur {slug} : {e}")
            
        if (index + 1) % 100 == 0:
            print(f"🕒 {index + 1}/{len(all_items)} objets analysés...")

    # ==============================================================================
    # GÉNÉRATION DE LA CATÉGORIE VIRTUELLE : WFM50 (Top 50 par Volume 48h)
    # ==============================================================================
    print("\n📊 Génération de la liste WFM50 (Top 50 des items les plus liquides)...")
    
    # 1. On rassemble TOUS les items générés à travers les 7 catégories de base
    all_extracted_table_items = []
    details_registry = {} # Pour retrouver facilement les détails lourds via le slug
    
    for cat in CATEGORIES:
        all_extracted_table_items.extend(new_data[cat]["table"])
        # Correction : On parcourt correctement le dictionnaire de détails (clé, valeur)
        for slug_id, det_content in new_data[cat]["details"].items():
            details_registry[slug_id] = det_content

    # 2. On trie par volume 'v' (le volume 48h calculé par ta nouvelle fonction) décroissant
    # et on extrait les 50 premiers
    wfm50_table = sorted(all_extracted_table_items, key=lambda x: x.get("v", 0) if isinstance(x, dict) else 0, reverse=True)[:50]

    # 3. On extrait les détails correspondants à ces 50 items
    # On utilise un dictionnaire pour wfm50_details
    wfm50_details = {}
    for item in wfm50_table:
        slug = item["id"]
        if slug in details_registry:
            wfm50_details[slug] = details_registry[slug] 

    # Enregistrement des 7 catégories classiques
    for cat in CATEGORIES:
        with open(DATA_DIR / f"{cat}_table.json", 'w', encoding='utf-8') as f:
            json.dump(new_data[cat]["table"], f, ensure_ascii=False, separators=(',', ':'))
            
        if run_type in ["UPDATE", "RESET"]:
            with open(DATA_DIR / f"{cat}_details.json", 'w', encoding='utf-8') as f:
                json.dump(new_data[cat]["details"], f, ensure_ascii=False)

    # 4. Écriture des fichiers pour la 8ème liste : WFM50
    with open(DATA_DIR / "wfm50_table.json", 'w', encoding='utf-8') as f:
        json.dump(wfm50_table, f, ensure_ascii=False, separators=(',', ':'))
        
    with open(DATA_DIR / "wfm50_details.json", 'w', encoding='utf-8') as f:
        json.dump(wfm50_details, f, ensure_ascii=False)

    print(f"✅ Fichiers wfm50_table.json et wfm50_details.json créés avec succès ({len(wfm50_table)} items).")

    # ==============================================================================
    # GÉNÉRATION DU CLASSIEUR EXCEL AUTO-AJUSTÉ ET FORMATÉ (POUR LES JOUEURS)
    # ==============================================================================
    print("\n📊 Génération du fichier Excel formaté pour les joueurs...")
    try:
        import pandas as pd

        # 1. Nettoyage de sécurité au cas où d'anciens fichiers datés traîneraient
        for old_file in DATA_DIR.glob("Warframe_Prices_*.xlsx"):
            try:
                old_file.unlink()
            except:
                pass

        # Le dictionnaire qui va contenir nos feuilles Excel
        excel_sheets = {}

        # Dictionnaires pour accumuler les composants complets par grande catégorie de Set
        components_by_cat = {
            "warframes": [],
            "armes": [],
            "equipements": []
        }

        # Dictionnaire de traduction global des en-têtes
        friendly_names = {
            "parent_fr": "Appartient au Set",
            "n_fr": "Nom (FR)", 
            "n_en": "Nom (EN)", 
            "p": "Prix Moyen (Plat)",
            "p90": "Évolution 90j (%)", 
            "v": "Volume (48h)", 
            "vr": "Volume Relatif",
            "ds": "Position Marché (%)", 
            "f": "Fiabilité (0-3)",
            "qty": "Quantité Requise",
            "p_max": "Prix Max (Plat)", 
            "p90_max": "Évolution Max 90j (%)",
            "v_max": "Volume Max (48h)", 
            "vr_max": "Volume Relatif Max",
            "ds_max": "Position Marché Max (%)", 
            "f_max": "Fiabilité Max (0-3)",
            "Slug": "Identifiant API (Slug)"
        }

        columns_order_base = ["n_fr", "n_en", "p", "p90", "v", "vr", "ds", "f"]

        # On parcourt STRICTEMENT les 7 catégories de base
        for cat in CATEGORIES:
            cat_table = new_data[cat].get("table", [])
            if not cat_table:
                continue

            # --- EXTRACTEUR DE COMPOSANTS ---
            if cat in components_by_cat:
                for item in cat_table:
                    slug_parent = item.get("id")
                    if slug_parent in new_data[cat]["details"]:
                        comps = new_data[cat]["details"][slug_parent].get("components", [])
                        for c in comps:
                            comp_entry = {
                                "parent_fr": item.get("n_fr"),
                                "n_fr": c.get("n_fr"),
                                "n_en": c.get("n_en"),
                                "p": c.get("p", 0.0),
                                "p90": c.get("p90", 0.0),
                                "v": c.get("v", 0),
                                "vr": c.get("vr", 0.0),
                                "ds": c.get("ds", 0.0),
                                "f": c.get("f", 0),
                                "qty": c.get("qty", 1),
                                "Slug": c.get("slug")
                            }
                            if "p_max" in c:
                                comp_entry.update({
                                    "p_max": c.get("p_max", 0.0),
                                    "p90_max": c.get("p90_max", 0.0),
                                    "v_max": c.get("v_max", 0),
                                    "vr_max": c.get("vr_max", 0.0),
                                    "ds_max": c.get("ds_max", 0.0),
                                    "f_max": c.get("f_max", 0)
                                })
                            components_by_cat[cat].append(comp_entry)

            # --- STRUCTURE DE L'ONGLET PRINCIPAL (SETS) ---
            df = pd.DataFrame(cat_table)
            df = df.rename(columns={"id": "Slug"})

            columns_order = list(columns_order_base)
            if "p_max" in df.columns:
                columns_order += ["p_max", "p90_max", "v_max", "vr_max", "ds_max", "f_max"]
            columns_order.append("Slug")

            columns_order = [col for col in columns_order if col in df.columns]
            df = df[columns_order]
            df = df.rename(columns=friendly_names)

            sheet_name = cat.capitalize()[:30]
            excel_sheets[sheet_name] = df

        # --- STRUCTURE DES ONGLETS COMPOSANTS ---
        target_components = [
            ("warframes", "Warframes Composants"),
            ("armes", "Armes Composants"),
            ("equipements", "Equipements Composants")
        ]

        for cat_key, sheet_title in target_components:
            list_comps = components_by_cat[cat_key]
            if list_comps:
                df_comps = pd.DataFrame(list_comps)
                df_comps = df_comps.drop_duplicates(subset=["Slug", "parent_fr"])
                df_comps = df_comps.sort_values(by=["parent_fr", "n_fr"])
                
                columns_order_comps = ["parent_fr"] + list(columns_order_base) + ["qty"]
                if "p_max" in df_comps.columns:
                    columns_order_comps += ["p_max", "p90_max", "v_max", "vr_max", "ds_max", "f_max"]
                columns_order_comps.append("Slug")

                columns_order_comps = [col for col in columns_order_comps if col in df_comps.columns]
                df_comps = df_comps[columns_order_comps]
                df_comps = df_comps.rename(columns=friendly_names)
                
                excel_sheets[sheet_title] = df_comps

        # ==============================================================================
        # 3. ÉCRITURE ET POLISSAGE DES CELLULES VIA OPENPYXL
        # ==============================================================================
        excel_path = DATA_DIR / "Warframe_Prices_Latest.xlsx"
        
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            for sheet_name, df in excel_sheets.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Récupération de la feuille openpyxl pour appliquer le style personnalisé
                worksheet = writer.sheets[sheet_name]
                
                # OPTIMISATION 1 : Ajustement automatique de la largeur des colonnes
                for col in worksheet.columns:
                    # On calcule la longueur max en caractères du contenu de la colonne
                    max_len = 0
                    col_letter = col[0].column_letter # Récupère la lettre (A, B, C...)
                    
                    for cell in col:
                        if cell.value is not None:
                            max_len = max(max_len, len(str(cell.value)))
                    
                    # On applique la largeur calculée + une marge de 4 caractères pour respirer
                    worksheet.column_dimensions[col_letter].width = max(max_len + 4, 12)
                
                # OPTIMISATION 2 : Figer la première ligne (En-têtes toujours visibles au défilement)
                worksheet.freeze_panes = "A2"

        print(f"✅ Fichier Excel permanent optimisé créé avec succès : {excel_path.name}")

    except ImportError:
        print("⚠️ Erreur : Les bibliothèques 'pandas' ou 'openpyxl' manquent à l'appel.")
    except Exception as e:
        print(f"❌ Impossible de générer le fichier Excel : {e}")

    with open(BLACKLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(list(blacklist), f)
        
# 3. Sauvegarde finale de l'état du scraper
    reset_date = today.isoformat() if run_type == "RESET" else (last_reset.isoformat() if last_reset else today.isoformat())
    
    with open(VERSION_PATH, 'w', encoding='utf-8') as f:
        json.dump({
            "api_version": current_api_version,  # 🆕 Version de l'API WFM technique (ex: 0.24.0)
            "items_hash": current_items_hash,    # 🆕 L'empreinte de la collection (base64) pour le prochain run
            "last_run": today.isoformat(),
            "last_full_reset": reset_date
        }, f, ensure_ascii=False, indent=2)

    print(f"🎉 Scraping {run_type} terminé avec succès !")

if __name__ == "__main__":
    main()
