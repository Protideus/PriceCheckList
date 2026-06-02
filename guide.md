# 📊 Guide de l'Utilisateur : Comprendre les Indicateurs Économiques

Bienvenue sur **PriceCheckList (PCL)**. Ce guide vous explique en détail la nature des données affichées, la méthodologie de calcul de nos indicateurs et comment les exploiter pour optimiser vos transactions dans *Warframe*.

---

## 1. 🔍 La nature des données (D'où viennent les informations ?)

Toutes les données affichées sur cette application proviennent de l'API de **Warframe Market (WFM)**. Cependant, pour bien interpréter les graphiques et les tableaux, il est fondamental de comprendre comment ces informations sont générées :

* **Des ventes déclarées, pas des ventes vérifiées :** Warframe Market est une plateforme tierce totalement indépendante de *Digital Extremes*. L'API ne lit pas les transactions réelles au sein du jeu. L'historique repose uniquement sur les vendeurs qui cliquent manuellement sur le bouton **"Vendu"** pour clôturer leurs annonces.
* **Une tendance globale sur 90 jours :** Bien que les données soient déclaratives, compiler et lisser cet historique sur une période de **90 jours** permet d'obtenir une excellente approximation mathématique de l'état réel du marché.

---

## 2. 📈 Explication des Indicateurs & Calculs

L'application synthétise l'état économique de chaque élément à l'aide de 6 indicateurs clés :

| Indicateur | Nom complet | Utilité (À quoi ça sert ?) | Méthode de calcul |
| :---: | :--- | :--- | :--- |
| **`p`** | **Prix Actuel** | Connaître la valeur moyenne de l'objet sur le marché à l'instant T. | C'est la moyenne lissée du prix médian des **3 derniers jours d'activité enregistrés** sur l'API. Cela évite qu'une transaction isolée ou absurde ne fausse le prix du jour. |
| **`p30`** | **Prix 30j** | Évaluer la valeur de l'objet sur le moyen terme ou détecter un début de baisse. | C'est le prix médian exact auquel s'échangeait cet objet **il y a 30 jours**. |
| **`p90`** | **Prix 90j** | Analyser la tendance lourde (macro-économie). Idéal pour suivre les objets *Vaulted* (retirés du jeu). | C'est le prix médian exact auquel s'échangeait l'objet au tout début de l'historique, **il y a 90 jours**. |
| **`v`** | **Volume** | Mesurer la "liquidité" de l'objet (savoir s'il se vend rapidement ou s'il est très rare). | C'est la **somme totale des unités déclarées vendues** au cours des 3 derniers jours d'activité de l'objet. |
| **`vr`** | **Volume Ratio** | **L'indicateur le plus puissant.** Repérer instantanément une explosion de la demande ou une hype soudaine. | On divise la moyenne des ventes récentes (3 jours) par la moyenne quotidienne des 90 derniers jours.<br>• **`vr` = 1.0 :** Le marché est parfaitement stable.<br>• **`vr` > 1.5 (Orange) :** L'objet subit un pic d'achat anormal (hype, buff d'une arme, etc.). |
| **`f`** | **Fiabilité** | Savoir si vous pouvez faire confiance aux prix affichés (noté de 0 à 3 ❤️). | Le score baisse si l'objet manque de données historiques (objet trop rare) ou si l'écart entre le prix minimum et maximum d'une même journée est chaotique. Un score de **3/3** signifie un marché régulier et sain. |

---

## 3. ⚠️ Alerte : Le risque de manipulation du marché

Puisque Warframe Market ne peut pas vérifier la réalité des échanges en jeu, la plateforme est parfois la cible de spéculateurs ou d'arnaqueurs qui tentent de manipuler les statistiques historiques.

### Les deux techniques de manipulation les plus courantes :

> ### 1️⃣ Le "Market Cornering" (Gonflement artificiel)
> Des groupes de joueurs complices créent de fausses annonces et déclarent de fausses ventes à des prix exorbitants (par exemple, déclarer plusieurs ventes d'un mod à 300 Platinum alors qu'il n'en vaut que 40). L'objectif est de faire grimper les indicateurs de prix (`p`) pour inciter les acheteurs crédules à payer l'objet au-dessus de sa vraie valeur.

> ### 2️⃣ Le "Price Dumping" (Effondrement artificiel)
> Un spéculateur déclare de fausses ventes à des prix ridiculement bas. Les algorithmes ou les joueurs honnêtes, pensant que l'objet a perdu sa valeur, s'alignent et bradent leurs biens. L'arnaqueur n'a plus qu'à racheter tous les *vrais* objets à bas prix avant de supprimer ses fausses annonces pour revendre le tout au prix fort quelques jours plus tard.

---

## 4. 💡 Conseils pratiques : Comment utiliser PCL pour commercer ?

* **Repérez les anomalies de prix :** Comparez le **Prix Actuel (`p`)** avec le **Prix 30j (`p30`)**. Si le prix actuel est très inférieur au prix historique mais que le **Volume (`v`)** reste élevé, l'objet est temporairement bradé. C'est le moment idéal pour acheter en vue d'une revente à moyen terme.
* **Anticipez les flambées (Le Volume Ratio) :** Un **Volume Ratio (`vr`)** qui explose (ex: `2.50`) signifie que les joueurs s'arrachent cet objet en ce moment même. Si son prix n'a pas encore augmenté, achetez-le immédiatement avant que la loi de l'offre et la demande ne fasse grimper sa valeur.
* **Protégez-vous des arnaques :** Si un objet affiche un prix très alléchant mais que sa **Fiabilité (`f`)** est de `1/3` ou `0/3`, le marché est instable ou manipulé. Ne vous fiez pas aveuglément à cette valeur. De même, une hausse de prix fulgurante accompagnée d'un volume minuscule est un signal d'alarme majeur.
