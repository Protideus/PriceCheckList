# Base de Données PriceCheckList (`/data`)

Ce dossier contient l'ensemble des données extraites de l'API de Warframe Market (WFM) par le script de scraping, ainsi que les analyses et astuces économiques fournies par les experts du clan. L'architecture est optimisée pour le *Lazy Loading* (chargement asynchrone) afin de minimiser le poids des fichiers initiaux chargés par le client Web.

---

## 📁 Liste des Fichiers et Rôles

### 1. Fichiers de Configuration et Suivi
* **`api_version.json`** : Stocke l'état de synchronisation avec l'API de WFM. Contient la version technique du serveur (`api_version`), l'empreinte unique en base64 de la liste des objets (`items_hash`), la date du dernier run et celle du dernier `RESET` complet. Permet de déterminer automatiquement le mode de lancement (`PARTIAL`, `UPDATE` ou `RESET`).
  * 🆕 **`items_hash`** : Empreinte de sécurité (Base64/MD5) fournie par l'endpoint `/v2/versions`. Elle change instantanément dès qu'un objet est ajouté, renommé ou modifié sur Warframe Market. C'est le déclencheur officiel des runs `UPDATE`.
  * 🆕 **`last_wfm50_hourly_update`** : Stocke l'horodatage ISO de la toute dernière mise à jour flash horaire de la liste WFM50. Permet au Frontend d'indiquer l'heure exacte de fraîcheur des prix du Top 50 sans se baser sur la date du gros script quotidien.
* **`ignored_slugs.json`** : Liste brute (Array) des objets exclus du scraping pour éviter les requêtes API inutiles.

### 2. Les Fichiers Tables (`{categorie}_table.json`)
Fichiers ultra-légers chargés dès l'ouverture de l'application. Ils contiennent la liste globale des objets d'une catégorie sous forme de tableau d'objets, avec uniquement les indicateurs économiques nécessaires au tri et à l'affichage principal.

### 3. Les Fichiers Détails (`{categorie}_details.json`)
Fichiers lourds structurés sous forme de dictionnaire (`clé: valeur`) où la clé est l'identifiant (`slug`) de l'objet. Ils contiennent les données textuelles (traductions, descriptions, liens), la structure interne de l'objet (ses sous-composants enrichis avec leurs indicateurs et leurs traductions), ainsi que les astuces d'experts injectées. Ils sont chargés à la demande (ex: au survol ou au clic sur un Set).

### 4. Liste Virtuelle (`wfm50_table.json` & `wfm50_details.json`)
Une 8ème catégorie générée dynamiquement par le script. Elle regroupe les 50 objets toutes catégories confondues ayant le plus gros volume d'échange sur les dernières 48 heures (les objets les plus liquides du marché).

### 5. Fichier /Warframe_Prices_Latest.xlsx réunissant toutes les infos destiné au téléchargement.

---

## ⏱️ Fréquence de rafraîchissement (Stratégie multi-sources)

Pour optimiser les performances, respecter les quotas de l'API Warframe Market et intégrer les connaissances humaines, les fichiers sont mis à jour selon trois cycles distincts :

1. **Cycle Global (Quotidien / `wfm_scraper.py`)** : Met à jour l'intégralité des objets cibles du jeu à travers les 7 catégories principales. C'est ce script qui interroge `/v2/versions`, compare l'icône de l'empreinte (`items_hash`), détermine quels sont les 50 objets les plus liquides et fige la liste WFM50.
2. **Cycle Flash (Horaire / `wfm_top50_updater.py`)** : S'exécute toutes les heures. Sans modifier la liste des objets établie par le script quotidien, il va chercher en mode ultra-rapide les nouveaux prix du Top 50 et de leurs composants. À la fin de son exécution, il met à jour le champ `last_wfm50_hourly_update` dans `api_version.json`.
3. **Cycle d'Astuces Clan (Quotidien / `googlesheets_scraper.py`)** : S'exécute juste après le script de scraping principal. Il se connecte de manière sécurisée à un Google Sheets privé via un compte de service Google Cloud. Il récupère les conseils rédigés par les experts du clan, élimine les conseils obsolètes grâce à un système de date de péremption, et injecte dynamiquement les astuces sous forme de liste dans les fiches d'items des fichiers de détails.

---

## 🔬 Structure Précise des Données

### 📋 Format d'une Table (`_table.json`)
```json
[
  {
    "id": "frost_prime_set",
    "n_fr": "Frost Prime - Set",
    "n_en": "Frost Prime Set",
    "p": 79.4,
    "p90": 8.6,
    "v": 81,
    "vr": 0.7,
    "ds": 94.0,
    "f": 3
  }
]
🔍 Format des Détails (_details.json)JSON{
{
  "frost_prime_set": {
    "desc_fr": "En plus des Pouvoirs polaires de Frost, Frost Prime dispose de polarités de Mods uniques...",
    "desc_en": "Frost Prime has the same chilling abilities as Frost but provides unique mod polarities...",
    "wiki_en": "[https://wiki.warframe.com/w/Frost_Prime](https://wiki.warframe.com/w/Frost_Prime)",
    "icon": "items/images/en/frost_prime_set.4f8ff8605be1afaab9a0e5cc3c67cb21.png",
    "expert_tips": [
      {
        "author": "Protideus",
        "text": "Attention ! Cet item subit une forte spéculation suite à sa récente résurgence Prime. Attendez avant d'acheter."
      }
    ],
    "components": [
      {
        "slug": "frost_prime_blueprint",
        "qty": 1,
        "n_fr": "Schéma Frost Prime",
        "n_en": "Frost Prime Blueprint",
        "p": 15.0,
        "p90": -1.2,
        "v": 45,
        "vr": 1.1,
        "ds": 42.5,
        "f": 3
      },
      {
        "slug": "frost_prime_systems",
        "qty": 1,
        "n_fr": "Systèmes Frost Prime",
        "n_en": "Frost Prime Systems",
        "p": 22.5,
        "p90": 4.0,
        "v": 32,
        "vr": 0.9,
        "ds": 78.0,
        "f": 3
      }
    ]
  }
}
```

Note 1 : Pour les catégories sans composants (Mods, Arcanes, Reliques), la liste components est présente mais vide [].

Note 2 : Le champ expert_tips est une liste ([]). Si plusieurs experts rédigent un conseil sur un même objet, les astuces se cumuleront les unes à la suite des autres sans s'écraser.

---

## 📈 Signification des Indicateurs ÉconomiquesChaque objet (et chaque composant interne) dispose d'un set d'indicateurs standardisés calculés à partir de l'historique des prix des dernières 48 heures et des 90 derniers jours :
| Clé | Type | Signification | Origine / Logique de calcul |
| :--- | :--- | :--- | :--- |
| **p** | float | Prix d'Équilibre Actuel | Moyenne des prix pondérée par les volumes des dernières 48h. Si aucun échange récent, repli automatique sur la dernière Moyenne Mobile (moving_avg) des 90 jours. |
| **p90** | float | Évolution sur 90 jours (%) | Variation en pourcentage entre le prix d'équilibre actuel (p) et la moyenne mobile d'il y a 90 jours. |
| **v** | int | Volume Récent | Quantité totale de l'objet échangée (acheté/vendu) au cours des dernières 48 heures. |
| **vr** | float | Volume Relatif | Ratio d'activité. Compare le volume des dernières 24h à la moyenne journalière historique sur 90 jours. Un vr > 1.5 indique une forte hausse de la demande/liquidité. |
| **ds** | float | Score de Donchian (0-100) | Positionnement du prix actuel par rapport aux extrêmes (Minimum et Maximum des médianes) des 90 derniers jours. 0 = Prix au plus bas historique, 100 = Sommet historique. |
| **f** | int | Indice de Fiabilité (0 à 3) | Score de confiance mathématique du prix calculé. Dégradé si les prix de vente s'éloignent anormalement des médianes historiques, si le volume global sur 90 jours est inférieur à 30 unités, ou si le marché est trop instable. |

-

## 🃏 Cas particulier des objets à Rangs (Mods & Arcanes)
Pour les objets possédant un système de progression (comme les Mods ou les Arcanes), la fonction de calcul sépare strictement les données. Le dictionnaire inclut alors les indicateurs pour le Rang 0 (clés de base : p, v, etc.) ET le Rang Maximum via des clés suffixées _max :
p_max, p90_max, v_max, vr_max, ds_max, f_max

---
