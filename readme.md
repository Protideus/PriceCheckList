--------------------------------------------------------------------------------
# PriceCheckList (PCL) — Warframe Market Analytics

**PriceCheckList** est un tableau de bord analytique conçu pour optimiser le trading sur *Warframe*. En exploitant les données de l'API **Warframe Market (WFM)**, cet outil transforme des statistiques brutes en indicateurs de marché actionnables (liquidité, tendances, "hype") et séparéees en liste prédéfinies.

Le projet est entièrement **Open Source**, hébergé sur **GitHub Pages**, et maintenu de manière autonome par une infrastructure **Serverless** gràce **Github Actions**.

---

## 🌐 Pour les Utilisateurs

L'application permet de filtrer et trier des milliers d'objets (Warframes, Armes, Mods, Arcanes, etc.) selon 6 indicateurs mathématiques clés :

*   **Prix d'Équilibre** : Le prix de référence de l'objet basé sur la Moyenne pondérée par les volumes des dernières 48 heures.
*   **Variation 90j** : Il s'agit du pourcentage de variation entre le prix actuel et la moyenne mobile d'il y a 90 jours.
*   **Hype Ratio** : Il divise le volume des dernières 48 heures par la moyenne quotidienne des 90 derniers jours. 
*   **Donchian Score** : La position du prix actuel au sein de son canal de Donchian (le plus haut et le plus bas historiques des 90 derniers jours), exprimée de 0% à 100%.
*   **Volumétrie** : Le volume de transactions réelles sur les dernières 48 heures.
*   **Indice de Fiabilité** : Le marché de WFM étant auto-déclaratif, certains acteurs tentent de fausser les statistiques (*Market Cornering* ou *Price Dumping*). Cet indice tente de détecter les irrégularités dans les stats.
👉 *Pour une explication approfondie de la méthodologie et des conseils de trading, consultez le guide.md.*

🗂️ **Structure et Harmonisation des 8 Catégories** : 
1. **Warframes :** Uniquement les Sets complets des Warframes Primes.
2. **Armes :** Uniquement les Sets complets (Prime, Syndicat, Vandal, Wraith...).
3. **Compagnons & Équipements Primes :** Uniquement les Sets complets (Sentinelles, Archwings, Colliers).
4. **Reliques :** Toutes les reliques (Lith, Meso, Neo, Axi, Requiem).
5. **Mods :** Tous les mods du jeu.
6. **Arcanes :** Toutes les arcanes.
7. **Composants & Ressources :** Uniquement les marchandises unitaires incontournables du commerce de fin de jeu et privées de structure en "Set" (ex: Parties construites de *Necramech*, Lentilles de Focus, Étoiles/Sculptures Ayatan).
8. **Le WFM50** : Les 50 items avec le plus gros volume de ventes parmi les 7 catégories précédentes.
👉 Afin de purifier l'interface graphique et de s'aligner sur l'économie moderne du jeu (exclusion des Poissons et Gemmes obsolètes), une règle d'or est appliquée : **Si un équipement s'échange sous forme de "Set", seuls les Sets complets sont conservés.** Les composants isolés (schémas, canons, culasses) sont purgés pour éviter les doublons.

---

## 🛠️ Pour les Développeurs (Architecture Technique)

PCL est un exemple d'application de données "statique-dynamique". Il n'utilise aucune base de données traditionnelle (SQL/NoSQL), ce qui permet un hébergement gratuit et une maintenance zéro.

### 0.📂 Architecture du Projet GitHub
L'organisation des fichiers au sein du dépôt est structurée pour séparer l'interface, les données et la logique d'automatisation :

Racine du projet :
*   index.html : Le cœur de l'interface utilisateur et de la logique de visualisation
*   readme.md : Le fichier de présentation et de documentation technique.
*   guide.md : Le guide détaillé expliquant la méthodologie des indicateurs économiques
*   PCL_background.jpg : L'image de fond et de prévisualisation de l'interface PCL

**/data** : Regroupe les 18 fichiers JSON générés par le script et maintenus à jour automatiquement (comprenant les fichiers de tables et de détails pour chaque catégorie)

**/scripts** : 
*   wfm_scraper.py : Le script Python chargé du scraping de l'API et du calcul des indicateurs. Déclenchement quotidien.
*   wfm_scraper_50only : La mise à jour horaire du WFM50.
*   googlesheets_scraper.py : Le script chargé de lire le Google Sheets du clan qui contient des astuces sur les items. Ce script nécessite un compte de service google et une clé placée dans les secrets du projet Github.

**/.github/workflows** : wfm_scraper.yml , wfm_scraper_50only.yml et googlesheets_scraper.yml : Les fichiers de configuration au format YAML pilotant l'automatisation via GitHub Actions


### 1. Automatisation via GitHub Actions
Le rafraîchissement des données est piloté par un workflow **YAML** dans GitHub Actions. Ce script Python s'exécute périodiquement pour :
*   Scanner l'API Warframe Market.
*   Calculer les indicateurs économiques (moyennes mobiles, lissage "Forward Fill" pour combler les jours sans ventes) [2].
*   Générer des fichiers JSON statiques dans le répertoire `/data`.
*   Puisque les scripts travaillent sur les mêmes fichiers, ils sont synchronisés pour ne pas fonctionner en même temps (concurrency). 

### 2. Optimisation Backend : Aspiration Courtoise 
Pour éviter le bannissement IP par le pare-feu de WFM, le script intègre des règles strictes de politesse réseau :
*    **User-Agent Dédié :** Un en-tête explicite est envoyé (`User-Agent: WF-PriceCheck-V2-Scraper`).
*    **Délai de Courtoisie :** Une pause obligatoire de `0.4s` est observée entre chaque requête (limitation à ~2,5 requêtes/seconde).
*    **Cache Différentiel & Blacklist :** Les objets n'appartenant pas aux catégories cibles sont définitivement placés dans un fichier `ignored_slugs.json`. Le script ne scanne quotidiennement que les nouveautés si l'endpoint `/v2/versions` indique qu'une mise à jour a eu lieu. Un rafraîchissement global est planifié de manière trimestrielle.
*    **Refresh trimestriel :** Tous les 90 jours, le script met à jour les données en ignorant les données existantes et sa blacklist afin d'éviter une corruption rémanente des données.

### 3. Traitement des Trous de Données (Missing Values)
Warframe Market n'enregistre aucune ligne les jours où aucune transaction n'a eu lieu sur un objet. Pour empêcher le script de planter ou de fausser les moyennes mobiles, le pipeline applique un algorithme de **Forward Fill (Dernier Prix Connu)** :
1. Génération d'un calendrier mathématique continu de 90 jours.
2. Si une date est manquante dans l'API, elle hérite automatiquement des valeurs économiques du jour valide précédent.
3. Si aucune donnée historique n'est disponible à J-30 ou J-90, la valeur bascule à `0` (indiquant un marché historiquement inactif).

### 4. Stratégie API Hybride (Transition Juin 2026)
Le script Python utilise une architecture de requêtes hybride pour gérer la migration en cours de l'API WFM [3, 4] :
*   **V2 (Stable)** : Utilisée pour le manifeste global des objets et la gestion multilingue (i18n) [4].
*   **V1 (Legacy)** : Utilisée spécifiquement pour l'historique de prix sur 90 jours (`/statistics`), le point de terminaison V2 n'étant pas encore finalisé [4, 5].
*   **Optimisation** : Un délai de sécurité (`DELAY = 0.4`) est appliqué entre chaque requête pour respecter les limites de l'API tout en assurant un scan complet [6].

### 5. Optimisation Frontend & Fluidité
L'interface a été conçue pour rester instantanée, même avec des milliers d'entrées :
*   **Partitionnement des données (Data Chunking)** : Au lieu de charger un fichier JSON massif, le backend découpe les données par catégories (`warframes.json`, `mods.json`, etc.) [7]. Le frontend ne charge que le "chunk" nécessaire à la demande, évitant ainsi la saturation de la mémoire du navigateur.
*   **Architecture "Light vs Heavy (Lazy Loading)** : À l'écriture, le script segmente les données en deux fichiers :
    * **Les fichiers Tables (`*_table.json`) :** Fichiers critiques compressés (< 150 Ko) contenant uniquement les indicateurs de tri mathématiques sous forme de clés d'une seule lettre.
    * * **Les fichiers Détails (`*_details.json`) :** Dictionnaires riches (descriptions, liens wiki, images), téléchargés de manière asynchrone par le JavaScript pour alimenter les infobulles uniquement au survol de la souris.
*   **Tailwind CSS** : Utilisation de Tailwind pour un rendu visuel moderne et ultra-léger (poids CSS minimal).
*   **Recherche i18n** : Le moteur de recherche JavaScript permet de filtrer les objets simultanément en français et en anglais grâce aux métadonnées récupérées via les headers `Language: fr/en` [6].

### 6.✍️ Module d'Enrichissement : Analyse Humaine & Astuces d'Experts (`googlesheets_scraper.py`)
Pour pallier la cécité des algorithmes face aux annonces de mises à jour ou aux cycles de la "Vault", PCL intègre un second module asynchrone connecté à un **Google Sheets** collaboratif via l'API Google Drive (`gspread`). 

#### 1. Complémentarité Stratégique (La "Distance" Data vs Humain)
Le système maintient une séparation stricte entre les données brutes et l'interprétation humaine :
* **L'API WFM** modélise le *passé* et le *présent* via des indicateurs purement mathématiques (volumes récents, cassures de canaux de Donchian, prix d'équilibre).
* **Le Google Sheet** modélise le *futur* et le *contexte* via des alertes de spéculation, des conseils de rétention de stock (Vaulting) ou des analyses d'impact sur les builds à la suite des patchnotes de Digital Extremes.

#### 2. Fonctionnement du Flux & Alignement Temporel
* **Appariement Intelligent (Fuzzy Matching)** : Pour l'intégration, le script nettoie les saisies manuelles des experts (retrait des accents, casses, espaces superflus) et utilise un algorithme de correspondance de mots. Si un expert écrit `"Chroma Prime"` ou `"Chroma Set"`, le script résout automatiquement le conflit pour cibler le slug exact `"chroma_prime_set"`.
* **Cumul non-destructif** : L'injection dans les fichiers `{categorie}_details.json` se fait par enrichissement. Le script ajoute les conseils dans un tableau `"expert_tips"` sans altérer les statistiques d'artisanat ou de prix déjà calculées. Si plusieurs experts ciblent le même objet, leurs avis se cumulent.
* **Auto-nettoyage par Péremption** : Les conseils économiques étant hautement volatiles, le script compare la date d'exécution avec la date de péremption saisie par l'expert (format `JJ/MM/AAAA`). Toute astuce obsolète est **immédiatement purgée** du fichier JSON final, évitant ainsi d'afficher des conseils de spéculation dépassés sur le site.

## 🚀 Déploiement
Le projet est configuré pour être déployé en un clic via **GitHub Pages**. Toute modification poussée sur la branche principale déclenche automatiquement la mise à jour du site et des données.

---
*Avertissement : PCL est un projet communautaire indépendant et n'est pas affilié à Digital Extremes ou Warframe Market.*
