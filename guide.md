# 📊 Guide de l'Utilisateur : Comprendre les Indicateurs Économiques

Bienvenue sur **PriceCheckList (PCL)**, l'outil de screening macro-économique pour les traders, boursicoteurs et vétérans de Warframe. 

Contrairement aux plateformes d'exécution comme *Warframe.market (WFM)* qui n'offrent qu'une vision atomique (item par item), PCL agrège, filtre et nettoie les données pour vous offrir une **vue d'ensemble sectorielle et dynamique** du marché. 

Ce guide vous explique le fonctionnement de l'outil, la logique de nos indicateurs et la réalité technique qui régit nos flux de données.

---

## 1. 🔍 La nature des données (D'où viennent les informations ?)

Toutes les données affichées sur cette application proviennent de l'API de **Warframe Market (WFM)**. Cependant, pour bien interpréter les graphiques et les tableaux, il est fondamental de comprendre comment ces informations sont générées :

* **Des ventes déclarées, pas des ventes vérifiées :** Warframe Market est une plateforme tierce totalement indépendante de *Digital Extremes*. L'API ne lit pas les transactions réelles au sein du jeu. L'historique repose uniquement sur les vendeurs qui cliquent manuellement sur le bouton **"Vendu"** pour clôturer leurs annonces.
* **Une tendance globale sur 90 jours :** Bien que les données soient déclaratives, compiler et lisser cet historique sur une période de **90 jours** permet d'obtenir une excellente approximation mathématique de l'état réel du marché.

---

## 🧭 Philosophie du Marché PCL (La Règle d'Or)

Le catalogue est sectorisé en 7 listes stratégiques :
1. **Warframes** (Sets complets Prime)
2. **Armes** (Sets complets Prime, Syndicat, Vandal, Wraith...)
3. **Compagnons & Équipements** (Sentinelles, Archwings, Colliers...)
4. **Reliques** (Lith, Meso, Neo, Axi, Requiem)
5. **Mods** (Tous les mods du jeu)
6. **Arcanes** (Toutes les arcanes)
7. **Composants & Ressources** (Marchandises unitaires majeures : Necramech, Lentilles, Ayatans...)
Pour purifier l'interface et coller à l'économie moderne du jeu, PCL applique un filtrage strict : **Seuls les Sets complets sont conservés** pour les Warframes, Armes et Compagnons. Les composants isolés (schémas, canons, systèmes) sont purgés pour éliminer le bruit visuel et statistique.

---

## 📊 Comprendre les Indicateurs (Les 6 Colonnes)

Chaque tableau comparatif présente 6 indices clés, calculés pour vous aider à prendre des décisions d'investissement en quelques secondes.

### 1. `p` : Prix d'Équilibre
* **Qu'est-ce que c'est ?** Le prix de référence de l'objet basé sur le `wa_price` (Moyenne pondérée par les volumes) des dernières 48 heures.
* **Pourquoi c'est fiable ?** Contrairement à une moyenne simple, le prix pondéré accorde plus d'importance aux volumes réels. Si 100 joueurs achètent un item à 40 pl et qu'un seul l'achète par erreur à 300 pl, `p` restera ancré à 40 pl.
* **Comment calculer ?** p (Prix d'Équilibre) = wa_price des dernières 48h.



### 2. `𝚫90` : Variation 90j
* **Qu'est-ce que c'est ?** La tendance macro-économique à long terme. Il s'agit du pourcentage de variation entre le prix actuel et la moyenne mobile d'il y a 90 jours.
* **Comment l'utiliser ?** Idéal pour repérer les objets *Vaulted* qui prennent de la valeur de mois en mois ou, à l'inverse, les items en dévaluation chronique.
* **Comment calculer ?** Δ90 (Variation 90j) = (p_actuel - p_90j) / p_90j [Utiliser la moving_avg de la journée d'il y a 90 jours pour p_90j].



### 3. `VR` : Hype Ratio (Volume Ratio)
* **Qu'est-ce que c'est ?** Le détecteur de mouvements de foule. Il divise le volume des dernières 48 heures par la moyenne quotidienne des 90 derniers jours. 
* **`VR = 1.0`** : Marché parfaitement stable. 
* **`VR > 1.5`** : Activité anormale. 
* **`VR > 2.0` (Feu/Rouge)** : Explosion de la demande ou spéculation massive (souvent liée à un buff meta, un rework ou une annonce de Vault).
* **Comment calculer ?** VR (Hype Ratio) = Volume_48h_ramené_sur_24h / Volume_moyen_journalier_90j



### 4. `DS` : Donchian Score (Position Cycle)
* **Qu'est-ce que c'est ?** La position du prix actuel au sein de son canal de Donchian (le plus haut et le plus bas historiques des 90 derniers jours), exprimée de 0% à 100%.
* **Proche de 100%** : L'item touche son sommet historique. **Signal de vente** pour vider vos stocks.
* **Proche de 0%** : L'item est au plus bas historique. **Signal d'achat / investissement** à long terme.
* **Comment calculer ?** DS (Donchian Score) = ((p_actuel - donch_bot) / (donch_top - donch_bot)) * 100



### 5. `VL` : Volumétrie / Liquidité
* **Qu'est-ce que c'est ?** Le volume de transactions réelles sur les dernières 48 heures.
* **Le conseil du trader :** Un `DS` très élevé (sommet) associé à un `VL` ridicule est un **faux signal** (marché illiquide). Un vrai mouvement de marché sain demande un `VL` robuste.
* **Comment calculer ?** VL (Liquidité) = Volume des dernières 48h.



### 6. `F` : Indice de Fiabilité (Score sur 3 ❤️)*
* **Qu'est-ce que c'est ?** Notre bouclier algorithmique contre les manipulations de marché. Le marché de WFM étant auto-déclaratif, certains acteurs tentent de fausser les statistiques (*Market Cornering* ou *Price Dumping*).
* **Comment le score baisse :**
 * Écart anormal entre le prix médian et la moyenne (suspicion de fausses ventes à prix exorbitant).
 * Transactions déclarées à un prix inférieur aux offres d'achat instantanées en cours (ventes impossibles).
 * Volume long terme trop faible pour garantir la pertinence du prix.
* **Verdict :** `3/3` = Marché sain et régulier. `1/3` ou moins = Suspicion de manipulation ou forte instabilité, soyez prudents.
* **Comment calculer ?** F (Indice de Fiabilité sur 3) = Déduire 1 point si (avg_price/median) > 1.2 ; Déduire 1 point si closed_price < max_price des offres "buy" en cours ; Déduire 1 point si le volume 90j est critique.



---

## ⚙️ Contraintes Techniques et Fraîcheur des Données

PCL extrait ses informations depuis l'API de *Warframe.market*. Pour respecter la charge des serveurs hôtes et garantir la pérennité de notre application (éviter le bannissement de nos robots), les données tournent à deux vitesses :

### 📡 Le "WFM 50" (Mise à jour Horaire)
Les **50 items générant le plus gros volume d'échange** du jeu font l'objet d'un suivi ultra-prioritaire. Leurs indices (`p`, `VR`, `F`) sont rafraîchis **toutes les heures** en tâche de fond. C'est votre salle des marchés en direct pour le *day-trading*.

### ⏳ Le Reste du Catalogue (Mise à jour Quotidienne)

---

## 🚀 Stratégies de Screening Recommandées

En combinant et en triant nos colonnes, vous pouvez appliquer des stratégies de traders professionnels :

* **La stratégie "Value Investor" (Achat bas) :** 
  Filtrez par `DS` croissant (< 15%) + `F` égal à 3 + `VL` stable. Vous trouverez les objets délaissés, au plus bas de leur prix, mais sur des marchés sains. Achetez et stockez.
* **La stratégie "Momentum Trader" (Achat-Revente rapide) :** 
  Filtrez par `VR` décroissant (> 2.0) + `VL` élevé. Vous plongez directement là où se trouve l'argent et la volatilité immédiate, idéal pour écouler rapidement vos stocks au prix fort.
* **Protégez-vous des arnaques :** Si un objet affiche un prix très alléchant mais que sa **Fiabilité (`f`)** est de `1/3` ou `0/3`, le marché est instable ou manipulé. Ne vous fiez pas aveuglément à cette valeur. De même, une hausse de prix fulgurante accompagnée d'un volume minuscule est un signal d'alarme majeur.
  
---

## 3. ⚠️ Alerte : Le risque de manipulation du marché

Puisque Warframe Market ne peut pas vérifier la réalité des échanges en jeu, la plateforme est parfois la cible de spéculateurs ou d'arnaqueurs qui tentent de manipuler les statistiques historiques.

### Les deux techniques de manipulation les plus courantes :

> ### 1️⃣ Le "Market Cornering" (Gonflement artificiel)
> Des groupes de joueurs complices créent de fausses annonces et déclarent de fausses ventes à des prix exorbitants (par exemple, déclarer plusieurs ventes d'un mod à 300 Platinum alors qu'il n'en vaut que 40). L'objectif est de faire grimper les indicateurs de prix (`p`) pour inciter les acheteurs crédules à payer l'objet au-dessus de sa vraie valeur.

> ### 2️⃣ Le "Price Dumping" (Effondrement artificiel)
> Un spéculateur déclare de fausses ventes à des prix ridiculement bas. Les algorithmes ou les joueurs honnêtes, pensant que l'objet a perdu sa valeur, s'alignent et bradent leurs biens. L'arnaqueur n'a plus qu'à racheter tous les *vrais* objets à bas prix avant de supprimer ses fausses annonces pour revendre le tout au prix fort quelques jours plus tard.

---
