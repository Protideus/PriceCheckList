/* Alerts Manager Client-Side - PCL
   Analyse les tables JSON côté client et expose un store global d'alertes.
   Cette version fonctionne sans backend supplémentaire et s'intègre dans l'application existante.
*/

window.AlertStore = (() => {
    const alerts = [];
    const alertIndex = new Map();
    const subscribers = new Set();
    const priorityOrder = ['critical', 'high', 'medium'];

    const PRIORITY = {
        critical: { label: 'Critique 🔥', weight: 1, icon: '🔥', color: 'text-rose-400' },
        high: { label: 'Haute 🔴', weight: 2, icon: '🔴', color: 'text-amber-400' },
        medium: { label: 'Moyenne 🟠', weight: 3, icon: '⚠️', color: 'text-yellow-300' }
    };

    const normalizeNumber = (value) => {
        const n = Number(value);
        return Number.isFinite(n) ? n : 0;
    };

    const formatPrice = (value) => {
        const n = normalizeNumber(value);
        return `${n.toFixed(1)} pl`;
    };

    const createAlert = ({ category, itemId, label, icon, priority, message, targetRank = 'R0', profit = null }) => {
        const uid = `${category}:${itemId}:${label}:${targetRank}`;
        if (alertIndex.has(uid)) return null;

        const alert = {
            uid,
            category,
            itemId,
            label,
            icon,
            priority,
            message,
            targetRank,
            profit,
            weight: PRIORITY[priority]?.weight || 4,
            timestamp: Date.now()
        };

        alertIndex.set(uid, alert);
        alerts.push(alert);
        return alert;
    };

    const comparePriority = (a, b) => {
        if (a.weight !== b.weight) return a.weight - b.weight;
        return a.timestamp - b.timestamp;
    };

    const evaluateTimingAlerts = (category, item, rankSuffix = '', rankLabel = 'R0') => {
        const row = rankSuffix ? {
            p: normalizeNumber(item[`${rankSuffix ? rankSuffix + '_' : ''}p`]),
            p90: normalizeNumber(item[`${rankSuffix ? rankSuffix + '_' : ''}p90`]),
            v: normalizeNumber(item[`${rankSuffix ? rankSuffix + '_' : ''}v`]),
            vr: normalizeNumber(item[`${rankSuffix ? rankSuffix + '_' : ''}vr`]),
            ds: normalizeNumber(item[`${rankSuffix ? rankSuffix + '_' : ''}ds`]),
            f: normalizeNumber(item[`${rankSuffix ? rankSuffix + '_' : ''}f`])
        } : {
            p: normalizeNumber(item.p),
            p90: normalizeNumber(item.p90),
            v: normalizeNumber(item.v),
            vr: normalizeNumber(item.vr),
            ds: normalizeNumber(item.ds),
            f: normalizeNumber(item.f)
        };

        if (Number.isNaN(row.p90) || row.p90 === 0) {
            // Protection contre valeurs non définies.
        }

        // Exclure les items sans ventes récentes (volume 48h = 0)
        if (row.v === 0) {
            return;
        }

        const baseName = item.n_fr || item.id || 'Objet inconnu';
        const rankSuffixLabel = rankSuffix ? ' RMAX' : '';
        const absP90 = Math.abs(row.p90);

        if (row.ds >= 92 && row.vr >= 1.2 && absP90 >= 10) {
            createAlert({
                category,
                itemId: item.id,
                label: 'Sommet Historique',
                icon: '🔥',
                priority: 'high',
                message: `🔥 SOMMET${rankSuffixLabel} : ${baseName}${rankSuffixLabel} est proche de son plus haut des 90 jours avec un volume fort. Excellent moment pour liquider vos stocks.`,
                targetRank: rankLabel
            });
        }

        if (row.ds <= 12 && row.vr >= 1.0 && row.f >= 2 && absP90 >= 10) {
            createAlert({
                category,
                itemId: item.id,
                label: 'Creux Historique',
                icon: '💎',
                priority: 'high',
                message: `💎 CREUX HISTORIQUE${rankSuffixLabel} : ${baseName}${rankSuffixLabel} est au plus bas des 90 jours sur un marché actif et fiable. Très bon point d'entrée pour accumuler.`,
                targetRank: rankLabel
            });
        }

        if (row.ds <= 15 && row.vr > 1.8 && absP90 >= 10) {
            createAlert({
                category,
                itemId: item.id,
                label: 'Chute Libre',
                icon: '⚠️',
                priority: 'medium',
                message: `⚠️ CHUTE LIBRE${rankSuffixLabel} : Énorme pic de volume sur ${baseName}${rankSuffixLabel} mais le prix s'effondre. Vente panique ou correction majeure en cours.`,
                targetRank: rankLabel
            });
        }
    };

    const evaluateRankArbitrageAlerts = (category, item) => {
        if (category !== 'arcanes') return;

        const baseName = item.n_fr || item.id || 'Objet inconnu';
        const ratio = normalizeNumber(item.fusion_ratio) || 21;
        const p = normalizeNumber(item.p);
        const pMax = normalizeNumber(item.p_max);
        const costToCraft = p * ratio;

        // Exclure items sans ventes en 48h
        const v = normalizeNumber(item.v);
        if (v === 0) return;
        
        const MIN_PROFIT_THRESHOLD = 30; // Seuil minimum de profit en platines

        if (pMax > 0 && p > 0) {
            // Alerte : RMAX Sous-évalué (arbitrage par séparation)
            const profitSeparation = costToCraft - pMax;
            if (profitSeparation >= MIN_PROFIT_THRESHOLD) {
                createAlert({
                    category,
                    itemId: item.id,
                    label: 'RMAX Sous-évalué',
                    icon: '💔',
                    priority: 'high',
                    message: `💔 SÉPARATION RENTABLE : ${baseName} RMAX vaut ${formatPrice(pMax)}. 
                              Acheter des R0 et séparer coûterait ${formatPrice(costToCraft)} (${ratio} copies). 
                              Profit potentiel : +${profitSeparation.toFixed(1)} pl.`,
                    targetRank: 'RMAX',
                    profit: profitSeparation
                });
            }

            // Alerte : Arbitrage Fusion (arbitrage par fusion)
            const profitFusion = pMax - costToCraft;
            if (profitFusion >= MIN_PROFIT_THRESHOLD) {
                createAlert({
                    category,
                    itemId: item.id,
                    label: 'Arbitrage Fusion',
                    icon: '⚗️',
                    priority: 'critical',
                    message: `⚗️ FUSION RENTABLE : ${baseName} RMAX se vend ${formatPrice(pMax)}. 
                              Acheter ${ratio} copies R0 coûterait ${formatPrice(costToCraft)}. 
                              Profit potentiel : +${profitFusion.toFixed(1)} pl.`,
                    targetRank: 'RMAX',
                    profit: profitFusion
                });
            }
        }
    };

    const scanItem = (category, item) => {
        if (!item || typeof item !== 'object') return;
        evaluateTimingAlerts(category, item, '', 'R0');

        if (item.p_max !== undefined || item.ds_max !== undefined) {
            evaluateTimingAlerts(category, item, 'max', 'RMAX');
            evaluateRankArbitrageAlerts(category, item);
        }
    };

    const scanTable = (category, tableData) => {
        if (category === 'wfm50') return;
        if (!Array.isArray(tableData)) return;
        tableData.forEach(item => scanItem(category, item));
    };

    const clearAlerts = () => {
        alerts.length = 0;
        alertIndex.clear();
    };

    const notify = () => {
        const sorted = [...alerts].sort(comparePriority);
        subscribers.forEach(cb => {
            try {
                cb(sorted);
            } catch (error) {
                console.warn('AlertStore subscriber failed', error);
            }
        });
    };

    const getAlerts = ({ category = 'all', priority = 'all' } = {}) => {
        let result = [...alerts];
        if (category !== 'all') {
            result = result.filter(alert => alert.category === category);
        }
        if (priority !== 'all') {
            result = result.filter(alert => alert.priority === priority);
        }
        return result.sort(comparePriority);
    };

    const getItemAlerts = (category, itemId) => {
        return getAlerts({ category: category || 'all' }).filter(alert => alert.itemId === itemId);
    };

    const getCategories = () => {
        return Array.from(new Set(alerts.map(alert => alert.category))).sort();
    };

    const getAlertCount = () => alerts.length;

    const scanAllTables = async (tables) => {
        clearAlerts();
        const entries = Object.entries(tables || {});
        await Promise.all(entries.map(([category, data]) => new Promise(resolve => {
            setTimeout(() => {
                scanTable(category, data);
                resolve();
            }, 0);
        })));
        notify();
        return getAlerts();
    };

    return {
        scanCategory: (category, tableData) => {
            scanTable(category, tableData);
            notify();
        },
        scanAllTables,
        getAlerts,
        getItemAlerts,
        getCategories,
        getAlertCount,
        subscribe: (cb) => {
            if (typeof cb === 'function') {
                subscribers.add(cb);
                return () => subscribers.delete(cb);
            }
            return () => {};
        }
    };
})();
