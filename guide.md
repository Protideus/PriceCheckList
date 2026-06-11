# 📊 Guide de l'Utilisateur : Comprendre les Indicateurs Économiques

Bienvenue sur **PriceCheckList (PCL)**, l'outil de screening macro-économique pour les traders, boursicoteurs et vétérans de Warframe. 

Contrairement aux plateformes d'exécution comme *Warframe.market (WFM)* qui n'offrent qu'une vision atomique (item par item), PCL agrège, filtre et nettoie les données pour vous offrir une **vue d'ensemble sectorielle et dynamique** du marché. 

Ce guide vous explique le fonctionnement de l'outil, la logique de nos indicateurs et la réalité technique qui régit nos flux de données.

---

## 1. 🔍 La nature des données (D'voù viennent les informations ?)

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

Chaque tableau comparatif presents 6 indices clés, calculés pour vous aider à prendre des décisions d'investissement en quelques secondes.

### 1. `p` : Prix d'Équilibre
* **Qu'est-ce que c'est ?** Le prix de référence de l'objet basé sur la moyenne des prix pondérée par les volumes des dernières 48 heures.
* **Pourquoi c'est fiable ?** Contrairement à une moyenne simple, le prix pondéré accorde plus d'importance aux volumes réels. Si 100 joueurs achètent un item à 40 pl et qu'un seul l'achète par erreur à 300 pl, `p` restera ancré à 40 pl.
* **Particularité :** Si aucun échange n'a eu lieu récemment (marché illiquide), un repli automatique est effectué sur la dernière Moyenne Mobile (`moving_avg`) connue sur 90 jours.

### 2. `𝚫90` : Variation 90j
* **Qu'est-ce que c'est ?** La tendance macro-économique à long terme. Il s'agit du pourcentage de variation entre le prix actuel et la moyenne mobile d'il y a 90 jours.
* **Comment l'utiliser ?** Idéal pour repérer les objets *Vaulted* qui prennent de la valeur de mois en mois ou, à l'inverse, les items en dévaluation chronique.

### 3. `VR` : Hype Ratio (Volume Ratio)
* **Qu'est-ce que c'est ?** Le détecteur de mouvements de foule. Il divise le volume des dernières 48 heures (ramené sur 24h) par la moyenne journalière historique calculée de manière stricte sur l'ensemble des 90 derniers jours.
* **Interprétation :**
 * `VR = 1.0` : Marché parfaitement stable.
 * `VR > 1.5` : Activité anormale.
 * `VR > 2.0` (Feu/Rouge) : Explosion de la demande ou spéculation massive (buff meta, rework, annonce de Vault).

### 4. `DS` : Donchian Score (Position Cycle)
* **Qu'est-ce que c'est ?** La position du prix actuel au sein de son canal de Donchian (le plus haut et le plus bas historiques des médianes réelles enregistrées sur les 90 derniers jours), exprimée de 0% à 100%.
* **Proche de 100%** : L'item touche son sommet historique. **Signal de vente** pour vider vos stocks.
* **Proche de 0%** : L'item est au plus bas historique. **Signal d'achat / investissement** à long terme.

### 5. `VL` : Volumétrie / Liquidité
* **Qu'est-ce que c'est ?** Le volume total de transactions réelles enregistrées sur les dernières 48 heures.
* **Le conseil du trader :** Un `DS` très élevé (sommet) associé à un `VL` ridicule est un **faux signal** dû à l'asphyxie du marché. Un vrai mouvement de tendance sain requiert un `VL` robuste.

### 6. `F` : Indice de Fiabilité (Score sur 3 🛡️)
* **Qu'est-ce que c'est ?** Notre bouclier algorithmique avancé contre la spéculation, l'illiquidité et les manipulations de marché (*Market Cornering* ou *Price Dumping*). Au lieu de simplement valider la cohérence instantanée des prix, cet indice évalue la **santé structurelle de l'écosystème global** de l'objet sur 90 jours.
* **La logique de dégradation (Score initial à 3/3) :**
 1. 🛑 **Alerte Marché Fantôme (Baisse de 1 point) :** Déclenché si l'objet enregistre moins de 15 jours d'activité transactionnelle réelle sur les 90 derniers jours, OU si son volume cumulé sur 90 jours est inférieur à 45 unités. Un manque structurel de liquidité rend le prix instable et facilement manipulable.
 2. ⚡ **Alerte Volatilité Crétacée (Baisse de 1 point) :** Déclenché si l'écart entre les extrêmes du canal de Donchian est excessif (prix maximum historique plus de 5 fois supérieur au prix minimum sur 90 jours). Signale un marché sujet aux cracks boursiers ou à des vagues spéculatives agressives.
 3. 📉 **Alerte Manipulation Récente (Baisse de 1 point) :** Déclenché si, sur les 7 derniers jours calendaires, l'écart moyen entre le prix de vente (`avg_price`) et la médiane (`median`) dépasse un ratio de 1.2. C'est l'empreinte mathématique d'un gonflement artificiel du prix par des acteurs complices.
* **Verdict :** * `3/3` = Marché sain, régulier et hautement liquide. Idéal pour le trading court terme.
 * `2/3` = Confiance modérée. Marché régulier mais à faible vélocité (ex: Mods/Arcanes au Rang Max, nécessitant un investissement en Endo/crédits).
 * `1/3` ou `0/3` = **Danger / Haute Spéculation.** Marché illiquide, instable ou en cours de manipulation évidente. Le prix affiché est réel à l'instant T mais ne représente pas une valeur d'échange pérenne.

---

## ⚙️ Contraintes Techniques et Fraîcheur des Données

PCL extrait ses informations depuis l'API de *Warframe.market*. Pour respecter la charge des serveurs hôtes et garantir la pérennité de notre application, les données tournent à deux vitesses :

### 📡 Le "WFM 50" (Mise à jour Horaire)
Les **50 items générant le plus gros volume d'échange** du jeu font l'objet d'un suivi ultra-prioritaire. Leurs indices (`p`, `VR`, `F`) sont rafraîchis **toutes les heures** en tâche de fond. C'est votre salle des marchés en direct pour le *day-trading*.

### ⏳ Le Reste du Catalogue (Mise à jour Quotidienne)
L'intégralité du catalogue des 7 catégories subit une reconstruction lourde une fois par jour (Cycle Global) pour lisser les tendances macro-économiques et recalculer les canaux historiques.

---

## 🚀 Stratégies de Screening Recommandées

En combinant et en triant nos colonnes, vous pouvez appliquer des stratégies de traders professionnels :

* **La stratégie "Value Investor" (Achat bas) :** Filtrez par `DS` croissant (< 15%) + `F` égal à 3 + `VL` stable. Vous trouverez les objets temporairement délaissés, au plus bas de leur cycle, mais adossés à des marchés profonds et sains. Achetez et stockez.
* **La stratégie "Momentum Trader" (Achat-Revente rapide) :** Filtrez par `VR` décroissant (> 2.0) + `VL` élevé. Vous plongez directement là où se trouvent les flux financiers et la volatilité immédiate, idéal pour capter une tendance forte et écouler rapidement vos stocks au prix fort.
* **Protégez-vous des arnaques :** Si un objet affiche un prix très alléchant mais que sa **Fiabilité (`F`)** s'effondre à `1/3` ou `0/3`, ne foncez pas tête baissée. Le prix d'équilibre calculé est artificiel car il subit soit une asphyxie par manque d'activité (relique rare/abandonnée), soit un raid de spéculation sauvage.

---

## 3. ⚠️ Alerte : Le risque de manipulation du marché

Puisque Warframe Market ne peut pas vérifier la réalité des échanges en jeu, la plateforme est parfois la cible de spéculateurs ou d'arnaqueurs qui tentent de manipuler les statistiques historiques.

### Les deux techniques de manipulation les plus courantes :

> ### 1️⃣ Le "Market Cornering" (Gonflement artificiel)
> Des groupes de joueurs complices créent de fausses annonces et déclarent de fausses ventes à des prix exorbitants (par exemple, déclarer plusieurs ventes d'un mod à 300 Platinum alors qu'il n'en vaut que 40). L'objectif est de faire grimper artificiellement l'indicateur de prix (`p`) pour inciter les acheteurs crédules à payer l'objet bien au-dessus de sa vraie valeur économique.

> ### 2️⃣ Le "Price Dumping" (Effondrement artificiel)
> Un spéculateur déclare de fausses ventes à des prix ridiculement bas. Les algorithmes ou les joueurs honnêtes, pensant que l'objet a soudainement perdu sa valeur, s'alignent et bradent leurs biens. L'arnaqueur n'a plus qu'à racheter tous les *vrais* objets à bas prix avant de supprimer ses fausses annonces pour revendre le tout au prix fort quelques jours plus tard.
