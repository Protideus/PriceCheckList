import requests
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# ==============================================================================
# CONFIGURATION & CONFIG ARCHITECTURE
# ==============================================================================
DATA_DIR = Path("data")
WFM50_TABLE_PATH = DATA_DIR / "wfm50_table.json"
WFM50_DETAILS_PATH = DATA_DIR / "wfm50_details.json"
VERSION_PATH = DATA_DIR / "version.json"

BASE_URL_V1 = "https://api.warframe.market/v1"
HEADERS = {
    "User-Agent": "PriceCheckList-FastScraper/1.0 (Contact: github.com/Protideus/PriceCheckList)",
    "Language": "fr"
}
DELAY = 0.4  # Respect de l'API de Warframe Market

# ==============================================================================
# FONCTION ÉCONOMIQUE SÉCURISÉE
# ==============================================================================
def calculate_economic_indicators(stats_data):
    """
    Calcule les indicateurs avancés à partir du bucket statistics_closed.
    Sécurisé contre les historiques vides (Donchian Score).
    """
    default_indicators = {"p": 0.0, "p90": 0.0, "v": 0, "vr": 0.0, "ds": 50.0, "f": 3}
    if not isinstance(stats_data, dict):
        return default_indicators

    # 1. Parsing des données ultra-récentes (48h heure par heure)
    hours_48 = []
    if "statistics_closed" in stats_data:
        hours_48 = stats_data["statistics_closed"].get("48hours", [])
    elif "statistics_live" in stats_data:
        hours_48 = stats_data["statistics_live"].get("48hours", [])

    total_volume_48h = 0
    weighted_price_sum = 0.0

    for entry in hours_48:
        vol = entry.get("volume", 0)
        wa_price = entry.get("wa_price", entry.get("median", 0))
        total_volume_48h += vol
        weighted_price_sum += (wa_price * vol)

    p_actuel = 0.0
    if total_volume_48h > 0:
        p_actuel = round(weighted_price_sum / total_volume_48h, 1)
    elif hours_48:
        medians_48h = [e.get("median", 0) for e in hours_48 if e.get("median", 0) > 0]
        p_actuel = round(sum(medians_48h) / len(medians_48h), 1) if medians_48h else 0.0

    vl = total_volume_48h

    # 2. Parsing des données macro (90j jour par jour)
    days_90 = []
    if "statistics_closed" in stats_data:
        days_90 = stats_data["statistics_closed"].get("90days", [])
    if not days_90 and "statistics_live" in stats_data:
        days_90 = stats_data["statistics_live"].get("90days", [])

    if not days_90:
        return {"p": p_actuel, "p90": 0.0, "v": vl, "vr": 0.0, "ds": 50.0, "f": 1}

    raw_data_90j = {}
    for entry in days_90:
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
                    "max_price": entry.get("max_price", entry.get("median", 0))
                }

    # CORRECTIF DATETIME APPLIQUÉ ICI AUSSI
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

    # CORRECTIF SÉCURITÉ MIN/MAX APPLIQUÉ ICI AUSSI
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

    return {"p": p_actuel, "p90": p90_delta, "v": vl, "vr": vr, "ds": ds, "f": f}

# ==============================================================================
# SCRIPT PRINCIPAL
# ==============================================================================
def main():
    print("⚡ Démarrage du rafraîchissement rapide WFM50...")

    if not WFM50_TABLE_PATH.exists():
        print(f"❌ Erreur : Le fichier {WFM50_TABLE_PATH} n'existe pas.")
        return

    with open(WFM50_TABLE_PATH, 'r', encoding='utf-8') as f:
        wfm50_items = json.load(f)

    if not wfm50_items:
        print("⚠️ La liste WFM50 est vide.")
        return

    print(f"🔄 Mise à jour des statistiques pour {len(wfm50_items)} objets...")
    
    updated_items = []
    
    for index, item in enumerate(wfm50_items):
        slug = item.get("id")
        n_fr = item.get("n_fr")
        n_en = item.get("n_en")
        
        print(f"  [{index+1}/{len(wfm50_items)}] Mise à jour : {n_fr}...")
        
        # Structure d'indicateurs par défaut harmonisée en cas de panne réseau complète
        indicators = {"p": item.get("p", 0.0), "p90": item.get("p90", 0.0), "v": item.get("v", 0), "vr": item.get("vr", 0.0), "ds": item.get("ds", 50.0), "f": item.get("f", 0)}
        
        try:
            url = f"{BASE_URL_V1}/items/{slug}/statistics"
            response = requests.get(url, headers=HEADERS, timeout=10)
            
            if response.status_code == 200:
                stats_payload = response.json().get("payload", {})
                indicators = calculate_economic_indicators(stats_payload)
            else:
                print(f"  ⚠️ Statut API anormal pour {slug} : {response.status_code}. Conservation des anciennes valeurs.")
                
        except Exception as e:
            print(f"  ⚠️ Erreur réseau pour {slug} : {e}. Valeurs par défaut appliquées.")
            
        updated_item = {"id": slug, "n_fr": n_fr, "n_en": n_en, **indicators}
        updated_items.append(updated_item)
        time.sleep(DELAY)

    with open(WFM50_TABLE_PATH, 'w', encoding='utf-8') as f:
        json.dump(updated_items, f, ensure_ascii=False, separators=(',', ':'))

    if VERSION_PATH.exists():
        try:
            with open(VERSION_PATH, 'r', encoding='utf-8') as f:
                v_data = json.load(f)
            v_data["last_run"] = datetime.now().strftime("%Y-%m-%d")
            with open(VERSION_PATH, 'w', encoding='utf-8') as f:
                json.dump(v_data, f)
        except Exception as e:
            print(f"⚠️ Impossible de mettre à jour version.json : {e}")

    print("✅ Liste WFM50 rafraîchie avec succès !")

if __name__ == "__main__":
    main()
