// STRUCTURE GLOBALE DES DONNÉES
        const PCLData = {
            version: null,
            tables: {},
            details: {}
        };

        const LIST_CONFIG = [
            { id: 'wfm50', table: 'wfm50_table.json', details: 'wfm50_details.json', label: 'WFM50', icon: 'fa-fire' },
            { id: 'warframes', table: 'warframes_table.json', details: 'warframes_details.json', label: 'Warframes', icon: 'fa-shield-halved' },
            { id: 'armes', table: 'armes_table.json', details: 'armes_details.json', label: 'Armes', icon: 'fa-gun' },
            { id: 'equipements', table: 'equipements_table.json', details: 'equipements_details.json', label: 'Équipements', icon: 'fa-robot' },
            { id: 'mods', table: 'mods_table.json', details: 'mods_details.json', label: 'Mods', icon: 'fa-id-card' },
            { id: 'arcanes', table: 'arcanes_table.json', details: 'arcanes_details.json', label: 'Arcanes', icon: 'fa-gem' },
            { id: 'reliques', table: 'reliques_table.json', details: 'reliques_details.json', label: 'Reliques', icon: 'fa-cube' },
            { id: 'ressources', table: 'ressources_table.json', details: 'ressources_details.json', label: 'Ressources', icon: 'fa-box-tissue' }
        ];

        const CATEGORIES = LIST_CONFIG;
        const RANK_FILTER_CATEGORIES = new Set(['mods', 'arcanes', 'wfm50']);

        // ÉTAT GLOBAL DE L'APPLICATION
        let appState = {
            currentCategory: "wfm50",
            searchQuery: "",
            sortColumn: "n_fr",
            sortDirection: "asc",
            rankFilter: "all",
            alertProfitThreshold: 30
        };

        // INITIALISATION DE L'APPLICATION
        window.addEventListener("DOMContentLoaded", async () => {
            buildProgressChecklist();
            await initApplicationPipeline();

            const searchInput = document.getElementById("search-input");
            const clearSearchBtn = document.getElementById("clear-search-btn");

            if (searchInput) {
                searchInput.addEventListener("input", (e) => {
                    appState.searchQuery = e.target.value.toLowerCase().trim();
                    updateClearSearchButton();
                    renderTable();
                });
            }

            if (clearSearchBtn && searchInput) {
                clearSearchBtn.addEventListener("click", () => {
                    searchInput.value = "";
                    appState.searchQuery = "";
                    updateClearSearchButton();
                    renderTable();
                    searchInput.focus();
                });
            }

            const rankFilter = document.getElementById("rank-filter");
            if (rankFilter) {
                rankFilter.addEventListener("change", (e) => {
                    appState.rankFilter = e.target.value;
                    renderTable();
                });
            }

            const alertsBtn = document.getElementById("alerts-btn");
            if (alertsBtn) {
                alertsBtn.addEventListener("click", openAlertsPanel);
            }
            const copyDataBtn = document.getElementById("copy-data-btn");
            if (copyDataBtn) {
                copyDataBtn.addEventListener("click", handleCopyVisibleTableData);
            }
            document.getElementById("guide-btn").addEventListener("click", openGuideModal);
            document.getElementById("readme-btn").addEventListener("click", openReadmeModal);
            document.getElementById("author-btn").addEventListener("click", openAuthorModal);

            AlertStore.subscribe((alerts) => {
                updateAlertsBadge(alerts.length);
                if (alerts.length > 0) {
                    renderTable();
                }
            });

            updateClearSearchButton();
        });

        function updateClearSearchButton() {
            const searchInput = document.getElementById("search-input");
            const clearSearchBtn = document.getElementById("clear-search-btn");
            if (!searchInput || !clearSearchBtn) return;

            const hasValue = searchInput.value.trim().length > 0;
            clearSearchBtn.classList.toggle("opacity-0", !hasValue);
            clearSearchBtn.classList.toggle("pointer-events-none", !hasValue);
            clearSearchBtn.classList.toggle("opacity-100", hasValue);
        }

        // CONSTRUIRE LA CHECKLIST GRAPHIQUE DU CHARGEMENT
        function buildProgressChecklist() {
            const container = document.getElementById("progress-checklist");
            container.innerHTML = `
                <div id="check-version" class="flex items-center justify-between text-gray-500">
                    <span><i class="fa-solid fa-circle-notch fa-spin mr-2 text-cyan-400"></i> api_version.json</span>
                    <span class="text-xs">En attente</span>
                </div>
            `;

            LIST_CONFIG.forEach(cat => {
                container.innerHTML += `
                    <div id="check-${cat.id}" class="flex items-center justify-between text-gray-500">
                        <span><i class="fa-solid fa-circle-notch fa-spin mr-2 text-gray-700"></i>${cat.table}</span>
                        <span class="text-xs">En attente</span>
                    </div>
                `;
            });
        }

        function updateAlertsBadge(count) {
            const badge = document.getElementById('alerts-count');
            if (!badge) return;
            badge.textContent = count;
            badge.classList.toggle('hidden', count === 0);
        }

        function escapeHtml(value) {
            return String(value || '').replace(/[&<>"']/g, (char) => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            })[char]);
        }

        function getAlertBadgeClass(priority) {
            if (priority === 'critical') return 'bg-rose-500/15 text-rose-300 border border-rose-500/30';
            if (priority === 'high') return 'bg-amber-500/15 text-amber-300 border border-amber-500/30';
            return 'bg-yellow-500/15 text-yellow-200 border border-yellow-500/30';
        }

        function getAlertIconForItem(category, itemId) {
            const alerts = AlertStore.getItemAlerts(category, itemId);
            return alerts.length ? alerts[0] : null;
        }

        function renderAlertMarker(category, itemId) {
            const alert = getAlertIconForItem(category, itemId);
            if (!alert) return '';
            return ` <span class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${getAlertBadgeClass(alert.priority)}" title="${escapeHtml(alert.message)}">${alert.icon}</span>`;
        }

        function getCategoryLabel(categoryId) {
            const config = LIST_CONFIG.find((item) => item.id === categoryId);
            return config ? config.label : categoryId;
        }

        function renderAlertsList(categoryFilter = 'all') {
            const modalContent = document.getElementById('modal-content');
            if (!modalContent) return;

            const threshold = Number(appState.alertProfitThreshold || 30);
            const categories = ['all', ...AlertStore.getCategories()];
            const alerts = AlertStore.getAlerts({ category: categoryFilter, priority: 'all' })
                .filter(alert => {
                    if (typeof alert.profit !== 'number') return true;
                    return alert.profit >= threshold;
                });
            const filterButtons = categories.map(catId => {
                const label = catId === 'all' ? 'Toutes' : getCategoryLabel(catId);
                const activeClass = catId === categoryFilter ? 'bg-cyan-500 text-black' : 'bg-gray-900/70 text-gray-300 hover:bg-gray-800';
                return `<button onclick="renderAlertsList('${catId}')" class="px-3 py-2 rounded-full text-xs font-semibold transition ${activeClass}">${label}</button>`;
            }).join('');

            const alertRows = alerts.length ? alerts.map(alert => {
                return `
                    <div class="bg-gray-950/80 border border-gray-800/50 rounded-2xl p-4 mb-3">
                        <div class="flex items-start justify-between gap-3">
                            <div class="space-y-2">
                                <div class="flex flex-wrap items-center gap-2 text-sm font-semibold ${getAlertBadgeClass(alert.priority)} rounded-full px-2 py-1">
                                    <span>${alert.icon}</span>
                                    <span>${escapeHtml(alert.label)}</span>
                                </div>
                                <p class="text-sm text-gray-200 leading-snug">${escapeHtml(alert.message)}</p>
                            </div>
                            <div class="text-right text-xs text-gray-400">
                                <div>${getCategoryLabel(alert.category)}</div>
                                <div class="mt-1 font-semibold">${escapeHtml(alert.targetRank)}</div>
                            </div>
                        </div>
                        <div class="mt-3 flex items-center justify-between text-[11px] text-gray-500">
                            <span>Item ID: ${escapeHtml(alert.itemId)}</span>
                            <button onclick="openItemDetails('${alert.itemId}')" class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 transition">Voir le détail</button>
                        </div>
                    </div>
                `;
            }).join('') : `
                <div class="p-6 rounded-2xl bg-gray-950/70 border border-gray-800/50 text-center text-gray-400">
                    <p class="text-sm font-medium">Aucune alerte active pour le filtre sélectionné.</p>
                </div>
            `;

            modalContent.innerHTML = `
                <div class="p-6 bg-gray-950/60 border-b border-gray-800/40 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h2 class="text-lg font-bold text-white uppercase tracking-wider flex items-center gap-2">
                            <i class="fa-solid fa-bell text-cyan-400"></i> Alertes économiques
                        </h2>
                        <p class="text-xs text-gray-400 mt-1">${alerts.length} alerte(s) active(s) triées par priorité.</p>
                    </div>
                    <div class="flex flex-col sm:flex-row sm:items-center gap-3">
                        <label class="flex items-center gap-2 text-xs text-gray-300">
                            <span>Seuil profit</span>
                            <input id="alert-profit-threshold" type="number" min="0" step="5" value="${threshold}" onchange="handleAlertProfitThresholdChange(this.value)" class="w-20 bg-gray-950/70 border border-gray-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/30">
                        </label>
                        <button onclick="closeModal()" class="text-gray-500 hover:text-white transition-colors p-1"><i class="fa-solid fa-xmark text-lg"></i></button>
                    </div>
                </div>
                <div class="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
                    <div class="flex flex-wrap gap-2 mb-4">${filterButtons}</div>
                    ${alertRows}
                </div>
            `;
        }

        function openAlertsPanel() {
            const modalContainer = document.getElementById('modal-container');
            const modalContent = document.getElementById('modal-content');
            if (!modalContainer || !modalContent) return;

            modalContainer.classList.remove('hidden');
            setTimeout(() => modalContainer.classList.add('modal-show'), 10);
            setTimeout(() => modalContent.classList.add('modal-scale'), 10);
            renderAlertsList('all');
        }

        async function fetchJSON(url, label) {
            try {
                updateLoaderWidget(`Chargement : ${label}`, 0);
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.warn(`⚠️ Impossible de charger le fichier : ${url}. Contenu ignoré.`, error);
                return null;
            }
        }

        function displaySyncDate(versionData) {
            const target = document.getElementById("api-version-info");
            if (!target) return;

            const baseDate = versionData && versionData.last_run ? new Date(versionData.last_run) : null;
            const syncDate = baseDate ? baseDate.toLocaleString('fr-FR') : 'Inconnue';
            const ageText = formatDataAge(versionData, appState.currentCategory);

            target.innerHTML = `
                <div><i class="fa-solid fa-clock text-cyan-400"></i> Synchro : ${syncDate}</div>
                <div class="text-[11px] text-gray-300 mt-1">Data age : ${ageText}</div>
            `;
        }

        function formatDataAge(versionData, category) {
            if (!versionData) return 'indisponible';

            const now = new Date();
            let referenceDate = null;

            if (category === 'wfm50' && versionData.last_wfm50_hourly_update) {
                referenceDate = new Date(versionData.last_wfm50_hourly_update);
            } else if (versionData.last_run) {
                referenceDate = new Date(versionData.last_run);
            }

            if (!referenceDate || Number.isNaN(referenceDate.getTime())) {
                return 'indisponible';
            }

            const diffMs = now - referenceDate;
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffHours / 24);

            if (diffDays > 5) {
                return 'Trop vieux';
            }

            const hoursOnly = diffHours % 24;
            if (diffDays === 0) {
                return `${diffHours}h`;
            }
            return `${diffDays}j ${hoursOnly}h`;
        }

        function showGlobalError(message) {
            const statusText = document.getElementById("loading-status-text");
            if (statusText) {
                statusText.innerText = message;
                statusText.classList.add("text-rose-400");
            }
            updateLoaderWidget(message, 100);
        }

        function updateLoaderWidget(text, percent) {
            const textStatus = document.getElementById("bg-loader-text");
            const percentStatus = document.getElementById("bg-loader-percent");
            const barStatus = document.getElementById("bg-loader-bar");
            const pingStatus = document.getElementById("bg-loader-ping");
            const dotStatus = document.getElementById("bg-loader-dot");
            const widget = document.getElementById("bg-loader-status");

            if (textStatus) textStatus.innerText = text;
            if (percentStatus) percentStatus.innerText = `${percent}%`;
            if (barStatus) barStatus.style.width = `${percent}%`;

            if (percent === 100) {
                if (percentStatus) {
                    percentStatus.className = "text-xs font-mono font-bold text-green-400 bg-green-950/50 px-1.5 py-0.5 rounded border border-green-500/20";
                }
                if (barStatus) {
                    barStatus.className = "h-full w-full bg-gradient-to-r from-green-500 to-emerald-600 transition-all duration-300 ease-out";
                }
                if (dotStatus) {
                    dotStatus.className = "relative inline-flex rounded-full h-2 w-2 bg-green-500";
                }
                if (pingStatus) {
                    const pingEffect = pingStatus.querySelector('.animate-ping');
                    if (pingEffect) pingEffect.remove();
                }

                setTimeout(() => {
                    if (widget) {
                        widget.classList.add("translate-y-full", "opacity-0");
                    }
                }, 1800);
            }
        }

        async function initApplicationPipeline() {
            const loaderOverlay = document.getElementById("loading-screen");
            const statusText = document.getElementById("loading-status-text");
            const totalFiles = 1 + LIST_CONFIG.length * 2;
            let loadedFiles = 0;

            const markFile = (stepId, label, isSuccess) => {
                loadedFiles += 1;
                const progress = Math.round((loadedFiles / totalFiles) * 100);
                updateLoaderWidget(`Chargement : ${label}`, progress);

                const element = document.getElementById(`check-${stepId}`);
                if (!element) return;
                if (isSuccess) {
                    element.className = "flex items-center justify-between text-emerald-400";
                    element.innerHTML = `<span><i class="fa-solid fa-circle-check mr-2"></i>${label}</span><span class="text-xs">OK</span>`;
                } else {
                    element.className = "flex items-center justify-between text-rose-400";
                    element.innerHTML = `<span><i class="fa-solid fa-circle-xmark mr-2"></i>${label}</span><span class="text-xs">Erreur</span>`;
                }
            };

            const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

            updateLoaderWidget("Initialisation...", 5);
            if (statusText) statusText.innerText = "Récupération des fichiers prioritaires...";

            const startTime = performance.now();
            const [versionData, wfm50Table] = await Promise.all([
                fetchJSON('https://raw.githubusercontent.com/Protideus/PriceCheckList/main/data/api_version.json', 'api_version.json'),
                fetchJSON('data/wfm50_table.json', 'wfm50_table.json')
            ]);

            if (versionData) {
                PCLData.version = versionData;
                displaySyncDate(versionData);
                if (window.updateXlsxMetadata) {
                    window.updateXlsxMetadata(versionData);
                }
                markFile('version', 'api_version.json', true);
            } else {
                if (window.updateXlsxMetadata) {
                    window.updateXlsxMetadata(null);
                }
                markFile('version', 'api_version.json', false);
            }

            if (wfm50Table) {
                PCLData.tables['wfm50'] = wfm50Table;
                markFile('wfm50', 'wfm50_table.json', true);
            } else {
                markFile('wfm50', 'wfm50_table.json', false);
            }

            if (!wfm50Table) {
                showGlobalError('Erreur critique : Impossible de charger la liste prioritaire.');
                return;
            }

            buildNavigationTabs();
            renderTable();
            AlertStore.scanCategory('wfm50', wfm50Table);
            if (loaderOverlay) {
                loaderOverlay.classList.add('opacity-0', 'pointer-events-none');
                setTimeout(() => loaderOverlay.style.display = 'none', 600);
            }

            const elapsed = performance.now() - startTime;
            if (elapsed < 200) await sleep(200 - elapsed);

            updateLoaderWidget('Données prioritaires chargées. Chargement du catalogue...', 30);
            if (statusText) statusText.innerText = 'Chargement des tables restantes...';

            const scanAllTablesPromise = Promise.all(LIST_CONFIG.filter(item => item.id !== 'wfm50').map(async (list) => {
                const data = await fetchJSON(`data/${list.table}`, list.table);
                if (data) {
                    PCLData.tables[list.id] = data;
                    markFile(list.id, list.table, true);
                } else {
                    PCLData.tables[list.id] = [];
                    markFile(list.id, list.table, false);
                }
            })).then(() => AlertStore.scanAllTables(PCLData.tables));

            await scanAllTablesPromise;

            updateLoaderWidget('Toutes les tables sont prêtes. Finalisation des détails...', 70);
            if (statusText) statusText.innerText = 'Préchargement des fiches détaillées...';

            const detailsPromises = LIST_CONFIG.map(async (list) => {
                const data = await fetchJSON(`data/${list.details}`, list.details);
                PCLData.details[list.id] = data ? data : {};
                // Ne met pas à jour la checklist pour les détails, on affiche uniquement le widget global
            });
            await Promise.all(detailsPromises);

            updateLoaderWidget('DATASET COMPLET', 100);
            if (statusText) statusText.innerText = 'Dataset complet';
        }

        // CONSTRUIRE LA BARRE D'ONGLETS (DESKTOP & MOBILE)
        function buildNavigationTabs() {
            const desktopNav = document.getElementById("nav-tabs");
            const mobileNav = document.getElementById("nav-tabs-mobile");

            CATEGORIES.forEach(cat => {
                const btnHTML = `
                    <button id="tab-${cat.id}" onclick="switchCategory('${cat.id}')" class="px-4 py-2 border-b-2 border-transparent text-gray-400 hover:text-white hover:border-gray-700 transition-all text-sm font-medium flex items-center gap-2">
                        <i class="fa-solid ${cat.icon} text-xs"></i> ${cat.label}
                    </button>
                `;
                desktopNav.innerHTML += btnHTML;
                
                const mobileHTML = `
                    <button id="tab-mob-${cat.id}" onclick="switchCategory('${cat.id}')" class="px-3 py-1.5 rounded-lg border border-gray-800 text-gray-400 bg-gray-950/40 text-xs font-medium inline-flex items-center gap-1.5">
                        <i class="fa-solid ${cat.icon}"></i> ${cat.label}
                    </button>
                `;
                mobileNav.innerHTML += mobileHTML;
            });
            updateTabStyle();
        }

        // CHANGER DE CATÉGORIE ACTIVE
        function switchCategory(catId) {
            appState.currentCategory = catId;
            updateTabStyle();
            updateRankFilterUI();
            displaySyncDate(PCLData.version);
            renderTable();
        }

        // METTRE À JOUR LE STYLE GRAPHIQUE DES ONGLETS SÉLECTIONNÉS
        function updateTabStyle() {
            CATEGORIES.forEach(cat => {
                const dTab = document.getElementById(`tab-${cat.id}`);
                const mTab = document.getElementById(`tab-mob-${cat.id}`);
                
                if (cat.id === appState.currentCategory) {
                    if (dTab) dTab.className = "px-4 py-2 border-b-2 text-sm font-medium flex items-center gap-2 tab-active";
                    if (mTab) mTab.className = "px-3 py-1.5 rounded-lg border text-xs font-medium inline-flex items-center gap-1.5 bg-cyan-950/30 border-cyan-500/50 text-cyan-400 drop-shadow-[0_0_6px_rgba(34,211,238,0.3)]";
                } else {
                    if (dTab) dTab.className = "px-4 py-2 border-b-2 border-transparent text-gray-400 hover:text-white hover:border-gray-700 transition-all text-sm font-medium flex items-center gap-2";
                    if (mTab) mTab.className = "px-3 py-1.5 rounded-lg border border-gray-800 text-gray-400 bg-gray-950/40 text-xs font-medium inline-flex items-center gap-1.5";
                }
            });
            updateRankFilterUI();
        }

        function isRankFilterAvailable() {
            return RANK_FILTER_CATEGORIES.has(appState.currentCategory);
        }

        function updateRankFilterUI() {
            const rankFilterWrapper = document.getElementById('rank-filter-container');
            const rankFilterSelect = document.getElementById('rank-filter');
            if (!rankFilterWrapper || !rankFilterSelect) return;

            const available = isRankFilterAvailable();
            rankFilterSelect.disabled = !available;
            rankFilterWrapper.classList.toggle('opacity-40', !available);
            rankFilterSelect.classList.toggle('border-cyan-500', available);
            rankFilterSelect.classList.toggle('border-gray-700', !available);
            rankFilterWrapper.title = available ? 'Filtre actif pour cette catégorie' : 'Ce filtre n\'est pas disponible pour cette catégorie';
        }

        function handleAlertProfitThresholdChange(value) {
            const threshold = Number(value);
            appState.alertProfitThreshold = Number.isFinite(threshold) && threshold >= 0 ? threshold : 30;
            renderAlertsList('all');
        }

        // RENDU ULTRA-RAPIDE DU TABLEAU DYNAMIQUE (ZÉRO FREEZE)
        function getVisibleTableData() {
            const rawData = PCLData.tables[appState.currentCategory] || [];
            let data = rawData.slice();

            if (appState.searchQuery) {
                data = data.filter(item => 
                    (item.n_fr && item.n_fr.toLowerCase().includes(appState.searchQuery)) ||
                    (item.n_en && item.n_en.toLowerCase().includes(appState.searchQuery))
                );
            }

            const col = appState.sortColumn;
            const dir = appState.sortDirection === "asc" ? 1 : -1;

            data.sort((a, b) => {
                let valA = a[col] !== undefined ? a[col] : 0;
                let valB = b[col] !== undefined ? b[col] : 0;

                if (typeof valA === 'string') {
                    return valA.localeCompare(valB, 'fr') * dir;
                }
                return (valA - valB) * dir;
            });

            return data;
        }

        function renderTable() {
            const tbody = document.getElementById("table-body");
            const noResults = document.getElementById("no-results");
            let data = getVisibleTableData();

            updateSortIcons();

            if (data.length === 0) {
                tbody.innerHTML = "";
                noResults.classList.remove("hidden");
                return;
            }
            noResults.classList.add("hidden");

            // OPTIMISATION CRITIQUE : Accumulation dans un flux texte hors-DOM
            let tableHTML = "";
            
            data.forEach(item => {
                const deltaValue = item.p90 !== undefined && item.p90 !== null ? Number(item.p90) : 0;
                const deltaMax = item.p90_max !== undefined && item.p90_max !== null ? Number(item.p90_max) : null;
                const dsValue = item.ds !== undefined && item.ds !== null ? Number(item.ds) : 0;
                const dsMax = item.ds_max !== undefined && item.ds_max !== null ? Number(item.ds_max) : null;
                const vrValue = item.vr !== undefined && item.vr !== null ? Number(item.vr) : 0;
                const vrMax = item.vr_max !== undefined && item.vr_max !== null ? Number(item.vr_max) : null;
                const alertMarker = renderAlertMarker(appState.currentCategory, item.id);

                tableHTML += `
                    <tr class="table-row-hover border-b border-gray-800/30 cursor-pointer text-gray-300 font-medium" onclick="openItemDetails('${item.id}')">
                        <td class="p-4">
                            <div class="text-white">${item.n_fr || item.id}${alertMarker}</div>
                            <div class="text-xs text-gray-500 italic font-mono">${item.n_en || ''}</div>
                        </td>
                        <td class="p-4 text-right font-mono text-cyan-300">
                            ${renderRankValue(item.p, item.p_max, formatPrice)}
                        </td>
                        <td class="p-4 text-right font-mono text-gray-100">
                            ${renderRankValue(item.v, item.v_max, formatVolume)}
                        </td>
                        <td class="p-4 text-right text-sm font-semibold ${getDeltaClass(deltaValue, deltaMax)}">
                            ${renderRankValue(deltaValue, deltaMax, renderDelta, 'R0', 'Rmax')}
                        </td>
                        <td class="p-4 text-right">
                            ${renderRankValue(vrValue, vrMax, renderVrBadge)}
                        </td>
                        <td class="p-4 text-left">
                            ${renderRankValue(dsValue, dsMax, renderDsBar)}
                        </td>
                        <td class="p-4 text-center text-sm">
                            ${renderRankValue(item.f, item.f_max, renderFiabilityIcons)}
                        </td>
                    </tr>
                `;
            });

            // Une seule et unique injection pour liquider instantanément le freeze
            tbody.innerHTML = tableHTML;
        }

        function formatExportPrice(value) {
            const num = Number(value);
            if (Number.isNaN(num)) return '0.0 pl';
            return `${num.toFixed(1)} pl`;
        }

        function formatExportPercent(value) {
            const num = Number(value);
            if (Number.isNaN(num)) return '0%';
            const normalized = num % 1 === 0 ? num : Number(num.toFixed(1));
            return `${normalized > 0 ? '+' : ''}${normalized}%`;
        }

        function formatExportNumber(value) {
            const num = Number(value);
            if (Number.isNaN(num)) return '0';
            return num % 1 === 0 ? String(num) : String(num);
        }

        function getExportLinesForItem(item) {
            const baseFields = {
                p: item.p,
                p90: item.p90,
                v: item.v,
                vr: item.vr,
                ds: item.ds,
                f: item.f
            };
            const maxFields = {
                p: item.p_max,
                p90: item.p90_max,
                v: item.v_max,
                vr: item.vr_max,
                ds: item.ds_max,
                f: item.f_max
            };

            const hasRank = item.p_max !== undefined || item.v_max !== undefined || item.p90_max !== undefined || item.vr_max !== undefined || item.ds_max !== undefined || item.f_max !== undefined;
            const state = appState.rankFilter;
            const nameFr = item.n_fr || "";
            const nameEn = item.n_en || "";
            const lines = [];

            function buildLine(rankLabel, fields) {
                return [
                    nameFr,
                    nameEn,
                    rankLabel,
                    formatExportPrice(fields.p),
                    formatExportPercent(fields.p90),
                    formatExportNumber(fields.v),
                    formatExportNumber(fields.vr),
                    formatExportPercent(fields.ds),
                    formatExportNumber(fields.f)
                ].join("\t");
            }

            if (!hasRank || state !== 'all') {
                const rankLabel = hasRank && state === 'rmax' ? 'Rmax' : (hasRank && state === 'r0' ? 'R0' : '-');
                const fields = state === 'rmax' ? maxFields : baseFields;
                lines.push(buildLine(rankLabel, fields));
                return lines;
            }

            // Export both R0 and Rmax as separate lines for rank-aware objects when the filter allows both.
            lines.push(buildLine('R0', baseFields));
            lines.push(buildLine('Rmax', maxFields));
            return lines;
        }

        function handleCopyVisibleTableData() {
            const data = getVisibleTableData();
            if (!data.length) return;

            const lines = data.flatMap(item => getExportLinesForItem(item));
            if (!lines.length) return;

            const textToCopy = lines.join("\n");
            navigator.clipboard.writeText(textToCopy).then(() => {
                const button = document.getElementById("copy-data-btn");
                if (!button) return;
                const originalText = button.textContent;
                button.textContent = "Copié !";
                setTimeout(() => {
                    button.textContent = originalText;
                }, 2000);
            }).catch(() => {
                console.warn("Impossible de copier les données dans le presse-papiers.");
            });
        }

        // DETERMINER LA COULEUR DES TENDANCES DE PRIX
        function clamp(value, min, max) {
            return Math.min(Math.max(value, min), max);
        }

        function formatPrice(value) {
            if (value === undefined || value === null || Number.isNaN(Number(value))) return '0.0 pl';
            return `${Number(value).toFixed(1)} pl`;
        }

        function formatVolume(value) {
            if (value === undefined || value === null || Number.isNaN(Number(value))) return '0';
            const normalized = Number(value);
            if (normalized >= 1000) {
                return `${(normalized / 1000).toFixed(1)}k`;
            }
            return normalized.toString();
        }

        function getDeltaClass(delta, deltaMax) {
            if (deltaMax !== null) {
                if (delta > 0 || deltaMax > 0) return 'text-emerald-300';
                if (delta < 0 && deltaMax < 0) return 'text-rose-400';
                return 'text-gray-400';
            }
            if (delta > 0) return 'text-emerald-300';
            if (delta < 0) return 'text-rose-400';
            return 'text-gray-400';
        }

        function renderRankValue(base, max, renderer, labelBase = 'R0', labelMax = 'Rmax') {
            if (max === undefined || max === null) {
                return renderer(base);
            }

            const filterMode = appState.rankFilter;
            if (filterMode === 'r0') {
                return `
                    <div>${renderer(base)}</div>
                    <div class="text-[10px] text-slate-500 uppercase tracking-[0.18em] mt-1">${labelBase}</div>
                `;
            }

            if (filterMode === 'rmax') {
                if (max !== undefined && max !== null) {
                    return `
                        <div>${renderer(max)}</div>
                        <div class="text-[10px] text-slate-500 uppercase tracking-[0.18em]">${labelMax}</div>
                    `;
                }
                return renderer(base);
            }

            return `
                <div>${renderer(base)}</div>
                <div class="text-[10px] text-slate-500 uppercase tracking-[0.18em] mt-1">${labelBase}</div>
                <div class="mt-1">${renderer(max)}</div>
                <div class="text-[10px] text-slate-500 uppercase tracking-[0.18em]">${labelMax}</div>
            `;
        }

        function renderDelta(delta) {
            if (delta > 0) return `▲ +${delta.toFixed(1)}%`;
            if (delta < 0) return `▼ ${delta.toFixed(1)}%`;
            return '• 0.0%';
        }

        function renderVrBadge(vr) {
            const value = vr ? vr.toFixed(1) : '0.0';
            const badgeClass = getVrBadgeClass(vr);
            const icon = vr > 2 ? '<span class="ml-1">🔥</span>' : '';
            return `<span class="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${badgeClass}">${value}x${icon}</span>`;
        }

        function renderDsBar(score) {
            const width = clamp(score, 0, 100);
            const barClass = getDsBarClass(score);
            return `
                <div class="w-full min-w-[120px] bg-gray-800 rounded-full h-2 overflow-hidden">
                    <div class="h-full rounded-full ${barClass}" style="width: ${width}%;"></div>
                </div>
            `;
        }

        function getVrBadgeClass(vr) {
            if (vr > 2.0) return 'bg-rose-500/15 text-rose-200 border border-rose-500/30';
            if (vr > 1.5) return 'bg-amber-500/15 text-amber-200 border border-amber-500/30';
            return 'bg-slate-800 text-slate-300 border border-slate-700';
        }

        function getDsBarClass(score) {
            if (score >= 75) return 'bg-rose-500';
            if (score >= 45) return 'bg-sky-500';
            return 'bg-emerald-500';
        }

        function renderFiabilityIcons(score) {
            const filled = clamp(score, 0, 3);
            let icons = '';
            for (let i = 1; i <= 3; i += 1) {
                if (i <= filled) {
                    const colorClass = score === 3 ? 'text-emerald-400' : score === 2 ? 'text-amber-400' : 'text-rose-400';
                    icons += `<i class="fa-solid fa-shield-alt ${colorClass} mx-0.5"></i>`;
                } else {
                    icons += `<i class="fa-solid fa-shield text-slate-600 mx-0.5"></i>`;
                }
            }
            return `<div class="flex items-center justify-center text-base">${icons}</div>`;
        }

        function getPriceColorClass(current, old) {
            if (!current || !old || current === old) return "text-gray-400";
            return current > old ? "text-emerald-500/90" : "text-rose-500/90";
        }

        // INVERSER LA DIRECTION DU TRI DES COLONNES
        function handleSort(columnName) {
            if (appState.sortColumn === columnName) {
                appState.sortDirection = appState.sortDirection === "asc" ? "desc" : "asc";
            } else {
                appState.sortColumn = columnName;
                appState.sortDirection = columnName === "n_fr" ? "asc" : "desc";
            }
            renderTable();
        }

        // RE-DESSINER LES FLÈCHES DE TRI (▲/▼)
        function updateSortIcons() {
            const columns = ["n_fr", "p", "v", "p90", "vr", "ds", "f"];
            columns.forEach(col => {
                const icon = document.getElementById(`sort-icon-${col}`);
                if (!icon) return;
                
                if (col === appState.sortColumn) {
                    icon.className = appState.sortDirection === "asc" ? "fa-solid fa-sort-up ml-1 text-cyan-400" : "fa-solid fa-sort-down ml-1 text-cyan-400";
                } else {
                    icon.className = "fa-solid fa-sort ml-1 text-gray-800 opacity-30";
                }
            });
        }

        // CHARGEMENT À LA VOLÉE DE LA FICHE D'ENCYCLOPÉDIE DE L'ITEM
        async function openItemDetails(itemId) {
            const cat = appState.currentCategory;
            const modalContainer = document.getElementById("modal-container");
            const modalContent = document.getElementById("modal-content");
            
            // État visuel "Patientez" pré-chargement
            modalContent.innerHTML = `
                <div class="p-12 flex flex-col items-center justify-center gap-3">
                    <i class="fa-solid fa-circle-notch fa-spin text-2xl text-cyan-400"></i>
                    <p class="text-xs text-gray-400 tracking-wide">Extraction de la fiche encyclopédique...</p>
                </div>
            `;
            modalContainer.classList.remove("hidden");
            setTimeout(() => modalContainer.classList.add("modal-show"), 10);
            setTimeout(() => modalContent.classList.add("modal-scale"), 10);

            // Charger les détails si nécessaire
            if (!PCLData.details[cat] || Object.keys(PCLData.details[cat]).length === 0) {
                try {
                    const res = await fetch(`data/${cat}_details.json`);
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    const data = await res.json();
                    PCLData.details[cat] = data || {};
                } catch (e) {
                    console.warn(`⚠️ Impossible de charger les détails pour ${cat}:`, e);
                    PCLData.details[cat] = {};
                }
            }

            // Récupération des données (sûre)
            const summary = (PCLData.tables[cat] || []).find(i => i.id === itemId) || {};
            const info = (PCLData.details[cat] || {})[itemId] || {};
            
            // Construction robuste de l'URL de l'icône
            let iconUrl = '';
            if (info && info.icon) {
                try {
                    const raw = String(info.icon).trim();
                    if (raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('//')) {
                        iconUrl = raw;
                    } else {
                        const base = 'https://warframe.market/static/assets/';
                        iconUrl = base + encodeURI(raw.replace(/^\/+/, ''));
                    }
                } catch (e) {
                    iconUrl = '';
                }
            }

            const marketSlug = String(info.marketSlug || info.slug || itemId || '').trim().toLowerCase();
            const marketSlugUrl = encodeURIComponent(marketSlug);
            
            // Récupération et calcul des composants
            const components = (info.components || []);
            const componentTotalPrice = components.reduce((sum, comp) => sum + ((comp.p || 0) * (comp.qty || 1)), 0);

            // Log pour déboguer (optionnel - peut être retiré en production)
            console.log('📋 Item Details Loaded:', { 
                itemId, 
                cat, 
                summary_exists: !!summary.n_fr, 
                info_exists: !!info.desc_fr, 
                icon_exists: !!iconUrl,
                components_count: components.length
            });

            // Remplissage dynamique des données réelles
            modalContent.innerHTML = `
                <div class="p-6 bg-gray-950/60 border-b border-gray-800/40 flex items-start justify-between gap-4">
                    <div class="flex items-center gap-4">
                        ${iconUrl ? `<img src="${iconUrl}" loading="lazy" alt="${summary.n_fr || itemId}" class="w-20 h-20 object-contain bg-gray-950 rounded-xl border border-gray-800 p-1 shadow-inner" onerror="this.onerror=null;this.style.display='none'">` : ''}
                        ${!iconUrl ? `<div class="w-20 h-20 bg-gray-950 rounded-xl border border-gray-800 flex items-center justify-center"><i class="fa-solid fa-box text-2xl text-gray-600"></i></div>` : ''}
                        <div>
                            <h2 class="text-xl font-bold text-white tracking-wide">${summary.n_fr || itemId}</h2>
                            <p class="text-xs text-gray-400 font-mono italic">${summary.n_en || ''}</p>
                            <p class="text-[10px] text-slate-500 mt-2">ID: ${itemId}</p>
                        </div>
                    </div>
                    <button onclick="closeModal()" class="text-gray-500 hover:text-white transition-colors p-1"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                
                <div class="p-6 flex flex-col gap-6 max-h-[75vh] overflow-y-auto">
                    ${info.desc_fr || info.desc_en ? `
                    <div class="flex flex-col gap-2">
                        <span class="text-xs font-bold text-cyan-400 uppercase tracking-widest">Description Codex</span>
                        <p class="text-sm text-gray-300 leading-relaxed bg-gray-950/30 border border-gray-800/30 rounded-xl p-3 text-justify italic">
                            ${info.desc_fr || info.desc_en || "Aucune description disponible."}
                        </p>
                    </div>
                    ` : ''}

                    <div class="flex flex-col gap-2">
                        <span class="text-xs font-bold text-cyan-400 uppercase tracking-widest">Synthèse Économique</span>
                        <div class="grid grid-cols-4 gap-2 text-center font-mono text-xs bg-gray-950/30 border border-gray-800/30 rounded-xl p-3">
                            <div>
                                <div class="text-slate-500 mb-1">PRIX</div>
                                <div class="text-white font-bold">${summary.p ? summary.p.toFixed(1) : '0.0'} pl</div>
                                ${summary.p_max !== undefined ? `<div class="text-slate-600 text-[9px] mt-1">R0</div><div class="text-white font-bold mt-1">${summary.p_max ? summary.p_max.toFixed(1) : '0.0'} pl</div><div class="text-slate-600 text-[9px]">Rmax</div>` : ''}
                            </div>
                            <div>
                                <div class="text-slate-500 mb-1">VOL</div>
                                <div class="text-white font-bold">${summary.v ? (summary.v >= 1000 ? (summary.v / 1000).toFixed(1) + 'k' : summary.v) : '0'}</div>
                                ${summary.v_max !== undefined ? `<div class="text-slate-600 text-[9px] mt-1">R0</div><div class="text-white font-bold mt-1">${summary.v_max ? (summary.v_max >= 1000 ? (summary.v_max / 1000).toFixed(1) + 'k' : summary.v_max) : '0'}</div><div class="text-slate-600 text-[9px]">Rmax</div>` : ''}
                            </div>
                            <div>
                                <div class="text-slate-500 mb-1">Δ90</div>
                                <div class="${summary.p90 > 0 ? 'text-emerald-300' : summary.p90 < 0 ? 'text-rose-400' : 'text-gray-400'} font-bold">${summary.p90 > 0 ? '▲ +' : summary.p90 < 0 ? '▼ ' : '• '}${Math.abs(summary.p90 || 0).toFixed(1)}%</div>
                                ${summary.p90_max !== undefined ? `<div class="text-slate-600 text-[9px] mt-1">R0</div><div class="${summary.p90_max > 0 ? 'text-emerald-300' : summary.p90_max < 0 ? 'text-rose-400' : 'text-gray-400'} font-bold mt-1">${summary.p90_max > 0 ? '▲ +' : summary.p90_max < 0 ? '▼ ' : '• '}${Math.abs(summary.p90_max || 0).toFixed(1)}%</div><div class="text-slate-600 text-[9px]">Rmax</div>` : ''}
                            </div>
                            <div>
                                <div class="text-slate-500 mb-1">HYPE</div>
                                <div class="${summary.vr > 2 ? 'text-rose-400' : summary.vr > 1.5 ? 'text-amber-400' : 'text-slate-300'} font-bold">${summary.vr ? summary.vr.toFixed(1) : '0.0'}x</div>
                                ${summary.vr_max !== undefined ? `<div class="text-slate-600 text-[9px] mt-1">R0</div><div class="${summary.vr_max > 2 ? 'text-rose-400' : summary.vr_max > 1.5 ? 'text-amber-400' : 'text-slate-300'} font-bold mt-1">${summary.vr_max ? summary.vr_max.toFixed(1) : '0.0'}x</div><div class="text-slate-600 text-[9px]">Rmax</div>` : ''}
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-2 text-center font-mono text-xs mt-2">
                            <div class="bg-gray-950/30 border border-gray-800/30 rounded-xl p-3">
                                <div class="text-slate-500 mb-1">DONCHIAN</div>
                                <div class="bg-gray-800 rounded-full h-2 overflow-hidden mt-2">
                                    <div class="h-full ${summary.ds >= 75 ? 'bg-rose-500' : summary.ds >= 45 ? 'bg-sky-500' : 'bg-emerald-500'}" style="width: ${Math.min(Math.max(summary.ds || 0, 0), 100)}%;"></div>
                                </div>
                                <div class="text-white font-bold mt-2">${summary.ds ? summary.ds.toFixed(1) : '0.0'}%</div>
                                ${summary.ds_max !== undefined ? `<div class="text-slate-600 text-[9px] mt-2">R0</div><div class="bg-gray-800 rounded-full h-2 overflow-hidden mt-1"><div class="h-full ${summary.ds_max >= 75 ? 'bg-rose-500' : summary.ds_max >= 45 ? 'bg-sky-500' : 'bg-emerald-500'}" style="width: ${Math.min(Math.max(summary.ds_max || 0, 0), 100)}%;"></div></div><div class="text-white font-bold mt-1">${summary.ds_max ? summary.ds_max.toFixed(1) : '0.0'}%</div><div class="text-slate-600 text-[9px]">Rmax</div>` : ''}
                            </div>
                            <div class="bg-gray-950/30 border border-gray-800/30 rounded-xl p-3">
                                <div class="text-slate-500 mb-1">FIABILITE</div>
                                <div class="flex items-center justify-center gap-1 mt-2">
                                    ${[1,2,3].map(i => `<i class="fa-solid ${i <= (summary.f || 0) ? (summary.f === 3 ? 'fa-shield-alt text-emerald-400' : summary.f === 2 ? 'fa-shield-alt text-amber-400' : 'fa-shield-alt text-rose-400') : 'fa-shield text-slate-600'}"></i>`).join('')}
                                </div>
                                <div class="text-white font-bold mt-2">${summary.f || 0}/3</div>
                                ${summary.f_max !== undefined ? `<div class="text-slate-600 text-[9px] mt-2">R0</div><div class="flex items-center justify-center gap-1 mt-1">${[1,2,3].map(i => `<i class="fa-solid ${i <= (summary.f_max || 0) ? (summary.f_max === 3 ? 'fa-shield-alt text-emerald-400' : summary.f_max === 2 ? 'fa-shield-alt text-amber-400' : 'fa-shield-alt text-rose-400') : 'fa-shield text-slate-600'}"></i>`).join('')}</div><div class="text-white font-bold mt-1">${summary.f_max || 0}/3</div><div class="text-slate-600 text-[9px]">Rmax</div>` : ''}
                            </div>
                        </div>
                    </div>

                    ${info.expert_tips && info.expert_tips.length > 0 ? `
                    <div class="flex flex-col gap-2">
                        <span class="text-xs font-bold text-orange-400 uppercase tracking-widest">💡 Astuces d'Experts</span>
                        <div class="tips-carousel bg-gradient-to-br from-orange-950/20 to-amber-950/20 border border-orange-700/40 rounded-xl p-4">
                            ${info.expert_tips.map((tip, idx) => `
                                <div class="tip-item ${idx === 0 ? 'active' : ''}" data-tip-index="${idx}">
                                    <div class="mb-2">
                                        <h4 class="text-sm font-semibold text-orange-300">L'astuce de <span class="handwriting text-orange-200 text-base">${tip.author}</span> :</h4>
                                    </div>
                                    <p class="handwriting text-base text-amber-100 leading-relaxed italic bg-orange-950/40 rounded-lg p-3 border border-orange-700/20">
                                        "${tip.text}"
                                    </p>
                                </div>
                            `).join('')}
                        </div>
                        <div class="text-xs text-gray-500 text-center">
                            <span id="tip-counter"></span>
                        </div>
                    </div>
                    ` : ''}

                    ${components.length > 0 ? `
                    <div class="flex flex-col gap-2">
                        <span class="text-xs font-bold text-cyan-400 uppercase tracking-widest">Composants du Set</span>
                        <div class="space-y-2">
                            ${components.map(comp => {
                                return `
                                    <div class="bg-gray-900/50 border border-gray-800/50 rounded-lg p-3">
                                        <div class="flex items-start justify-between gap-2 mb-2">
                                            <div>
                                                <div class="text-base font-bold text-white">${comp.n_fr || comp.slug}</div>
                                                <div class="text-xs text-gray-500 italic font-mono">${comp.n_en || ''}</div>
                                                <div class="text-xs text-gray-600 mt-1">Qty: ${comp.qty || 1}</div>
                                            </div>
                                            <div class="text-right">
                                                <div class="text-sm font-bold text-cyan-300">${(comp.p || 0).toFixed(1)} pl × ${comp.qty || 1} = <span class="text-emerald-400">${((comp.p || 0) * (comp.qty || 1)).toFixed(1)} pl</span></div>
                                            </div>
                                        </div>
                                        <div class="grid grid-cols-5 gap-1 text-[10px] font-mono text-gray-400">
                                            <div><span class="text-slate-500">VOL:</span> ${comp.v ? (comp.v >= 1000 ? (comp.v / 1000).toFixed(1) + 'k' : comp.v) : '0'}</div>
                                            <div><span class="text-slate-500">Δ90:</span> ${comp.p90 > 0 ? '▲' : comp.p90 < 0 ? '▼' : '•'} ${Math.abs(comp.p90 || 0).toFixed(1)}%</div>
                                            <div><span class="text-slate-500">HYPE:</span> ${(comp.vr || 0).toFixed(1)}x</div>
                                            <div><span class="text-slate-500">DONCHIAN:</span> ${(comp.ds || 0).toFixed(1)}%</div>
                                            <div><span class="text-slate-500">FIA:</span> ${comp.f || 0}/3</div>
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                        <div class="bg-amber-950/30 border border-amber-700/30 rounded-lg p-3 mt-3">
                            <div class="text-xs font-bold text-amber-300 uppercase tracking-widest mb-2">Analyse de Composition</div>
                            <div class="grid grid-cols-2 gap-2 text-sm">
                                <div class="flex justify-between">
                                    <span class="text-gray-400">Prix du Set:</span>
                                    <span class="text-white font-bold">${(summary.p || 0).toFixed(1)} pl</span>
                                </div>
                                <div class="flex justify-between">
                                    <span class="text-gray-400">Somme Composants:</span>
                                    <span class="text-white font-bold">${componentTotalPrice.toFixed(1)} pl</span>
                                </div>
                                <div class="flex justify-between col-span-2 pt-2 border-t border-amber-700/30">
                                    <span class="text-amber-300 font-semibold">Différence:</span>
                                    <span class="${(summary.p || 0) > componentTotalPrice ? 'text-emerald-400' : (summary.p || 0) < componentTotalPrice ? 'text-rose-400' : 'text-gray-400'} font-bold">${((summary.p || 0) - componentTotalPrice).toFixed(1)} pl ${((summary.p || 0) - componentTotalPrice > 0 ? '(Profit)' : '(Perte)')}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    ` : ''}
                </div>

                <div class="px-6 py-4 bg-gray-950/40 border-t border-gray-800/40 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 text-xs">
                    <div class="flex flex-wrap gap-2">
                        ${info.wiki_fr ? `<a href="${info.wiki_fr}" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-cyan-950/40 text-cyan-400 border border-cyan-500/30 font-semibold rounded-lg hover:bg-cyan-500 hover:text-black transition-all text-xs"><i class="fa-solid fa-book-open"></i> Wiki FR</a>` : ''}
                        ${info.wiki_en ? `<a href="${info.wiki_en}" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-950/40 text-blue-400 border border-blue-500/30 font-semibold rounded-lg hover:bg-blue-500 hover:text-black transition-all text-xs"><i class="fa-solid fa-book-open"></i> Wiki EN</a>` : ''}
                        ${marketSlug ? `<a href="https://warframe.market/items/${marketSlugUrl}?type=sell" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-green-950/40 text-emerald-300 border border-emerald-500/30 font-semibold rounded-lg hover:bg-emerald-500 hover:text-black transition-all text-xs"><i class="fa-solid fa-hand-holding-dollar"></i> Offres</a>` : ''}
                        ${marketSlug ? `<a href="https://warframe.market/items/${marketSlugUrl}/statistics" target="_blank" class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-violet-950/40 text-violet-300 border border-violet-500/30 font-semibold rounded-lg hover:bg-violet-500 hover:text-black transition-all text-xs"><i class="fa-solid fa-chart-line"></i> Statistiques</a>` : ''}
                    </div>
                    ${marketSlug ? `<span class="text-gray-400 italic">Market slug: ${marketSlug}</span>` : ''}
                </div>
            `;
            
            // Démarrer le carrousel des astuces si disponible
            setTimeout(() => startTipsCarousel(), 100);
        }

        // OUVERTURE DE LA MODALE "GUIDE"
        async function openGuideModal() {
            const modalContainer = document.getElementById("modal-container");
            const modalContent = document.getElementById("modal-content");

            modalContent.innerHTML = `
                <div class="p-6 bg-gray-950/60 border-b border-gray-800/40 flex items-center justify-between">
                    <h2 class="text-lg font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-book text-cyan-400"></i> Guide
                    </h2>
                    <button onclick="closeModal()" class="text-gray-500 hover:text-white transition-colors p-1"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <div class="p-6 flex flex-col gap-3 text-sm text-gray-300 max-h-[70vh] overflow-y-auto prose prose-invert">
                    <i class="fa-solid fa-circle-notch fa-spin text-cyan-400 text-lg"></i> Chargement du guide...
                </div>
            `;
            modalContainer.classList.remove("hidden");
            setTimeout(() => modalContainer.classList.add("modal-show"), 10);
            setTimeout(() => modalContent.classList.add("modal-scale"), 10);

            try {
                const res = await fetch("guide.md");
                const markdown = await res.text();
                const htmlContent = markdownToHTML(markdown);
                document.querySelector(".prose").innerHTML = htmlContent;
            } catch (e) {
                document.querySelector(".prose").innerHTML = `<p class="text-red-400">⚠️ Impossible de charger le fichier guide.md</p>`;
            }
        }

        // OUVERTURE DE LA MODALE "README"
        async function openReadmeModal() {
            const modalContainer = document.getElementById("modal-container");
            const modalContent = document.getElementById("modal-content");

            modalContent.innerHTML = `
                <div class="p-6 bg-gray-950/60 border-b border-gray-800/40 flex items-center justify-between">
                    <h2 class="text-lg font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-file-lines text-cyan-400"></i> README
                    </h2>
                    <button onclick="closeModal()" class="text-gray-500 hover:text-white transition-colors p-1"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <div class="p-6 flex flex-col gap-3 text-sm text-gray-300 max-h-[70vh] overflow-y-auto prose prose-invert">
                    <i class="fa-solid fa-circle-notch fa-spin text-cyan-400 text-lg"></i> Chargement du README...
                </div>
            `;
            modalContainer.classList.remove("hidden");
            setTimeout(() => modalContainer.classList.add("modal-show"), 10);
            setTimeout(() => modalContent.classList.add("modal-scale"), 10);

            try {
                const res = await fetch("readme.md");
                const markdown = await res.text();
                const htmlContent = markdownToHTML(markdown);
                document.querySelector(".prose").innerHTML = htmlContent;
            } catch (e) {
                document.querySelector(".prose").innerHTML = `<p class="text-red-400">⚠️ Impossible de charger le fichier readme.md</p>`;
            }
        }

        // OUVERTURE DE LA MODALE "AUTEUR"
        function openAuthorModal() {
            const modalContainer = document.getElementById("modal-container");
            const modalContent = document.getElementById("modal-content");

            modalContent.innerHTML = `
                <div class="p-6 bg-gray-950/60 border-b border-gray-800/40 flex items-center justify-between">
                    <h2 class="text-lg font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <i class="fa-solid fa-user text-cyan-400"></i> Auteur & Crédits
                    </h2>
                    <button onclick="closeModal()" class="text-gray-500 hover:text-white transition-colors p-1"><i class="fa-solid fa-xmark text-lg"></i></button>
                </div>
                <div class="p-6 flex flex-col gap-6 text-sm text-gray-300 max-h-[70vh] overflow-y-auto">
                    <img src="PCL_background.jpg" alt="Bannière PCL" class="w-full h-48 object-cover rounded-xl border border-gray-800 shadow-lg" />
                    
                    <div class="flex flex-col gap-4">
                        <div>
                            <h3 class="text-lg font-bold text-white mb-2">Protideus</h3>
                            <p class="text-sm text-gray-400 mb-2">Développeur principal</p>
                            <p class="text-cyan-400 font-semibold">Clan L-Zass</p>
                        </div>

                        <div class="border-t border-gray-800 pt-4">
                            <h4 class="text-sm font-bold text-white mb-2">✨ Assistants IA</h4>
                            <ul class="text-xs text-gray-400 space-y-1.5">
                                <li>🤖 <span class="text-cyan-300">Google Gemini</span> - Optimisation et debugging</li>
                                <li>🤖 <span class="text-cyan-300">GitHub Copilot</span> (gratuit) - Refactorisation et patterns</li>
                            </ul>
                        </div>

                        <div class="border-t border-gray-800 pt-4">
                            <h4 class="text-sm font-bold text-white mb-2">📚 Inspirations</h4>
                            <p class="text-xs text-gray-400 mb-2">
                                Inspiré du projet initial de 
                                <a href="https://github.com/Steffronte/L-Zass-Price-Checklist" target="_blank" class="text-cyan-400 hover:text-cyan-300 underline">Steffronté</a>
                            </p>
                        </div>

                        <div class="border-t border-gray-800 pt-4">
                            <h4 class="text-sm font-bold text-white mb-2">Disclaimer</h4>
                            <ul class="text-xs text-gray-400 space-y-1.5">
                                <span class="text-cyan-300">Digital Extremes Ltd, Warframe and the logo Warframe are registered trademarks. All rights are reserved worldwide. This site has no official link with Digital Extremes Ltd or Warframe or Warframe Market. All artwork, screenshots, characters or other recognizable features of the intellectual property relating to these trademarks are likewise the intellectual property of Digital Extremes Ltd.</span>
                            </ul>
                        </div>

                        <div class="border-t border-gray-800 pt-4 flex flex-col gap-3">
                            <a href="https://clan-warframe.fr/" target="_blank" class="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-cyan-500 text-black font-bold rounded-xl hover:bg-cyan-400 transition-all text-xs uppercase tracking-wider shadow-md">
                                <i class="fa-solid fa-globe"></i> Site du Clan L-Zass
                            </a>
                            <a href="https://github.com/Protideus/PriceCheckList" target="_blank" class="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-gray-800 text-white font-bold rounded-xl hover:bg-gray-700 transition-all text-xs uppercase tracking-wider border border-gray-700">
                                <i class="fa-brands fa-github"></i> Repository GitHub
                            </a>
                        </div>
                    </div>
                </div>
            `;
            modalContainer.classList.remove("hidden");
            setTimeout(() => modalContainer.classList.add("modal-show"), 10);
            setTimeout(() => modalContent.classList.add("modal-scale"), 10);
        }

        // CONVERSION SIMPLE MARKDOWN -> HTML
        function markdownToHTML(markdown) {
            let html = markdown
                .replace(/^### (.*?)$/gm, '<h3 class="text-base font-bold text-cyan-400 mt-4 mb-2">$1</h3>')
                .replace(/^## (.*?)$/gm, '<h2 class="text-lg font-bold text-white mt-5 mb-3">$1</h2>')
                .replace(/^# (.*?)$/gm, '<h1 class="text-2xl font-bold text-white mb-4">$1</h1>')
                .replace(/^- (.*?)$/gm, '<li class="ml-4 text-sm">$1</li>')
                .replace(/\*\*(.*?)\*\*/g, '<strong class="text-white">$1</strong>')
                .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
                .replace(/`(.*?)`/g, '<code class="bg-gray-950 px-2 py-0.5 rounded font-mono text-cyan-300 text-xs">$1</code>')
                .replace(/\n\n/g, '</p><p class="my-3 leading-relaxed text-justify">')
                .replace(/^(?!<|$)/gm, '<p class="my-2 leading-relaxed text-justify">');
            return `<div class="space-y-3">${html}</div>`;
        }

        // FERMETURE DES MODALES (ANIMATION DE DÉGONFLEMENT FLUIDE)
        function closeModal() {
            const modalContainer = document.getElementById("modal-container");
            const modalContent = document.getElementById("modal-content");
            
            // Nettoyer l'intervalle du carrousel d'astuces si actif
            if (window.tipsCarouselInterval) {
                clearInterval(window.tipsCarouselInterval);
                window.tipsCarouselInterval = null;
            }
            
            modalContainer.classList.remove("modal-show");
            modalContent.classList.remove("modal-scale");
            setTimeout(() => modalContainer.classList.add("hidden"), 300);
        }

        // GESTION DU CARROUSEL D'ASTUCES D'EXPERTS
        function startTipsCarousel() {
            // Nettoyer tout intervalle existant
            if (window.tipsCarouselInterval) {
                clearInterval(window.tipsCarouselInterval);
            }

            const tipItems = document.querySelectorAll('.tip-item');
            const tipCounter = document.getElementById('tip-counter');
            
            if (tipItems.length === 0) return;

            let currentIndex = 0;

            const showTip = (index) => {
                tipItems.forEach((item, i) => {
                    if (i === index) {
                        item.classList.add('active');
                    } else {
                        item.classList.remove('active');
                    }
                });
                
                // Mettre à jour le compteur
                if (tipCounter && tipItems.length > 1) {
                    tipCounter.textContent = `Astuce ${index + 1} / ${tipItems.length}`;
                }
            };

            // Afficher la première astuce
            showTip(currentIndex);

            // Boucle automatique toutes les 10 secondes
            window.tipsCarouselInterval = setInterval(() => {
                currentIndex = (currentIndex + 1) % tipItems.length;
                showTip(currentIndex);
            }, 10000);
        }
