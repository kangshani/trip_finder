document.addEventListener('DOMContentLoaded', () => {
    let rawDestinations = [];
    let config = {};
    let filteredDestinations = [];
    let currentExploreMode = 'cards';

    // Map state
    let map = null;
    let markerClusterGroup = null;
    let mapInitialized = false;

    // Region-to-continent mapping
    const REGION_TO_CONTINENT = {
        'North America': 'Americas',
        'Central America': 'Americas',
        'South America': 'Americas',
        'Caribbean': 'Americas',
        'Western Europe': 'Europe',
        'Eastern Europe': 'Europe',
        'Northern Europe': 'Europe',
        'Southern Europe': 'Europe',
        'East Asia': 'Asia',
        'South Asia': 'Asia',
        'Southeast Asia': 'Asia',
        'Central Asia': 'Asia',
        'Middle East': 'Middle East',
        'North Africa': 'Africa',
        'East Africa': 'Africa',
        'Southern Africa': 'Africa',
        'West Africa': 'Africa',
        'Oceania': 'Oceania',
    };

    const DOM = {
        grid: document.getElementById('destination-grid'),
        resultCount: document.getElementById('result-count'),
        searchInput: document.getElementById('search-input'),
        sortSelect: document.getElementById('sort-select'),
        continentFilters: document.getElementById('continent-filters'),
        scoreMin: document.getElementById('score-min'),
        scoreMax: document.getElementById('score-max'),
        scoreMinLabel: document.getElementById('score-min-label'),
        scoreMaxLabel: document.getElementById('score-max-label'),
        tagFilters: document.getElementById('tag-filters'),
        childFilter: document.getElementById('filter-child'),
        elderlyFilter: document.getElementById('filter-elderly'),
        tabs: document.querySelectorAll('.tab-btn'),
        views: document.querySelectorAll('.view-content'),
        toggleBtns: document.querySelectorAll('.toggle-btn'),
        exploreModes: document.querySelectorAll('.explore-mode'),
    };

    // Plotly dark theme layout defaults
    const PLOTLY_LAYOUT = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { family: 'Inter, sans-serif', color: '#c9d1d9', size: 12 },
        margin: { t: 10, r: 20, b: 40, l: 40 },
        colorway: ['#58a6ff', '#3fb950', '#d29922', '#f85149', '#bc8cff', '#39d353', '#f0883e', '#79c0ff', '#56d364', '#e3b341'],
    };
    const PLOTLY_CONFIG = { displayModeBar: false, responsive: true };

    // Initialization
    async function init() {
        try {
            const configRes = await fetch('/api/config');
            config = await configRes.json();

            const destRes = await fetch('/api/destinations');
            const data = await destRes.json();
            rawDestinations = data.destinations.map(d => processDestination(d));

            // Load preference scores if available
            await loadPreferenceScores();

            buildContinentFilters();
            buildTagFilters();
            initScoreRange();
            bindEvents();
            applyFiltersAndRender();
        } catch (error) {
            console.error('Initialization failed:', error);
            DOM.grid.innerHTML = '<div class="placeholder-msg">Failed to load data. Make sure the backend is running.</div>';
        }
    }

    async function loadPreferenceScores() {
        try {
            const res = await fetch('/api/preference/scores');
            if (!res.ok) return;
            const data = await res.json();
            prefScores = {};
            data.scores.forEach(s => { prefScores[s.slug] = s.score; });
        } catch (e) {
            // Preference engine not initialized yet — scores stay empty
        }
    }

    // Tab switching
    DOM.tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            const btn = e.currentTarget;
            const targetId = btn.getAttribute('data-target');

            DOM.tabs.forEach(t => t.classList.remove('active'));
            DOM.views.forEach(v => v.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(targetId).classList.add('active');

            // Initialize or refresh map when switching to map view
            if (targetId === 'map-view') {
                if (!mapInitialized) {
                    initMap();
                } else {
                    // Leaflet needs invalidateSize after container becomes visible
                    setTimeout(() => map.invalidateSize(), 100);
                }
                updateMapMarkers();
            }

            // Load usage data when switching to API Usage view
            if (targetId === 'usage-view') {
                loadUsageData();
            }
        });
    });

    // Detail panel close
    document.getElementById('detail-close').addEventListener('click', () => {
        document.getElementById('detail-panel').classList.remove('open');
    });

    // Processes destination data for UI
    function processDestination(d) {
        // Ensure string for descriptions to avoid errors
        d.attractions_summary = d.attractions_summary || '';
        d.tags = d.tags || [];

        return d;
    }

    // Get preference score for a destination (0-100, or null if not available)
    function getPrefScore(d) {
        const slug = destToSlug(d);
        return prefScores[slug] ?? null;
    }

    // Explore mode toggle (Cards / Charts)
    DOM.toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.getAttribute('data-mode');
            currentExploreMode = mode;
            DOM.toggleBtns.forEach(b => b.classList.remove('active'));
            DOM.exploreModes.forEach(m => m.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`${mode}-mode`).classList.add('active');
            if (mode === 'charts') renderCharts();
        });
    });

    // Bind UI events
    function bindEvents() {
        DOM.searchInput.addEventListener('input', applyFiltersAndRender);
        DOM.sortSelect.addEventListener('change', applyFiltersAndRender);
        document.querySelectorAll('.month-cb').forEach(cb => {
            cb.addEventListener('change', applyFiltersAndRender);
        });
        DOM.childFilter.addEventListener('change', applyFiltersAndRender);
        DOM.elderlyFilter.addEventListener('change', applyFiltersAndRender);
        DOM.scoreMin.addEventListener('input', () => {
            DOM.scoreMinLabel.textContent = DOM.scoreMin.value;
            applyFiltersAndRender();
        });
        DOM.scoreMax.addEventListener('input', () => {
            DOM.scoreMaxLabel.textContent = DOM.scoreMax.value;
            applyFiltersAndRender();
        });
    }

    // Dynamic continent checkboxes based on loaded data
    function buildContinentFilters() {
        const continents = new Set();
        rawDestinations.forEach(d => {
            const continent = REGION_TO_CONTINENT[d.region] || d.region || 'Other';
            continents.add(continent);
        });

        const sortedContinents = Array.from(continents).sort();
        DOM.continentFilters.innerHTML = sortedContinents.map(c => `
            <label class="checkbox-label">
                <input type="checkbox" value="${c}" class="continent-cb"> ${c}
            </label>
        `).join('');

        document.querySelectorAll('.continent-cb').forEach(cb => {
            cb.addEventListener('change', applyFiltersAndRender);
        });
    }

    // Dynamic tag checkboxes based on loaded data
    function buildTagFilters() {
        const tags = new Set();
        rawDestinations.forEach(d => {
            (d.tags || []).forEach(t => tags.add(t));
        });

        const sortedTags = Array.from(tags).sort();
        DOM.tagFilters.innerHTML = sortedTags.map(t => `
            <label class="checkbox-label">
                <input type="checkbox" value="${t}" class="tag-cb"> ${t.replace(/_/g, ' ')}
            </label>
        `).join('');

        document.querySelectorAll('.tag-cb').forEach(cb => {
            cb.addEventListener('change', applyFiltersAndRender);
        });
    }

    // Set score range slider for preference scores (0-100)
    function initScoreRange() {
        DOM.scoreMin.min = 0;
        DOM.scoreMin.max = 100;
        DOM.scoreMin.step = 1;
        DOM.scoreMin.value = 0;
        DOM.scoreMinLabel.textContent = '0';
        DOM.scoreMax.min = 0;
        DOM.scoreMax.max = 100;
        DOM.scoreMax.step = 1;
        DOM.scoreMax.value = 100;
        DOM.scoreMaxLabel.textContent = '100';
    }

    // Filter pipeline
    function applyFiltersAndRender() {
        const query = DOM.searchInput.value.toLowerCase().trim();
        const activeMonths = Array.from(document.querySelectorAll('.month-cb:checked')).map(cb => cb.value);
        const reqChild = DOM.childFilter.checked;
        const reqElderly = DOM.elderlyFilter.checked;
        const scoreMin = parseFloat(DOM.scoreMin.value);
        const scoreMax = parseFloat(DOM.scoreMax.value);

        // Active continent checkboxes
        const activeContinents = Array.from(document.querySelectorAll('.continent-cb:checked')).map(cb => cb.value);
        // Active tag checkboxes
        const activeTags = Array.from(document.querySelectorAll('.tag-cb:checked')).map(cb => cb.value);

        filteredDestinations = rawDestinations.filter(d => {
            // Search text
            if (query) {
                const textTarget = `${d.name} ${d.display_name} ${d.tags.join(' ')} ${d.country} ${d.attractions_summary}`.toLowerCase();
                if (!textTarget.includes(query)) return false;
            }

            // Continent
            if (activeContinents.length > 0) {
                const continent = REGION_TO_CONTINENT[d.region] || d.region || 'Other';
                if (!activeContinents.includes(continent)) return false;
            }

            // Travel month — destination must have at least one of the selected months
            if (activeMonths.length > 0) {
                if (!d.best_months || !activeMonths.some(m => d.best_months.includes(m))) return false;
            }

            // Preference score range
            const pScore = getPrefScore(d) ?? 50;
            if (pScore < scoreMin || pScore > scoreMax) return false;

            // Interest tags — destination must have ALL selected tags
            if (activeTags.length > 0) {
                const dTags = d.tags || [];
                if (!activeTags.every(t => dTags.includes(t))) return false;
            }

            // Child/Elderly
            if (reqChild && d.child_friendly && d.child_friendly.toLowerCase() === 'no') return false;
            if (reqElderly && d.elderly_friendly && d.elderly_friendly.toLowerCase() === 'no') return false;

            return true;
        });

        sortData();
        renderGrid();
        if (currentExploreMode === 'charts') renderCharts();
        if (mapInitialized) updateMapMarkers();
    }

    function sortData() {
        const sortBy = DOM.sortSelect.value;

        filteredDestinations.sort((a, b) => {
            if (sortBy === 'score') {
                const sa = getPrefScore(a) ?? 50;
                const sb = getPrefScore(b) ?? 50;
                return sb - sa;
            } else if (sortBy === 'name') {
                return (a.display_name || a.name).localeCompare(b.display_name || b.name);
            } else if (sortBy === 'cost') {
                // Costs are string (e.g "$2000"). Fallback to 0 if unknown
                const ca = parseFloat(('' + a.rough_cost).replace(/[^0-9.]/g, '')) || 999999;
                const cb = parseFloat(('' + b.rough_cost).replace(/[^0-9.]/g, '')) || 999999;
                return ca - cb;
            } else if (sortBy === 'flight') {
                // Naive parse for "xh" from "12h direct"
                const faMatch = ('' + a.flight_duration_from_sfo).match(/(\d+)/);
                const fbMatch = ('' + b.flight_duration_from_sfo).match(/(\d+)/);
                const fa = faMatch ? parseInt(faMatch[1]) : 999;
                const fb = fbMatch ? parseInt(fbMatch[1]) : 999;
                return fa - fb;
            }
            return 0;
        });
    }

    function renderGrid() {
        DOM.resultCount.textContent = `${filteredDestinations.length} destination${filteredDestinations.length !== 1 ? 's' : ''}`;

        if (filteredDestinations.length === 0) {
            DOM.grid.innerHTML = '<div class="placeholder-msg">No destinations match your filters.</div>';
            return;
        }

        DOM.grid.innerHTML = filteredDestinations.map(d => {
            const imgIcon = d.season === 'winter' ? '🏔️' : d.season === 'summer' ? '☀️' : '🌴';
            const cost = d.rough_cost || 'Unknown Cost';
            const flight = d.flight_duration_from_sfo || 'Unknown Flight';
            const days = d.recommended_days || '7-10 Days';
            const name = d.display_name || d.name;

            // Use first attraction image as card thumbnail
            const heroImg = getHeroImage(d);
            const ps = getPrefScore(d);
            const badgeText = ps !== null ? `${ps.toFixed(0)}%` : '—';
            const imgHtml = heroImg
                ? `<div class="card-img" style="background-image:url('${heroImg}')"></div>`
                : `<div class="card-img-placeholder"><span>${imgIcon}</span></div>`;

            return `
                <div class="dest-card glass-panel" data-dest-idx="${filteredDestinations.indexOf(d)}" title="${d.attractions_summary.substring(0, 150)}...">
                    ${imgHtml}
                    <div class="card-body">
                        <div class="card-header">
                            <div class="card-header-top">
                                <h3 class="dest-title" title="${name}">${name}</h3>
                                <div class="score-badge">${badgeText}</div>
                            </div>
                            <div class="dest-region">${d.region}, ${d.country}</div>
                        </div>
                        <div class="card-stats">
                            <div class="stat-item">
                                <span class="stat-label">Cost</span>
                                <span class="stat-value">${cost}</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">Flight</span>
                                <span class="stat-value">${flight}</span>
                            </div>
                            <div class="stat-item">
                                <span class="stat-label">Duration</span>
                                <span class="stat-value">${days}</span>
                            </div>
                            <div class="stat-item stat-item-wide">
                                <span class="stat-label">Best Months</span>
                                <span class="stat-value">${(d.best_months || []).map(m => {
                                    const selMonths = Array.from(document.querySelectorAll('.month-cb:checked')).map(cb => cb.value);
                                    const active = selMonths.length > 0 && selMonths.includes(m);
                                    return `<span class="month-chip${active ? ' month-active' : ''}">${m}</span>`;
                                }).join('') || 'Any'}</span>
                            </div>
                        </div>
                        <div class="card-tags">
                            ${d.tags.slice(0, 3).map(t => `<span class="tag">${t.replace('_', ' ')}</span>`).join('')}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Bind card click to open detail panel
        document.querySelectorAll('.dest-card').forEach(card => {
            card.addEventListener('click', () => {
                const idx = parseInt(card.getAttribute('data-dest-idx'));
                openDetailPanel(filteredDestinations[idx]);
            });
        });
    }

    // ── Chart Rendering ──────────────────────────────────────────

    function renderCharts() {
        if (filteredDestinations.length === 0) return;
        renderRegionChart();
        renderSeasonChart();
        renderScoresChart();
        renderInterestsChart();
        renderTagsChart();
    }

    function renderRegionChart() {
        const counts = {};
        filteredDestinations.forEach(d => {
            const r = d.region || 'Unknown';
            counts[r] = (counts[r] || 0) + 1;
        });
        const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
        const trace = {
            labels: sorted.map(e => e[0]),
            values: sorted.map(e => e[1]),
            type: 'pie',
            hole: 0.45,
            textinfo: 'label+value',
            textposition: 'outside',
            marker: { colors: PLOTLY_LAYOUT.colorway },
        };
        const layout = { ...PLOTLY_LAYOUT, showlegend: false, margin: { t: 10, r: 10, b: 10, l: 10 } };
        Plotly.newPlot('chart-region', [trace], layout, PLOTLY_CONFIG);
    }

    function renderSeasonChart() {
        const counts = {};
        filteredDestinations.forEach(d => {
            const s = d.season || 'unknown';
            counts[s] = (counts[s] || 0) + 1;
        });
        const labels = Object.keys(counts);
        const values = Object.values(counts);
        const colors = labels.map(l => {
            if (l === 'summer') return '#d29922';
            if (l === 'winter') return '#58a6ff';
            if (l === 'spring') return '#3fb950';
            if (l === 'fall') return '#f0883e';
            return '#8b949e';
        });
        const trace = {
            labels, values, type: 'pie', hole: 0.5,
            textinfo: 'label+percent',
            textposition: 'outside',
            marker: { colors },
        };
        const layout = { ...PLOTLY_LAYOUT, showlegend: false, margin: { t: 10, r: 10, b: 10, l: 10 } };
        Plotly.newPlot('chart-season', [trace], layout, PLOTLY_CONFIG);
    }

    function renderScoresChart() {
        // Horizontal bar chart of all filtered destinations sorted by preference score
        const sorted = [...filteredDestinations].sort((a, b) => (getPrefScore(a) ?? 50) - (getPrefScore(b) ?? 50));
        const names = sorted.map(d => d.display_name || d.name);
        const scores = sorted.map(d => getPrefScore(d) ?? 50);

        // Color bars by preference score intensity (0-100 scale)
        const barColors = scores.map(s => {
            if (s >= 70) return '#3fb950';
            if (s >= 40) return '#d29922';
            return '#8b949e';
        });

        const trace = {
            y: names, x: scores, type: 'bar', orientation: 'h',
            marker: { color: barColors },
            hovertemplate: '%{y}: %{x:.1f}%<extra></extra>',
        };
        const height = Math.max(400, sorted.length * 22);
        const layout = {
            ...PLOTLY_LAYOUT,
            height,
            margin: { t: 10, r: 20, b: 40, l: 180 },
            xaxis: { title: 'Preference Score', range: [0, 100], gridcolor: 'rgba(255,255,255,0.05)', color: '#8b949e' },
            yaxis: { automargin: true, color: '#c9d1d9', tickfont: { size: 11 } },
        };
        Plotly.newPlot('chart-scores', [trace], layout, PLOTLY_CONFIG);
    }

    function renderInterestsChart() {
        // Radar chart: average interest score across all filtered destinations per category
        const categories = config.interests_ranked || [];
        if (categories.length === 0) return;

        const avgScores = categories.map(cat => {
            let sum = 0, count = 0;
            filteredDestinations.forEach(d => {
                if (d.interest_scores && d.interest_scores[cat] !== undefined) {
                    sum += d.interest_scores[cat];
                    count++;
                }
            });
            return count > 0 ? sum / count : 0;
        });

        const trace = {
            type: 'scatterpolar',
            r: [...avgScores, avgScores[0]], // close the polygon
            theta: [...categories.map(c => c.replace('_', ' ')), categories[0].replace('_', ' ')],
            fill: 'toself',
            fillcolor: 'rgba(88, 166, 255, 0.15)',
            line: { color: '#58a6ff' },
            name: 'Avg Score',
        };
        const layout = {
            ...PLOTLY_LAYOUT,
            polar: {
                bgcolor: 'rgba(0,0,0,0)',
                radialaxis: { visible: true, range: [0, 1], gridcolor: 'rgba(255,255,255,0.08)', color: '#8b949e' },
                angularaxis: { color: '#c9d1d9' },
            },
            showlegend: false,
            margin: { t: 30, r: 40, b: 30, l: 40 },
        };
        Plotly.newPlot('chart-interests', [trace], layout, PLOTLY_CONFIG);
    }

    function renderTagsChart() {
        // Count all tags across filtered destinations
        const counts = {};
        filteredDestinations.forEach(d => {
            (d.tags || []).forEach(t => {
                counts[t] = (counts[t] || 0) + 1;
            });
        });
        const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 15);
        const trace = {
            x: sorted.map(e => e[1]),
            y: sorted.map(e => e[0].replace('_', ' ')),
            type: 'bar',
            orientation: 'h',
            marker: { color: '#58a6ff' },
        };
        const layout = {
            ...PLOTLY_LAYOUT,
            margin: { t: 10, r: 20, b: 40, l: 120 },
            xaxis: { title: 'Count', gridcolor: 'rgba(255,255,255,0.05)', color: '#8b949e' },
            yaxis: { automargin: true, color: '#c9d1d9', autorange: 'reversed' },
        };
        Plotly.newPlot('chart-tags', [trace], layout, PLOTLY_CONFIG);
    }

    // ── Map View ──────────────────────────────────────────────────

    function initMap() {
        map = L.map('leaflet-map', {
            center: [25, 10],
            zoom: 2,
            minZoom: 2,
            maxZoom: 12,
            zoomControl: true,
            worldCopyJump: true,
        });

        // Dark tile layer (CartoDB Dark Matter — free, no API key)
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19,
        }).addTo(map);

        markerClusterGroup = L.markerClusterGroup({
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
        });
        map.addLayer(markerClusterGroup);
        mapInitialized = true;
    }

    function getMarkerColor(d) {
        const score = getPrefScore(d) ?? 50;
        if (score >= 70) return '#3fb950'; // green — strong preference
        if (score >= 40) return '#d29922'; // yellow — moderate
        return '#8b949e'; // gray — weak
    }

    function buildTooltipHtml(d) {
        const name = d.display_name || d.name;
        const cost = d.rough_cost || '—';
        const flight = d.flight_duration_from_sfo || '—';
        const days = d.recommended_days ? `${d.recommended_days} days` : '—';
        const months = (d.best_months || []).slice(0, 4).join(', ') || '—';
        const ps = getPrefScore(d);
        const prefText = ps !== null ? `${ps.toFixed(0)}%` : '—';
        const tags = (d.tags || []).slice(0, 2).map(t =>
            `<span class="tt-tag">${t.replace('_', ' ')}</span>`
        ).join('');

        return `<div class="map-tooltip">
            <div class="tt-name">${name}</div>
            <div class="tt-row"><span class="tt-label">Preference</span><span>${prefText}</span></div>
            <div class="tt-row"><span class="tt-label">Cost</span><span>${cost}</span></div>
            <div class="tt-row"><span class="tt-label">Flight</span><span>${flight}</span></div>
            <div class="tt-row"><span class="tt-label">Duration</span><span>${days}</span></div>
            <div class="tt-row"><span class="tt-label">Best</span><span>${months}</span></div>
            <div class="tt-tags">${tags}</div>
        </div>`;
    }

    function updateMapMarkers() {
        if (!mapInitialized) return;
        markerClusterGroup.clearLayers();

        filteredDestinations.forEach(d => {
            if (!d.latitude || !d.longitude) return;

            const color = getMarkerColor(d);
            const marker = L.circleMarker([d.latitude, d.longitude], {
                radius: 8,
                fillColor: color,
                color: '#fff',
                weight: 1.5,
                opacity: 0.9,
                fillOpacity: 0.85,
            });

            marker.bindTooltip(buildTooltipHtml(d), {
                direction: 'top',
                offset: [0, -10],
                className: '',
            });

            marker.on('click', () => openDetailPanel(d));
            markerClusterGroup.addLayer(marker);
        });
    }

    // Convert destination to slug (matches backend preference_engine._dest_slug)
    function destToSlug(d) {
        let slug = (d.display_name || d.name || '').toLowerCase();
        for (const ch of "(),.'\"!") slug = slug.replace(new RegExp('\\' + ch, 'g'), '');
        slug = slug.replace(/&/g, 'and').trim().split(/\s+/).join('-');
        return slug;
    }

    // Get the first available image from key_attractions
    function getHeroImage(d) {
        if (!d.key_attractions) return null;
        for (const a of d.key_attractions) {
            if (a.images && a.images.length > 0 && a.images[0].url) {
                return a.images[0].url;
            }
        }
        return null;
    }

    function buildAttractionsHtml(d) {
        const attractions = d.key_attractions || [];
        if (attractions.length === 0) return '';

        const items = attractions.map(a => {
            const img = (a.images && a.images.length > 0 && a.images[0].url)
                ? `<img class="attr-img" src="${a.images[0].url}" alt="${a.name}" loading="lazy">`
                : `<div class="attr-img attr-img-empty"></div>`;
            const attribution = (a.images && a.images.length > 0 && a.images[0].attribution)
                ? `<span class="attr-credit">${a.images[0].attribution}</span>`
                : '';
            return `<div class="attr-card">
                ${img}
                <div class="attr-name">${a.name}</div>
                ${attribution}
            </div>`;
        }).join('');

        return `<div class="detail-section">
            <h3>Key Attractions</h3>
            <div class="attr-grid">${items}</div>
        </div>`;
    }

    function openDetailPanel(d) {
        const panel = document.getElementById('detail-panel');
        const content = document.getElementById('detail-content');
        const name = d.display_name || d.name;

        const months = (d.best_months || []).map(m =>
            `<span class="month-pill">${m}</span>`
        ).join('');

        const tags = (d.tags || []).map(t =>
            `<span class="tag">${t.replace('_', ' ')}</span>`
        ).join('');

        const links = (d.reference_links || []).map(l => {
            const icon = l.type === 'video' ? '&#9654;' : '&#128196;';
            return `<li>${icon} <a href="${l.url}" target="_blank" rel="noopener">${l.title}</a></li>`;
        }).join('');

        // Cost breakdown chart placeholder
        const cb = d.cost_breakdown || {};
        const hasCostBreakdown = Object.keys(cb).length > 0;
        const costBreakdownHtml = hasCostBreakdown
            ? `<div id="detail-cost-chart" style="height:200px;"></div>`
            : '<p style="color:var(--text-muted);">No breakdown available</p>';

        content.innerHTML = `
            <div class="detail-header">
                <h2>${name}</h2>
                <div class="detail-region">${d.region}, ${d.country}</div>
            </div>

            <div class="detail-stats-grid">
                <div class="detail-stat">
                    <div class="ds-label">Preference</div>
                    <div class="ds-value">${getPrefScore(d) !== null ? getPrefScore(d).toFixed(0) + '%' : '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Cost</div>
                    <div class="ds-value">${d.rough_cost || '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Flight from SFO</div>
                    <div class="ds-value">${d.flight_duration_from_sfo || '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Recommended</div>
                    <div class="ds-value">${d.recommended_days ? d.recommended_days + ' days' : '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Season</div>
                    <div class="ds-value">${d.season || '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Safety</div>
                    <div class="ds-value">${d.safety_rating || '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Visa (US)</div>
                    <div class="ds-value">${d.visa_required || '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Child-Friendly</div>
                    <div class="ds-value">${d.child_friendly || '—'}</div>
                </div>
                <div class="detail-stat">
                    <div class="ds-label">Elderly-Friendly</div>
                    <div class="ds-value">${d.elderly_friendly || '—'}</div>
                </div>
            </div>

            ${d.seasonal_note ? `<div class="detail-section"><h3>Seasonal Note</h3><p>${d.seasonal_note}</p></div>` : ''}

            <div class="detail-section">
                <h3>Best Months</h3>
                <div class="detail-months">${months || '<span style="color:var(--text-muted)">Any</span>'}</div>
            </div>

            <div class="detail-section">
                <h3>Cost Breakdown</h3>
                ${costBreakdownHtml}
            </div>

            <div class="detail-section">
                <h3>About</h3>
                <p>${d.attractions_summary || 'No description available.'}</p>
            </div>

            ${buildAttractionsHtml(d)}

            <div class="detail-section">
                <h3>Tags</h3>
                <div class="detail-tags">${tags || '—'}</div>
            </div>

            ${links ? `<div class="detail-section"><h3>Reference Links</h3><ul>${links}</ul></div>` : ''}
        `;

        panel.classList.add('open');

        // Render cost breakdown donut if data exists
        if (hasCostBreakdown) {
            setTimeout(() => {
                const labels = Object.keys(cb).map(k => k.charAt(0).toUpperCase() + k.slice(1));
                const values = Object.values(cb);
                Plotly.newPlot('detail-cost-chart', [{
                    labels, values, type: 'pie', hole: 0.45,
                    textinfo: 'label+value',
                    textposition: 'outside',
                    marker: { colors: ['#58a6ff', '#3fb950', '#d29922', '#f0883e'] },
                    hovertemplate: '%{label}: $%{value}<extra></extra>',
                }], {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { family: 'Inter, sans-serif', color: '#c9d1d9', size: 11 },
                    showlegend: false,
                    margin: { t: 10, r: 10, b: 10, l: 10 },
                }, { displayModeBar: false, responsive: true });
            }, 50);
        }
    }

    // ── Preference Learning ────────────────────────────────────

    let prefScores = {};   // slug -> score
    let currentPairA = null;
    let currentPairB = null;
    let currentSlugA = '';
    let currentSlugB = '';

    // Tab switching hook for preference view
    function onPreferenceTabActivated() {
        checkPreferenceStatus();
    }

    // Patch tab switching to trigger preference init check
    DOM.tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            const targetId = e.currentTarget.getAttribute('data-target');
            if (targetId === 'preference-view') {
                onPreferenceTabActivated();
            }
        });
    });

    async function checkPreferenceStatus() {
        try {
            const res = await fetch('/api/preference/status');
            const status = await res.json();

            const initSection = document.getElementById('pref-init');
            const compareSection = document.getElementById('pref-compare');
            const resultsSection = document.getElementById('pref-results');
            const similarSection = document.getElementById('pref-similar-section');

            if (!status.initialized) {
                initSection.style.display = '';
                compareSection.style.display = 'none';
                resultsSection.style.display = 'none';
                similarSection.style.display = 'none';
                document.getElementById('pref-init-stats').textContent =
                    `${status.destination_count || rawDestinations.length} destinations available`;
            } else {
                initSection.style.display = 'none';
                // Show results if we have comparisons, otherwise start comparing
                if (status.comparisons_done > 0) {
                    showPreferenceResults();
                } else {
                    startComparing();
                }
                similarSection.style.display = '';
                populateSimilarSelect();
            }
        } catch (err) {
            console.error('Preference status check failed:', err);
        }
    }

    async function initPreferenceEngine() {
        try {
            const res = await fetch('/api/preference/init', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'ok') {
                startComparing();
                document.getElementById('pref-similar-section').style.display = '';
                populateSimilarSelect();
            }
        } catch (err) {
            console.error('Init failed:', err);
        }
    }

    async function startComparing() {
        document.getElementById('pref-init').style.display = 'none';
        document.getElementById('pref-compare').style.display = '';
        document.getElementById('pref-results').style.display = 'none';
        await loadNextPair();
    }

    async function loadNextPair() {
        try {
            const res = await fetch('/api/preference/next-pair');
            const data = await res.json();

            if (data.error) {
                console.error(data.error);
                return;
            }

            currentSlugA = data.slug_a;
            currentSlugB = data.slug_b;
            currentPairA = data.destination_a;
            currentPairB = data.destination_b;

            document.getElementById('pref-comparison-count').textContent = data.comparison_number;
            const phaseEl = document.getElementById('pref-phase');
            phaseEl.textContent = data.phase.replace(/_/g, ' ');

            renderPrefCard('pref-card-a', currentPairA);
            renderPrefCard('pref-card-b', currentPairB);

            // Reset chosen/not-chosen classes
            document.getElementById('pref-card-a').classList.remove('chosen', 'not-chosen');
            document.getElementById('pref-card-b').classList.remove('chosen', 'not-chosen');
        } catch (err) {
            console.error('Load next pair failed:', err);
        }
    }

    function renderPrefCard(containerId, dest) {
        if (!dest) return;
        const el = document.getElementById(containerId);
        const name = dest.display_name || dest.name;
        const heroImg = getHeroImage(dest);
        const cost = dest.rough_cost || '—';
        const flight = dest.flight_duration_from_sfo || '—';
        const days = dest.recommended_days ? `${dest.recommended_days} days` : '—';
        const tags = (dest.tags || []).slice(0, 5);
        const attractions = (dest.key_attractions || []).slice(0, 5);

        const imgHtml = heroImg
            ? `<img class="pref-card-hero" src="${heroImg}" alt="${name}">`
            : `<div class="pref-card-hero" style="display:flex;align-items:center;justify-content:center;font-size:2rem;">
                ${dest.season === 'winter' ? '🏔️' : '☀️'}
               </div>`;

        el.innerHTML = `
            ${imgHtml}
            <h3>${name}</h3>
            <div class="pref-card-region">${dest.region || ''}, ${dest.country || ''}</div>
            <div class="pref-card-meta">
                <span>Cost</span><strong>${cost}</strong>
                <span>Flight</span><strong>${flight}</strong>
                <span>Duration</span><strong>${days}</strong>
                <span>Safety</span><strong>${dest.safety_rating || '—'}</strong>
            </div>
            <div class="pref-card-tags">
                ${tags.map(t => `<span class="pref-card-tag">${t.replace(/_/g, ' ')}</span>`).join('')}
            </div>
            ${attractions.length > 0 ? `
                <ul class="pref-card-attractions">
                    ${attractions.map(a => `<li>${a.name}</li>`).join('')}
                </ul>
            ` : ''}
        `;
    }

    async function submitComparison(choice) {
        // Visual feedback
        const cardA = document.getElementById('pref-card-a');
        const cardB = document.getElementById('pref-card-b');

        if (choice === 'a') {
            cardA.classList.add('chosen');
            cardB.classList.add('not-chosen');
        } else if (choice === 'b') {
            cardB.classList.add('chosen');
            cardA.classList.add('not-chosen');
        }

        try {
            const res = await fetch('/api/preference/compare', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    slug_a: currentSlugA,
                    slug_b: currentSlugB,
                    choice: choice,
                }),
            });
            await res.json();

            // Brief delay for visual feedback, then load next
            setTimeout(() => loadNextPair(), 400);
        } catch (err) {
            console.error('Submit comparison failed:', err);
        }
    }

    async function showPreferenceResults() {
        document.getElementById('pref-init').style.display = 'none';
        document.getElementById('pref-compare').style.display = 'none';
        document.getElementById('pref-results').style.display = '';

        try {
            const res = await fetch('/api/preference/scores');
            const data = await res.json();

            // Cache scores for sort
            prefScores = {};
            data.scores.forEach(s => { prefScores[s.slug] = s.score; });

            const list = document.getElementById('pref-scores-list');
            list.innerHTML = data.scores.map(s => `
                <div class="pref-score-item">
                    <span class="pref-score-rank ${s.rank <= 3 ? 'top-3' : ''}">${s.rank}</span>
                    <span class="pref-score-name">${s.name}</span>
                    <div class="pref-score-bar-container">
                        <div class="pref-score-bar" style="width: ${s.score}%"></div>
                    </div>
                    <span class="pref-score-value">${s.score.toFixed(1)}</span>
                </div>
            `).join('');

            // Refresh explore/map views with updated scores
            applyFiltersAndRender();
        } catch (err) {
            console.error('Load scores failed:', err);
        }
    }

    function populateSimilarSelect() {
        const select = document.getElementById('pref-similar-select');
        const sorted = [...rawDestinations].sort((a, b) =>
            (a.display_name || a.name).localeCompare(b.display_name || b.name)
        );
        select.innerHTML = sorted.map(d => {
            const name = d.display_name || d.name;
            return `<option value="${destToSlug(d)}">${name}</option>`;
        }).join('');
    }

    async function findSimilar(slug) {
        const resultsEl = document.getElementById('pref-similar-results');
        resultsEl.innerHTML = '<div style="color:var(--text-secondary)">Searching...</div>';

        try {
            const res = await fetch(`/api/preference/similar?slug=${encodeURIComponent(slug)}&n=8`);
            const data = await res.json();

            if (!data.similar || data.similar.length === 0) {
                resultsEl.innerHTML = '<div style="color:var(--text-secondary)">No similar destinations found.</div>';
                return;
            }

            resultsEl.innerHTML = data.similar.map(s => {
                const pct = (s.similarity * 100).toFixed(0);
                // Find the destination data for tags
                const dest = rawDestinations.find(d => destToSlug(d) === s.slug);
                const tags = dest ? (dest.tags || []).slice(0, 3) : [];
                const cost = dest ? (dest.rough_cost || '') : '';

                return `
                    <div class="pref-similar-card">
                        <h4>${s.name}</h4>
                        <div class="pref-similar-score">${pct}% similar</div>
                        ${cost ? `<div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:0.4rem;">${cost}</div>` : ''}
                        <div class="pref-similar-tags">
                            ${tags.map(t => `<span class="pref-card-tag">${t.replace(/_/g, ' ')}</span>`).join('')}
                        </div>
                    </div>
                `;
            }).join('');
        } catch (err) {
            console.error('Find similar failed:', err);
            resultsEl.innerHTML = '<div style="color:var(--text-secondary)">Error finding similar destinations.</div>';
        }
    }

    // Bind preference UI events
    document.getElementById('pref-start-btn').addEventListener('click', initPreferenceEngine);
    document.getElementById('pref-pick-a').addEventListener('click', () => submitComparison('a'));
    document.getElementById('pref-pick-b').addEventListener('click', () => submitComparison('b'));
    document.getElementById('pref-pick-equal').addEventListener('click', () => submitComparison('equal'));
    document.getElementById('pref-stop-btn').addEventListener('click', showPreferenceResults);
    document.getElementById('pref-continue-btn').addEventListener('click', startComparing);
    document.getElementById('pref-reset-btn').addEventListener('click', async () => {
        if (confirm('Reset all learned preferences? This cannot be undone.')) {
            await fetch('/api/preference/reset', { method: 'POST' });
            prefScores = {};
            checkPreferenceStatus();
        }
    });
    document.getElementById('pref-similar-btn').addEventListener('click', () => {
        const slug = document.getElementById('pref-similar-select').value;
        if (slug) findSimilar(slug);
    });

    // Also allow clicking a pref card to choose it
    document.getElementById('pref-card-a').addEventListener('click', () => submitComparison('a'));
    document.getElementById('pref-card-b').addEventListener('click', () => submitComparison('b'));

    // ── API Usage Tab ────────────────────────────────────────────────────────
    async function loadUsageData() {
        try {
            const res = await fetch('/api/usage');
            const data = await res.json();

            // Brave
            document.getElementById('usage-brave-used').textContent = data.brave.used;
            document.getElementById('usage-brave-limit').textContent = data.brave.limit;
            document.getElementById('usage-brave-remaining').textContent = data.brave.remaining;
            const bravePct = Math.min(100, (data.brave.used / data.brave.limit) * 100);
            const braveBar = document.getElementById('usage-brave-bar');
            braveBar.style.width = bravePct + '%';
            if (bravePct > 90) braveBar.classList.add('usage-bar-danger');
            else if (bravePct > 70) braveBar.classList.add('usage-bar-warning');

            const braveStatus = document.getElementById('usage-brave-status');
            braveStatus.className = 'usage-status';
            if (data.brave.remaining <= 0) {
                braveStatus.textContent = 'Limit Reached';
                braveStatus.classList.add('usage-status-danger');
            } else if (data.brave.remaining < 100) {
                braveStatus.textContent = 'Low';
                braveStatus.classList.add('usage-status-warning');
            } else {
                braveStatus.textContent = 'Active';
            }

            // DuckDuckGo
            document.getElementById('usage-ddg-total').textContent = data.duckduckgo.total_calls;

            // Serper
            document.getElementById('usage-serper-remaining').textContent = data.serper.remaining;
            document.getElementById('usage-serper-used').textContent = data.serper.used;
            document.getElementById('usage-serper-total').textContent = data.serper.initial_credits;
            document.getElementById('usage-serper-expiry').textContent = data.serper.expiration;
            const serperPct = (data.serper.remaining / data.serper.initial_credits) * 100;
            const serperBar = document.getElementById('usage-serper-bar');
            serperBar.style.width = serperPct + '%';
            if (serperPct < 10) serperBar.classList.add('usage-bar-danger');
            else if (serperPct < 30) serperBar.classList.add('usage-bar-warning');

            const serperStatus = document.getElementById('usage-serper-status');
            serperStatus.className = 'usage-status';
            if (data.serper.expired) {
                serperStatus.textContent = 'Expired';
                serperStatus.classList.add('usage-status-danger');
            } else if (data.serper.remaining <= 0) {
                serperStatus.textContent = 'Exhausted';
                serperStatus.classList.add('usage-status-danger');
            } else {
                serperStatus.textContent = 'Active';
            }

            // SerpApi Google Hotels
            if (data.serpapi) {
                document.getElementById('usage-serpapi-used').textContent = data.serpapi.used;
                document.getElementById('usage-serpapi-limit').textContent = data.serpapi.limit;
                document.getElementById('usage-serpapi-remaining').textContent = data.serpapi.remaining;
                const serpapiPct = Math.min(100, (data.serpapi.used / data.serpapi.limit) * 100);
                const serpapiBar = document.getElementById('usage-serpapi-bar');
                serpapiBar.style.width = serpapiPct + '%';
                serpapiBar.classList.remove('usage-bar-danger', 'usage-bar-warning');
                if (serpapiPct > 90) serpapiBar.classList.add('usage-bar-danger');
                else if (serpapiPct > 70) serpapiBar.classList.add('usage-bar-warning');

                const serpapiStatus = document.getElementById('usage-serpapi-status');
                serpapiStatus.className = 'usage-status';
                if (data.serpapi.remaining <= 0) {
                    serpapiStatus.textContent = 'Limit Reached';
                    serpapiStatus.classList.add('usage-status-danger');
                } else if (data.serpapi.remaining < 25) {
                    serpapiStatus.textContent = 'Low';
                    serpapiStatus.classList.add('usage-status-warning');
                } else {
                    serpapiStatus.textContent = 'Active';
                }
            }
        } catch (err) {
            console.error('Failed to load usage data:', err);
        }
    }

    init();
});
