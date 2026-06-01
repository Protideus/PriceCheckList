import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# ==============================================================================
# CONFIGURATION
# ==============================================================================

BASE_URL = "https://api.warframe.market/v2"
DELAY = 0.4 

HEADERS_EN = {"Accept": "application/json", "Language": "en", "User-Agent": "WF-PriceCheck-V3-Scraper"}
HEADERS_FR = {"Accept": "application/json", "Language": "fr", "User-Agent": "WF-PriceCheck-V3-Scraper"}

BASE_DIR = Path(".") # Racine du projet
DATA_DIR = BASE_DIR / "data"
BLACKLIST_PATH = DATA_DIR / "ignored_slugs.json"
VERSION_PATH = DATA_DIR / "api_version.json"

CATEGORIES = ["warframes", "armes", "equipements", "reliques", "mods", "arcanes", "ressources"]

# ==============================================================================
# FONCTIONS UTILITAIRES & MATHÉMATIQUES
# ==============================================================================

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
    if any(t in tags for t in ["necramech", "focus_lens", "ayatan", "resource"]): 
        return "ignore" if is_set else "ressources"
        
    return "ignore"

def calculate_economic_indicators(stats_data):
    """Calcule les indicateurs allégés avec Forward Fill."""
    days_90 = stats_data.get("90_days", [])
    if not days_90:
        return {"p": 0, "p30": 0, "p90": 0, "v": 0, "vr": 0, "f": 0}

    raw_data = {entry["datetime"][:10]: entry for entry in days_90}
    today = datetime.utcnow().date()
    filled_data = []
    
    last_price, last_min, last_max = 0, 0, 0
    missing_days_count = 0

    for i in range(89, -1, -1):
        target_date = (today - timedelta(days=i)).isoformat()
        if target_date in raw_data:
            entry = raw_data[target_date]
            last_price = entry.get("median", last_price)
            last_min = entry.get("min_price", last_min)
            last_max = entry.get("max_price", last_max)
            vol = entry.get("volume", 0)
        else:
            missing_days_count += 1
            vol = 0 
        filled_data.append({"median": last_price, "min": last_min, "max": last_max, "volume": vol})

    last_7 = filled_data[-7:]
    p = sum(d["median"] for d in last_7) / len(last_7) if last_7 else 0
    p30 = filled_data[-30]["median"] if len(filled_data) >= 30 else 0
    p90 = filled_data[0]["median"] if len(filled_data) >= 90 else 0
    v = filled_data[-1]["volume"]
    
    avg_vol_90 = sum(d["volume"] for d in filled_data) / len(filled_data) if filled_data else 0
    vr = round(v / avg_vol_90, 2) if avg_vol_90 > 0 else 0

    f = 3
    if missing_days_count > 45: f -= 1 
    latest = filled_data[-1]
    if latest["median"] > 0:
        if ((latest["max"] - latest["min"]) / latest["median"]) > 1.5: f -= 1 
    if vr > 3 and latest["median"] > (p30 * 1.5): f -= 1 

    return {"p": round(p, 1), "p30": round(p30, 1), "p90": round(p90, 1), "v": v, "vr": vr, "f": max(0, f)}

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
        res = requests.get(f"{BASE_URL}/versions", headers=HEADERS_EN, timeout=10)
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

    res_manifest = requests.get(f"{BASE_URL}/items", headers=HEADERS_EN)
    all_items = res_manifest.json().get("data", [])
    
    print(f"📋 {len(all_items)} objets trouvés dans le manifeste global. Filtrage...")

    # Boucle Principale
    for index, item in enumerate(all_items):
        url_name = item.get("url_name", "")
        if not url_name or url_name in blacklist:
            continue

        found_category = None
        if run_type != "RESET":
            for cat in CATEGORIES:
                if url_name in cache[cat]["table"] or url_name in cache[cat]["details"]:
                    found_category = cat
                    break

        try:
            # SCÉNARIO A : L'objet est totalement inconnu ou mode RESET
            if not found_category or run_type == "RESET":
                time.sleep(DELAY)
                res_en = requests.get(f"{BASE_URL}/items/{url_name}", headers=HEADERS_EN)
                res_fr = requests.get(f"{BASE_URL}/items/{url_name}", headers=HEADERS_FR)
                
                if res_en.status_code == 200 and res_fr.status_code == 200:
                    json_en = res_en.json().get("data", {}).get("item", {})
                    json_fr = res_fr.json().get("data", {}).get("item", {})
                    
                    tags = json_en.get("tags", [])
                    cat = categorize_item(tags, url_name)
                    
                    if cat == "ignore":
                        blacklist.add(url_name)
                        continue
                    
                    data_en = json_en.get("items_in_set", [])
                    data_fr = json_fr.get("items_in_set", [])
                    
                    item_en = next((i for i in data_en if i.get("url_name") == url_name), json_en)
                    item_fr = next((i for i in data_fr if i.get("url_name") == url_name), json_fr)
                    
                    n_fr = item_fr.get("fr", {}).get("item_name", url_name)
                    n_en = item_en.get("en", {}).get("item_name", url_name)
                    
                    new_data[cat]["details"][url_name] = {
                        "desc_fr": item_fr.get("fr", {}).get("description", ""),
                        "desc_en": item_en.get("en", {}).get("description", ""),
                        "wiki_fr": item_fr.get("fr", {}).get("wiki_link", ""),
                        "icon": item_en.get("icon", "")
                    }
                    found_category = cat
                else:
                    continue

            # SCÉNARIO B : L'objet est connu
            else:
                old_entry = cache[found_category]["table"].get(url_name, {})
                n_fr = old_entry.get("n_fr", url_name)
                n_en = old_entry.get("n_en", url_name)
                
                if run_type == "UPDATE" and url_name not in new_data[found_category]["details"]:
                    new_data[found_category]["details"][url_name] = cache[found_category]["details"].get(url_name, {})

            # Récupération des prix
            time.sleep(DELAY)
            res_stats = requests.get(f"{BASE_URL}/items/{url_name}/statistics", headers=HEADERS_EN, timeout=10)
            if res_stats.status_code == 200:
                indicators = calculate_economic_indicators(res_stats.json().get("data", {}))
                new_data[found_category]["table"].append({"id": url_name, "n_fr": n_fr, "n_en": n_en, **indicators})

        except Exception as e:
            print(f"⚠️ Erreur sur {url_name} : {e}")
            
        if (index + 1) % 100 == 0:
            print(f"🕒 {index + 1}/{len(all_items)} objets analysés...")

    # Sauvegarde des fichiers
    for cat in CATEGORIES:
        with open(DATA_DIR / f"{cat}_table.json", 'w', encoding='utf-8') as f:
            json.dump(new_data[cat]["table"], f, ensure_ascii=False, separators=(',', ':'))
            
        if run_type in ["UPDATE", "RESET"]:
            with open(DATA_DIR / f"{cat}_details.json", 'w', encoding='utf-8') as f:
                json.dump(new_data[cat]["details"], f, ensure_ascii=False)

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
