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

# Configuration des chemins relative à la RACINE du projet (Working Directory)
BASE_DIR = Path(".") # Cible la racine là où GitHub Actions se positionne
DATA_DIR = BASE_DIR / "data"
BLACKLIST_PATH = DATA_DIR / "ignored_slugs.json"
VERSION_PATH = DATA_DIR / "api_version.json"

CATEGORIES = ["warframes", "armes", "equipements", "reliques", "mods", "arcanes", "ressources"]

# ==============================================================================
# FONCTIONS UTILITAIRES & MATHÉMATIQUES
# ==============================================================================

def categorize_item(tags, slug):
    """Filtre l'objet dans l'une des 7 catégories. Ne garde que les Sets si applicable."""
    is_set = slug.endswith("_set")
    if "warframe" in tags: return "warframes" if is_set else "ignore"
    if "weapon" in tags: return "armes" if is_set else "ignore"
    if any(t in tags for t in ["sentinel", "archwing", "kubrow"]): return "equipements" if is_set else "ignore"
    if "relic" in tags: return "reliques"
    if "mod" in tags: return "mods"
    if "arcane_enhancement" in tags: return "arcanes"
    if any(t in tags for t in ["necramech", "focus_lens", "ayatan", "resource"]): return "ignore" if is_set else "ressources"
    return "ignore"

def calculate_economic_indicators(stats_data):
    """Calcule les indicateurs allégés (p, p30, p90, v, vr, f) avec Forward Fill."""
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

# ==============================================================================
# LOGIQUE DE CACHE ET D'ARCHITECTURE
# ==============================================================================

def load_cache():
    """Charge les données existantes pour le run différentiel."""
    cache = {cat: {"table": {}, "details": {}} for cat in CATEGORIES}
    for cat in CATEGORIES:
        table_path = DATA_DIR / f"{cat}_table.json"
        details_path = DATA_DIR / f"{cat}_details.json"
        
        if table_path.exists():
            try:
                with open(table_path, 'r', encoding='utf-8') as f:
                    for item in json.load(f):
                        cache[cat]["table"][item["id"]] = item
            except: pass
            
        if details_path.exists():
            try:
                with open(details_path, 'r', encoding='utf-8') as f:
                    cache[cat]["details"] = json.load(f)
            except: pass
    return cache

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Évaluation de l'état (RESET, UPDATE ou PARTIAL)
    current_version = None
    try:
        res = requests.get(f"{BASE_URL}/versions", headers=HEADERS_EN, timeout=10)
        current_version = res.json().get("data", {}).get("version")
    except: pass

    saved_version = None
    last_reset = None
    if VERSION_PATH.exists():
        try:
            with open(VERSION_PATH, 'r') as f:
                v_data = json.load(f)
                saved_version = v_data.get("version")
                last_reset = datetime.fromisoformat(v_data.get("last_full_reset", "2000-01-01"))
        except: pass

    # Détermination du mode de run
    run_type = "PARTIAL"
    today = datetime.utcnow()
    
    if not last_reset or (today - last_reset).days >= 90:
        run_type = "RESET"
    elif current_version != saved_version:
        run_type = "UPDATE"

    print(f"🚀 Démarrage du Scraper V3 | Mode : {run_type}")

    # 2. Gestion de la Blacklist
    blacklist = set()
    if run_type != "RESET" and BLACKLIST_PATH.exists():
        with open(BLACKLIST_PATH, 'r') as f:
            blacklist = set(json.load(f))

    # 3. Chargement du Cache
    cache = load_cache() if run_type != "RESET" else {cat: {"table": {}, "details": {}} for cat in CATEGORIES}
    
    # Préparation des nouveaux dictionnaires
    new_data = {cat: {"table": [], "details": {}} for cat in CATEGORIES}
    if run_type == "PARTIAL":
        # On transfère directement les vieux détails, on ne les touchera pas
        for cat in CATEGORIES:
            new_data[cat]["details"] = cache[cat]["details"]

    # 4. Aspiration du Manifeste (Global)
    res_manifest = requests.get(f"{BASE_URL}/items", headers=HEADERS_EN)
    all_items = res_manifest.json().get("data", [])
    
    items_to_process = []
    for item in all_items:
        slug = item.get("slug", "")
        if slug in blacklist:
            continue
            
        category = categorize_item(item.get("tags", []), slug)
        if category == "ignore":
            blacklist.add(slug)
        else:
            items_to_process.append({"slug": slug, "cat": category})

    total = len(items_to_process)
    print(f"🎯 {total} objets valides. Début de la boucle des prix...")

    # 5. Boucle Principale
    for index, obj in enumerate(items_to_process):
        slug = obj["slug"]
        cat = obj["cat"]
        
        # A. Récupération des Statistiques (OBLIGATOIRE TOUS LES JOURS)
        try:
            res_stats = requests.get(f"{BASE_URL}/items/{slug}/statistics", headers=HEADERS_EN, timeout=10)
            if res_stats.status_code == 200:
                indicators = calculate_economic_indicators(res_stats.json().get("data", {}))
                
                # B. Gestion des Métadonnées (Descriptions, Noms FR/EN)
                needs_full_fetch = False
                n_fr, n_en = slug, slug
                
                if run_type == "RESET":
                    needs_full_fetch = True
                elif run_type == "UPDATE" and slug not in cache[cat]["details"]:
                    needs_full_fetch = True
                else:
                    # PARTIAL ou UPDATE sur un vieil objet : On recycle les textes locaux
                    old_table_entry = cache[cat]["table"].get(slug, {})
                    n_fr = old_table_entry.get("n_fr", slug)
                    n_en = old_table_entry.get("n_en", slug)

                # Si l'objet est nouveau ou qu'on est en RESET, on fait la grosse requête de détails
                if needs_full_fetch:
                    time.sleep(DELAY) # Pause avant la 2ème requête
                    res_en = requests.get(f"{BASE_URL}/items/{slug}", headers=HEADERS_EN)
                    res_fr = requests.get(f"{BASE_URL}/items/{slug}", headers=HEADERS_FR)
                    
                    if res_en.status_code == 200 and res_fr.status_code == 200:
                        data_en = res_en.json().get("data", {}).get("item", {}).get("items_in_set", [])
                        data_fr = res_fr.json().get("data", {}).get("item", {}).get("items_in_set", [])
                        
                        # Trouver le bon objet dans le set
                        item_en = next((i for i in data_en if i.get("url_name") == slug), {})
                        item_fr = next((i for i in data_fr if i.get("url_name") == slug), {})
                        
                        n_fr = item_fr.get(f"fr", {}).get("item_name", slug)
                        n_en = item_en.get(f"en", {}).get("item_name", slug)
                        
                        new_data[cat]["details"][slug] = {
                            "desc_fr": item_fr.get("fr", {}).get("description", ""),
                            "desc_en": item_en.get("en", {}).get("description", ""),
                            "wiki_fr": item_fr.get("fr", {}).get("wiki_link", ""),
                            "icon": item_en.get("icon", "")
                        }

                # Ajout de l'entrée dans le fichier léger
                new_data[cat]["table"].append({"id": slug, "n_fr": n_fr, "n_en": n_en, **indicators})

        except Exception as e:
            print(f"⚠️ Erreur sur {slug} : {e}")
            
        time.sleep(DELAY)
        if (index + 1) % 100 == 0:
            print(f"🕒 {index + 1}/{total} traités...")

    # 6. Sauvegarde Optimisée
    for cat in CATEGORIES:
        # On sauvegarde toujours les tables
        with open(DATA_DIR / f"{cat}_table.json", 'w', encoding='utf-8') as f:
            json.dump(new_data[cat]["table"], f, ensure_ascii=False, separators=(',', ':'))
            
        # On ne sauvegarde les détails que si on les a modifiés (UPDATE ou RESET)
        if run_type in ["UPDATE", "RESET"]:
            with open(DATA_DIR / f"{cat}_details.json", 'w', encoding='utf-8') as f:
                json.dump(new_data[cat]["details"], f, ensure_ascii=False)

    with open(BLACKLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(list(blacklist), f)
        
    # Mise à jour du fichier de version
    reset_date = today.isoformat() if run_type == "RESET" else (last_reset.isoformat() if last_reset else today.isoformat())
    with open(VERSION_PATH, 'w') as f:
        json.dump({
            "version": current_version, 
            "last_run": today.isoformat(),
            "last_full_reset": reset_date
        }, f)

    print(f"🎉 Scraping {run_type} terminé ! Fichiers mis à jour avec succès.")

if __name__ == "__main__":
    main()
