# Warframe Market Price Scraper - V2

Ce projet est un outil de scraping, de traitement de données et d'analyse prédictive pour le site **Warframe Market (WFM)**. Conçu comme le successeur spirituel des anciens scripts (notamment PCL de Steffronté), il exploite exclusivement la nouvelle **API V2** (GoLang) de la plateforme pour générer une base de données de prix ultra-légère, fiable et hautement optimisée pour une interface web moderne.

---

## 🛑 Contexte & Constat d'Échec de la V1

L'ancien outil (PCL) a cessé de fonctionner à la suite de la fermeture définitive des endpoints de l'API V1 par Warframe Market en décembre 2025. Bien qu'un correctif d'urgence appliqué en mai 2026 ait permis de sauver la liste des objets en basculant sur la V2, l'historique des prix repose toujours sur un endpoint V1 déprécié (`/v1/items/<slug>/statistics`). 

Cette dépendance condamne l'ancien script à une rupture définitive à court terme. La **V2** réécrit l'intégralité de la logique pour s'adapter aux strictes contraintes d'architecture de KycKyc (WFM).

---

## 🛠️ Modèle Conceptuel & Stratégie d'Optimisation

Le principal défi technique réside dans le volume des données : compiler l'historique brut de milliers d'objets génère un fichier JSON monolithique de plus de 15 Mo, inutilisable pour un navigateur web. Ce projet résout ce problème via trois piliers fondamentaux.

### 1. La Contrainte des "Doubles Appels"
L'API V2 interdit la récupération simultanée des métadonnées et des prix (suppression du paramètre V1 `?include=item`). Le pipeline Python procède donc en deux temps :
* **Appel Global (Manifeste) :** Récupération de l'annuaire complet des items via `/v2/items`.
* **Appels Individuels (Boucle synchrone) :** Requête spécifique par objet sur l'endpoint `/v2/items/{slug}/statistics` pour extraire l'historique macro des 90 jours (`90_days`).

### 2. Aspiration Courtoise (Rate Limiting & Cache)
Pour éviter le bannissement IP par le pare-feu de WFM, le script intègre des règles strictes de politesse réseau :
* **User-Agent Dédié :** Un en-tête explicite est envoyé (`User-Agent: WF-PriceCheck-V2-Scraper`).
* **Délai de Courtoisie :** Une pause obligatoire de `0.4s` est observée entre chaque requête (limitation à ~2,5 requêtes/seconde).
* **Cache Différentiel & Blacklist :** Les objets n'appartenant pas aux catégories cibles sont définitivement placés dans un fichier `ignored_slugs.json`. Le script ne scanne quotidiennement que les nouveautés si l'endpoint `/v2/versions` indique qu'une mise à jour a eu lieu. Un rafraîchissement global est planifié de manière trimestrielle.

### 3. Architecture "Light vs Heavy" (Lazy Loading)
À l'écriture, le script segmente les données en deux fichiers :
* **Les fichiers Tables (`*_table.json`) :** Fichiers critiques compressés (< 150 Ko) contenant uniquement les indicateurs de tri mathématiques sous forme de clés d'une seule lettre.
* **Les fichiers Détails (`*_details.json`) :** Dictionnaires riches (descriptions, liens wiki, images), téléchargés de manière asynchrone par le JavaScript pour alimenter les infobulles uniquement au survol de la souris.

---

## 🗂️ Structure et Harmonisation des 7 Catégories

Afin de purifier l'interface graphique et de s'aligner sur l'économie moderne du jeu (exclusion des Poissons et Gemmes obsolètes), une règle d'or est appliquée : **Si un équipement s'échange sous forme de "Set", seuls les Sets complets sont conservés.** Les composants isolés (schémas, canons, culasses) sont purgés pour éviter les doublons.

1. **Warframes :** Uniquement les Sets complets des Warframes Primes.
2. **Armes :** Uniquement les Sets complets (Primes, Syndicats, Vandale, Wraith, Invasion).
3. **Compagnons & Équipements Primes :** Uniquement les Sets complets (Sentinelles, Archwings, Colliers).
4. **Reliques :** Toutes les reliques (Lith, Meso, Neo, Axi, Requiem).
5. **Mods :** Tous les mods du jeu (avec injection manuelle algorithmique des mods *Umbra* absents de l'API).
6. **Arcanes :** Toutes les arcanes de rechargement/amélioration.
7. **Composants & Ressources :** Uniquement les marchandises unitaires incontournables du commerce de fin de jeu et privées de structure en "Set" (ex: Parties construites de *Necramech*, Lentilles de Focus, Étoiles/Sculptures Ayatan).

---

## 📊 Algorithmes d'Analyse Économique (Le Dictionnaire Light)

Pour éliminer le bruit des variations quotidiennes et protéger l'utilisateur contre les manipulations de prix, le script Python n'enregistre pas l'historique brut. Il calcule en amont des indicateurs de tendance macroéconomiques.

Chaque ligne du fichier léger (`*_table.json`) est compressée sous cette forme :
```json
{
  "id": "chroma_prime_set",
  "p": 65,
  "p30": 80,
  "p90": 140,
  "v": 42,
  "vr": 2.4,
  "f": 3
}

```

### Spécifications des Clés :

* `id` : **Slug unique** d'identification de l'objet sur Warframe Market.
* `p`  : **Prix Actuel**. Moyenne mobile calculée sur les 7 derniers jours pour lisser les anomalies du week-end.
* `p30` : **Prix Moyen à J-30** (Historique du mois précédent).
* `p90` : **Prix Moyen à J-90** (Historique à trois mois).
* `v`  : **Volume**. Nombre de transactions déclarées lors des dernières 24 heures.
* `vr` : **Volume Ratio (Momentum)**. Ratio mesurant l'attractivité soudaine de l'item ($\text{Volume}_{24\text{h}} / \text{Volume moyen}_{90\text{j}}$). Un score $> 2$ déclenche un badge *« 🔥 Très recherché »* sur l'interface, un score $< 0.3$ indique un *« 💤 Marché calme »*.
* `f`  : **Indice de Fiabilité**. Score de confiance noté de 0 à 3 calculé par des barrières de contrôle statistiques :
* *Alerte Donchian Channel :* Perte d'un point si l'écart de prix journalier ($\text{Max} - \text{Min}$) est disproportionné par rapport à la médiane (détection des faux comptes acheteurs/vendeurs).
* *Alerte Pump & Dump :* Perte d'un point si le volume et le prix subissent une explosion simultanée et déconnectée de la courbe de tendance sur 7 jours.
* *Alerte Volume Mort :* Perte d'un point si l'item souffre de trous de données trop importants (moins de 45 jours de ventes enregistrées sur les 90 jours analysés).



---

## 📉 Traitement des Trous de Données (Missing Values)

Warframe Market n'enregistre aucune ligne les jours où aucune transaction n'a eu lieu sur un objet. Pour empêcher le script de planter ou de fausser les moyennes mobiles, le pipeline applique un algorithme de **Forward Fill (Dernier Prix Connu)** :

1. Génération d'un calendrier mathématique continu de 90 jours.
2. Si une date est manquante dans l'API, elle hérite automatiquement des valeurs économiques du jour valide précédent.
3. Si aucune donnée historique n'est disponible à J-30 ou J-90, la valeur bascule à `0` (indiquant un marché historiquement inactif).

---

## 🚀 Roadmap

* [x] Analyse technique des limitations de l'API V2 et des comportements de marché.
* [x] Formalisation du modèle conceptuel et de la structure du dictionnaire optimisé.
* [ ] Branchement de la logique de récupération des prix (`/statistics`) sur la base de code Python existante.
* [ ] Codage des filtres de catégorisation et de l'algorithme d'extrapolation des trous de données.
* [ ] Écriture des fonctions d'exportation séparées (`_table.json` et `_details.json`).
* [ ] Déploiement de l'automatisation via GitHub Actions (Scraping et compression Brotli/Gzip nocturne).
* [ ] Développement du frontend web asynchrone.

