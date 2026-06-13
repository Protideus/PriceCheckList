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

    const createAlert = ({ category, itemId, label, icon, priority, message, targetRank = 'R0' }) => {
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
        const ds = normalizeNumber(item.ds);
        const dsMax = normalizeNumber(item.ds_max);
        const fMax = normalizeNumber(item.f_max);
        const p = normalizeNumber(item.p);
        const pMax = normalizeNumber(item.p_max);

        if (item.p_max !== undefined && item.ds_max !== undefined) {
            if (dsMax <= 15 && ds >= 50 && fMax >= 2) {
                createAlert({
                    category,
                    itemId: item.id,
                    label: 'RMAX Bradé',
                    icon: '⚡',
                    priority: 'high',
                    message: `⚡ ANOMALIE RANG : Le prix RMAX de ${baseName} (${formatPrice(pMax)}) est anormalement bas (Donchian ${dsMax.toFixed(1)}%) alors que sa version Rang 0 (${formatPrice(p)}) reste forte. Idéal pour acheter le RMAX directement.`,
                    targetRank: 'RMAX'
                });
            }

            if (dsMax >= 80 && ds <= 20 && normalizeNumber(item.f) >= 2) {
                createAlert({
                    category,
                    itemId: item.id,
                    label: 'Spéculation RMAX',
                    icon: '🛠️',
                    priority: 'critical',
                    message: `🛠️ ARBITRAGE FUSION : Le prix R0 de ${baseName} (${formatPrice(p)}) s'est effondré mais la version RMAX (${formatPrice(pMax)}) reste très chère. Achetez des R0, maxez-les et vendez le RMAX pour une marge maximale.`,
                    targetRank: 'RMAX'
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
