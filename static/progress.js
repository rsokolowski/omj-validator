/**
 * OMJ Validator - Progress Graph Visualization
 *
 * Uses Cytoscape.js to render an interactive graph of task prerequisites.
 * Tasks are nodes, prerequisites are directed edges.
 */

// Global state
let cy = null;
let progressData = null;
let currentCategory = '';
let options = {};

// Status colors matching CSS variables
const STATUS_COLORS = {
    mastered: '#059669',   // Green
    unlocked: '#2563eb',   // Blue
    locked: '#9ca3af'      // Gray
};

// Category colors
const CATEGORY_COLORS = {
    algebra: '#3b82f6',
    geometria: '#22c55e',
    teoria_liczb: '#f59e0b',
    kombinatoryka: '#8b5cf6',
    logika: '#ef4444',
    arytmetyka: '#06b6d4'
};

// Category Polish names
const CATEGORY_NAMES = {
    algebra: 'Algebra',
    geometria: 'Geometria',
    teoria_liczb: 'Teoria liczb',
    kombinatoryka: 'Kombinatoryka',
    logika: 'Logika',
    arytmetyka: 'Arytmetyka'
};

/**
 * Escape HTML special characters to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped HTML string
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Initialize the progress graph
 * @param {Object} opts - Configuration options
 */
function initProgressGraph(opts) {
    options = opts || {};

    // Setup event listeners
    setupFilterButtons();
    setupControlButtons();
    setupLayoutSelect();

    // Load initial data
    loadProgressData();
}

/**
 * Load progress data from API
 * @param {string} category - Optional category filter
 */
async function loadProgressData(category = '') {
    const loading = document.getElementById('graph-loading');
    const empty = document.getElementById('graph-empty');
    const container = document.getElementById('graph-container');

    loading.style.display = 'flex';
    empty.style.display = 'none';
    container.style.opacity = '0.5';

    try {
        const url = category
            ? `/api/progress/data?category=${encodeURIComponent(category)}`
            : '/api/progress/data';

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        progressData = await response.json();
        currentCategory = category;

        // Update UI components
        updateStats(progressData.stats);
        updateRecommendations(progressData.recommendations);
        renderGraph(progressData);

        // Handle empty state
        if (progressData.nodes.length === 0) {
            empty.style.display = 'flex';
            container.style.display = 'none';
        } else {
            empty.style.display = 'none';
            container.style.display = 'block';
        }

    } catch (error) {
        console.error('Failed to load progress data:', error);
        alert('Nie udalo sie zaladowac danych. Sprobuj odswiezyc strone.');
    } finally {
        loading.style.display = 'none';
        container.style.opacity = '1';
    }
}

/**
 * Update stats dashboard
 * @param {Object} stats - Stats object with total, mastered, unlocked, locked
 */
function updateStats(stats) {
    const elements = {
        'stat-total': stats.total,
        'stat-mastered': stats.mastered,
        'stat-unlocked': stats.unlocked,
        'stat-locked': stats.locked
    };

    for (const [id, value] of Object.entries(elements)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    }
}

/**
 * Update recommendations section
 * @param {Array} recommendations - Array of recommended task nodes
 */
function updateRecommendations(recommendations) {
    const list = document.getElementById('recommended-list');
    const count = document.getElementById('recommended-count');

    if (!list) return;

    if (count) {
        count.textContent = recommendations.length;
    }

    if (recommendations.length === 0) {
        list.innerHTML = `
            <div class="recommendations-empty">
                ${options.canViewProgress
                    ? 'Wszystkie zadania opanowane lub zablokowane. Rozwiaz wiecej zadan!'
                    : 'Zaloguj sie, aby zobaczyc polecane zadania.'}
            </div>
        `;
        return;
    }

    list.innerHTML = recommendations.map(task => `
        <a href="/task/${task.year}/${task.etap}/${task.number}" class="recommendation-card">
            <div class="rec-header">
                <span class="rec-number">${task.year} ${task.etap === 'etap2' ? 'II' : 'I'} #${task.number}</span>
                <span class="rec-difficulty">${'★'.repeat(task.difficulty || 3)}${'☆'.repeat(5 - (task.difficulty || 3))}</span>
            </div>
            <div class="rec-title math-content">${truncateTitle(task.title, 60)}</div>
            <div class="rec-categories">
                ${task.categories.map(cat => `
                    <span class="category-badge category-badge-small category-${cat}">
                        ${CATEGORY_NAMES[cat] || cat}
                    </span>
                `).join('')}
            </div>
        </a>
    `).join('');

    // Render math in recommendations
    if (typeof renderMathInElement !== 'undefined') {
        list.querySelectorAll('.math-content').forEach(el => {
            renderMathInElement(el, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false}
                ],
                throwOnError: false
            });
        });
    }
}

/**
 * Truncate title to max length and escape HTML
 * @param {string} title - Title to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated and escaped title
 */
function truncateTitle(title, maxLength) {
    const truncated = title.length <= maxLength ? title : title.substring(0, maxLength - 3) + '...';
    return escapeHtml(truncated);
}

/**
 * Render the Cytoscape graph
 * @param {Object} data - Progress data with nodes and edges
 */
function renderGraph(data) {
    const container = document.getElementById('graph-container');

    // Convert data to Cytoscape format
    const elements = [];

    // Add nodes
    data.nodes.forEach(node => {
        const primaryCategory = node.categories[0] || 'uncategorized';
        elements.push({
            data: {
                id: node.key,
                label: `${node.number}`,
                fullLabel: `${node.year} ${node.etap === 'etap2' ? 'II' : 'I'} #${node.number}`,
                title: node.title,
                year: node.year,
                etap: node.etap,
                number: node.number,
                difficulty: node.difficulty || 3,
                categories: node.categories,
                status: node.status,
                bestScore: node.best_score,
                prerequisites: node.prerequisites,
                primaryCategory: primaryCategory
            }
        });
    });

    // Add edges
    data.edges.forEach(edge => {
        elements.push({
            data: {
                id: `${edge.source}->${edge.target}`,
                source: edge.source,
                target: edge.target
            }
        });
    });

    // Initialize or update Cytoscape
    if (cy) {
        cy.destroy();
    }

    cy = cytoscape({
        container: container,
        elements: elements,

        style: [
            // Node base style
            {
                selector: 'node',
                style: {
                    'label': 'data(label)',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '12px',
                    'font-weight': 'bold',
                    'color': '#fff',
                    'width': 40,
                    'height': 40,
                    'border-width': 3,
                    'border-color': '#fff',
                    'text-outline-width': 0
                }
            },
            // Status-based colors
            {
                selector: 'node[status = "mastered"]',
                style: {
                    'background-color': STATUS_COLORS.mastered,
                    'border-color': '#047857'
                }
            },
            {
                selector: 'node[status = "unlocked"]',
                style: {
                    'background-color': STATUS_COLORS.unlocked,
                    'border-color': '#1d4ed8'
                }
            },
            {
                selector: 'node[status = "locked"]',
                style: {
                    'background-color': STATUS_COLORS.locked,
                    'border-color': '#6b7280',
                    'opacity': 0.7
                }
            },
            // Edge style
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#d1d5db',
                    'target-arrow-color': '#9ca3af',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'arrow-scale': 1.2
                }
            },
            // Highlighted node (hover)
            {
                selector: 'node:active',
                style: {
                    'overlay-opacity': 0.2,
                    'overlay-color': '#000'
                }
            },
            // Selected node
            {
                selector: 'node:selected',
                style: {
                    'border-width': 4,
                    'border-color': '#f59e0b'
                }
            }
        ],

        layout: getLayoutConfig('dagre'),

        // Interaction options
        minZoom: 0.2,
        maxZoom: 3,
        wheelSensitivity: 0.3,
        boxSelectionEnabled: false
    });

    // Add event listeners
    setupGraphEvents();
}

/**
 * Get layout configuration by name
 * @param {string} layoutName - Layout name
 * @returns {Object} Layout configuration
 */
function getLayoutConfig(layoutName) {
    const configs = {
        dagre: {
            name: 'dagre',
            rankDir: 'TB',  // Top to bottom
            nodeSep: 50,
            rankSep: 80,
            edgeSep: 20,
            animate: true,
            animationDuration: 500
        },
        cose: {
            name: 'cose',
            idealEdgeLength: 100,
            nodeOverlap: 20,
            refresh: 20,
            fit: true,
            padding: 30,
            randomize: false,
            componentSpacing: 100,
            nodeRepulsion: 400000,
            edgeElasticity: 100,
            nestingFactor: 5,
            gravity: 80,
            numIter: 1000,
            initialTemp: 200,
            coolingFactor: 0.95,
            minTemp: 1.0,
            animate: true,
            animationDuration: 500
        },
        grid: {
            name: 'grid',
            fit: true,
            padding: 30,
            rows: undefined,
            cols: undefined,
            animate: true,
            animationDuration: 500
        },
        circle: {
            name: 'circle',
            fit: true,
            padding: 30,
            animate: true,
            animationDuration: 500
        }
    };

    return configs[layoutName] || configs.dagre;
}

/**
 * Setup graph event listeners
 */
function setupGraphEvents() {
    if (!cy) return;

    // Click on node - navigate to task
    cy.on('tap', 'node', function(evt) {
        const node = evt.target;
        const data = node.data();
        const url = `/task/${data.year}/${data.etap}/${data.number}`;
        window.location.href = url;
    });

    // Hover effects - show tooltip
    cy.on('mouseover', 'node', function(evt) {
        const node = evt.target;
        showTooltip(node);
        document.body.style.cursor = 'pointer';
    });

    cy.on('mouseout', 'node', function(evt) {
        hideTooltip();
        document.body.style.cursor = 'default';
    });
}

/**
 * Show tooltip for a node
 * @param {Object} node - Cytoscape node
 */
function showTooltip(node) {
    const tooltip = document.getElementById('task-tooltip');
    if (!tooltip) return;

    const data = node.data();
    const position = node.renderedPosition();
    const container = document.getElementById('graph-container');
    const containerRect = container.getBoundingClientRect();

    // Populate tooltip content
    tooltip.querySelector('.tooltip-title').textContent = data.fullLabel;
    tooltip.querySelector('.tooltip-meta').innerHTML = `
        <span class="difficulty">${'★'.repeat(data.difficulty)}${'☆'.repeat(5 - data.difficulty)}</span>
        <span class="score">Wynik: ${data.bestScore}/${data.etap === 'etap2' ? '6' : '3'}</span>
    `;
    tooltip.querySelector('.tooltip-categories').innerHTML = data.categories.map(cat => `
        <span class="category-badge category-badge-small category-${cat}">${CATEGORY_NAMES[cat] || cat}</span>
    `).join('');

    const statusText = {
        mastered: 'Opanowane',
        unlocked: 'Odblokowane',
        locked: 'Zablokowane'
    };
    tooltip.querySelector('.tooltip-status').innerHTML = `
        <span class="status-badge status-${data.status}">${statusText[data.status]}</span>
    `;
    tooltip.querySelector('.tooltip-link').href = `/task/${data.year}/${data.etap}/${data.number}`;

    // Position tooltip
    const x = containerRect.left + position.x + 20;
    const y = containerRect.top + position.y - 20;

    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
    tooltip.style.display = 'block';

    // Close button
    tooltip.querySelector('.tooltip-close').onclick = () => hideTooltip();
}

/**
 * Hide tooltip
 */
function hideTooltip() {
    const tooltip = document.getElementById('task-tooltip');
    if (tooltip) {
        tooltip.style.display = 'none';
    }
}

/**
 * Setup category filter buttons
 */
function setupFilterButtons() {
    const buttons = document.querySelectorAll('#category-filters .filter-btn');

    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Load filtered data
            const category = btn.dataset.category;
            loadProgressData(category);
        });
    });
}

/**
 * Setup control buttons (zoom, fit, reset)
 */
function setupControlButtons() {
    document.getElementById('zoom-in')?.addEventListener('click', () => {
        if (cy) cy.zoom(cy.zoom() * 1.3);
    });

    document.getElementById('zoom-out')?.addEventListener('click', () => {
        if (cy) cy.zoom(cy.zoom() * 0.7);
    });

    document.getElementById('fit-view')?.addEventListener('click', () => {
        if (cy) cy.fit(50);
    });

    document.getElementById('reset-view')?.addEventListener('click', () => {
        if (cy) {
            cy.fit(50);
            cy.center();
        }
    });
}

/**
 * Setup layout selector
 */
function setupLayoutSelect() {
    const select = document.getElementById('layout-select');
    if (!select) return;

    select.addEventListener('change', () => {
        if (!cy) return;

        const layoutName = select.value;
        const layout = cy.layout(getLayoutConfig(layoutName));
        layout.run();
    });
}
