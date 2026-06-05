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
# CONFIGURATION
# ==============================================================================

BASE_URL_V2 = "https://api.warframe.market/v2"
BASE_URL_V1 = "https://api.warframe.market/v1"
DELAY = 0.4 

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
    """Filtre l'objet selon ses VRAIS tags de l'API."""
    is_set = url_name.endswith("_set")
    
    if "warframe" in tags: 
        return "warframes" if is_set else "ignore"
    if "weapon" in tags: 
        return "armes" if is_set else "ignore"
    if any(t in tags for t in ["sentinel", "archwing", "kubrow", "kavat"]): 
        return "equipements" if is_set else "ignore"
    if "relic" in tags: 
        return "reliques"
    if "mod" in tags: 
        return "mods"
    if "arcane_enhancement" in tags: 
        return "arcanes"
    if any(t in tags for t in ["necramech", "lens", "ayatan_star", "ayatan_sculpture"]): 
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
            return p_actuel, 0.0, vl, 0.0, 50.0, 1

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

        vol_24h_recent = vl / 2.0
        active_volumes = [d["volume"] for d in filled_90j if d["volume"] > 0]
        avg_vol_journalier_90j = sum(active_volumes) / len(active_volumes) if active_volumes else 0.0
        
        vr = 0.0
        if avg_vol_journalier_90j > 0:
            vr = round(vol_24h_recent / avg_vol_journalier_90j, 2)

        real_medians = [d["median"] for d in filled_90j if d["has_real_data"] and d["median"] > 0]
        ds = 50.0
        if real_medians:
            donch_bot = min(real_medians)
            donch_top = max(real_medians)
            if donch_top > donch_bot:
                ds = round(((p_actuel - donch_bot) / (donch_top - donch_bot)) * 100, 1)
                ds = max(0.0, min(100.0, ds))

        f = 3
        recent_real_days = [d for d in reversed(filled_90j) if d["has_real_data"]][:7]
        if recent_real_days:
            avg_ratio = sum(d["avg_price"] / d["median"] for d in recent_real_days if d["median"] > 0) / len(recent_real_days)
            if avg_ratio > 1.2: f -= 1
        total_volume_90j = sum(d["volume"] for d in filled_90j)
        if total_volume_90j < 30: f -= 1
        if recent_real_days:
            avg_min_ratio = sum(d["min_price"] / d["median"] for d in recent_real_days if d["median"] > 0) / len(recent_real_days)
            if avg_min_ratio < 0.6: f -= 1
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
    
    current_version = None
    try:
        res = safe_requests.get(f"{BASE_URL_V2}/versions", headers=HEADERS_EN, timeout=10)
        if res.status_code == 200:
            api_data = res.json().get("data", {})
            if isinstance(api_data, dict):
                current_version = api_data.get("version")
            elif isinstance(api_data, list) and len(api_data) > 0:
                current_version = api_data[0].get("version")
    except: 
        pass

    if not current_version:
        current_version = f"fallback_{today.strftime('%Y_%m')}"

    saved_version = None
    last_reset = None
    if VERSION_PATH.exists():
        try:
            with open(VERSION_PATH, 'r') as f:
                v_data = json.load(f)
                saved_version = v_data.get("version")
                last_reset = datetime.fromisoformat(v_data.get("last_full_reset", "2000-01-01"))
        except: 
            pass

    # Chargement et validation stricte du Cache
    cache, has_valid_cache = load_cache()
    
    blacklist = set()
    if VERSION_PATH.exists() and BLACKLIST_PATH.exists():
        try:
            with open(BLACKLIST_PATH, 'r') as f:
                blacklist = set(json.load(f))
        except:
            pass

    # Détermination du mode de run
    run_type = "PARTIAL"
    if not last_reset or (today - last_reset).days >= 90 or not has_valid_cache:
        run_type = "RESET"
        blacklist = set() # On vide la blacklist pour tout réanalyser proprement
    elif current_version != saved_version:
        run_type = "UPDATE"

    print(f"🚀 Démarrage du Scraper V3 | Mode : {run_type} (Cache valide : {has_valid_cache})")

    new_data = {cat: {"table": [], "details": {}} for cat in CATEGORIES}
    
    if run_type == "PARTIAL":
        for cat in CATEGORIES:
            new_data[cat]["details"] = cache[cat]["details"]

    res_manifest = safe_requests.get(f"{BASE_URL_V2}/items", headers=HEADERS_EN, timeout=10)
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
                res_en = safe_requests.get(f"{BASE_URL_V2}/items/{slug}", headers=HEADERS_EN, timeout=10)
                res_fr = safe_requests.get(f"{BASE_URL_V2}/items/{slug}", headers=HEADERS_FR, timeout=10)
                
                if res_en.status_code == 200 and res_fr.status_code == 200:
                    json_en = res_en.json().get("data", {})
                    json_fr = res_fr.json().get("data", {})
                    
                    tags = json_en.get("tags", [])
                    cat = categorize_item(tags, slug)
                    
                    if cat == "ignore":
                        blacklist.add(slug)
                        continue
                    
                    # Extract i18n translations (V2 structure)
                    i18n_en = json_en.get("i18n", {}).get("en", {})
                    i18n_fr = json_fr.get("i18n", {}).get("fr", {})
                    
                    # Try to get names: use 'name' key or fallback to slug
                    n_en = i18n_en.get("name") or json_en.get("name") or slug
                    n_fr = i18n_fr.get("name") or json_fr.get("name") or slug
                    
                    # 🟢 EXTRACTION BLINDÉE DES COMPOSANTS (Correction définitive des doublons et cumul V2)
                    components_blueprint = []
                    set_parts = json_en.get("setParts", [])
                    v2_items_list = json_en.get("items", [])

                    # 1. Analyse du bloc setParts
                    if isinstance(set_parts, list) and set_parts:
                        for part in set_parts:
                            comp_slug = None  # Évite l'UnboundLocalError
                            qty = 1

                            if isinstance(part, dict):
                                if part.get("setRoot", False):
                                    continue
                                comp_slug = part.get("slug") or item_id_map.get(part.get("id"))
                                qty = part.get("quantityInSet") or part.get("quantity") or 1
                            elif isinstance(part, str):
                                comp_slug = item_id_map.get(part, part)
                                qty = 1
                            else:
                                continue

                            if comp_slug and comp_slug != slug:
                                components_blueprint.append({
                                    "slug": comp_slug,
                                    "qty": qty
                                })

                    # 2. Analyse du bloc items (Indépendant, on utilise 'if' au lieu de 'elif')
                    if isinstance(v2_items_list, list) and len(v2_items_list) > 1:
                        for sub_item in v2_items_list:
                            if isinstance(sub_item, dict) and not sub_item.get("setRoot", False):
                                comp_slug = sub_item.get("slug") or item_id_map.get(sub_item.get("id"))
                                if comp_slug and comp_slug != slug:
                                    # Sécurité pour éviter d'ajouter deux fois le même composant s'il était déjà dans setParts
                                    if not any(c["slug"] == comp_slug for c in components_blueprint):
                                        components_blueprint.append({
                                            "slug": comp_slug,
                                            "qty": sub_item.get("quantityInSet") or sub_item.get("quantity") or 1
                                        })

                    new_data[cat]["details"][slug] = {
                        "desc_fr": i18n_fr.get("description", ""),
                        "desc_en": i18n_en.get("description", ""),
                        "wiki_en": i18n_en.get("wikiLink", ""),
                        "icon": i18n_en.get("icon", ""),
                        "components": [] # On va le remplir juste après avec les prix !
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

                # En mode UPDATE, on récupère le blueprint depuis le cache pour éviter d'avoir à refaire une requête V2
                old_details = cache[found_category]["details"].get(slug, {})
                old_components = old_details.get("components", [])
                for comp in old_components:
                    components_blueprint.append({
                        "slug": comp.get("slug"),
                        "qty": comp.get("qty", 1)
                    })

            # 🔄 MIGRATION POINT: Statistics endpoint - Currently V1 ONLY
            # TODO: When /v2/items/{slug}/statistics becomes available, replace:
            #   OLD: f"{BASE_URL_V1}/items/{slug}/statistics"
            #   NEW: f"{BASE_URL_V2}/items/{slug}/statistics"
            # And update calculate_economic_indicators() to parse V2 response format
            time.sleep(DELAY)
            res_stats = safe_requests.get(f"{BASE_URL_V1}/items/{slug}/statistics", headers=HEADERS_EN, timeout=10)
            
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
            # (Rempli plus haut uniquement pour les Sets)
            for comp in components_blueprint:
                comp_slug = comp.get("slug")
                comp_qty = comp.get("qty", 1)
                
                if not comp_slug:
                    continue
                    
                # Aspiration Courtoise : Pause obligatoire avant chaque sous-requête
                time.sleep(DELAY)
                
                try:
                    res_comp_stats = safe_requests.get(
                        f"{BASE_URL_V1}/items/{comp_slug}/statistics", 
                        headers=HEADERS_EN, 
                        timeout=10
                    )
                    
                    comp_indicators = {"p": 0.0, "v": 0} # Valeurs de secours (fallback)
                    
                    if res_comp_stats.status_code == 200:
                        comp_payload = res_comp_stats.json().get("payload", {})
                        if comp_payload and isinstance(comp_payload, dict):
                            comp_calc = calculate_economic_indicators(comp_payload)
                            if isinstance(comp_calc, dict):
                                # 🟢 On conserve l'intégralité des indicateurs calculés (p, p90, v, vr, ds, f)
                                comp_indicators = comp_calc
                    else:
                        print(f"   ⚠️ Code {res_comp_stats.status_code} sur les stats de {comp_slug}, fallback à 0.")
                        
                except Exception as e:
                    print(f"   ❌ Erreur sur le composant {comp_slug} : {e}")
                    comp_indicators = {"p": 0.0, "v": 0}
                    
                set_components_data.append({
                    "slug": comp_slug,
                    "qty": comp_qty,
                    **comp_indicators
                })
                
            # Injection sécurisée dans le dictionnaire de détails du Set principal
            # Si la liste est vide (Mod, Arcane, Relique...), cela ajoutera un tableau vide [] sans bug.
            # Sécurité : On s'assure que la catégorie a bien été identifiée dans notre dictionnaire
            if found_category and found_category in new_data:
                if slug in new_data[found_category]["details"]:
                    new_data[found_category]["details"][slug]["components"] = set_components_data

                new_data[found_category]["table"].append({
                    "id": slug, 
                    "n_fr": n_fr, 
                    "n_en": n_en, 
                    **indicators
                })
         
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
    wfm50_details = []
    for item in wfm50_table:
        slug = item["id"]
        if slug in details_registry:
            wfm50_details.append(details_registry[slug])

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

    with open(BLACKLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(list(blacklist), f)
        
    reset_date = today.isoformat() if run_type == "RESET" else (last_reset.isoformat() if last_reset else today.isoformat())
    with open(VERSION_PATH, 'w') as f:
        json.dump({
            "version": current_version, 
            "last_run": today.isoformat(),
            "last_full_reset": reset_date
        }, f)

    print(f"🎉 Scraping {run_type} terminé avec succès !")

if __name__ == "__main__":
    main()
