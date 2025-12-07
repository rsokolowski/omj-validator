/**
 * OMJ Validator - Progress Page
 *
 * Displays recommended tasks based on user progress.
 */

// Global state
let progressData = null;
let currentCategory = '';
let options = {};

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
 * Initialize the progress page
 * @param {Object} opts - Configuration options
 */
function initProgressPage(opts) {
    options = opts || {};

    // Setup event listeners
    setupFilterButtons();

    // Load initial data
    loadProgressData();
}

/**
 * Load progress data from API
 * @param {string} category - Optional category filter
 */
async function loadProgressData(category = '') {
    const list = document.getElementById('recommended-list');

    if (list) {
        list.innerHTML = '<div class="loading-placeholder">Ladowanie rekomendacji...</div>';
    }

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

        // Update recommendations
        updateRecommendations(progressData.recommendations);

    } catch (error) {
        console.error('Failed to load progress data:', error);
        if (list) {
            list.innerHTML = '<div class="recommendations-empty">Nie udalo sie zaladowac danych. Sprobuj odswiezyc strone.</div>';
        }
    }
}

/**
 * Update recommendations section
 * @param {Array} recommendations - Array of recommended task nodes
 */
function updateRecommendations(recommendations) {
    const list = document.getElementById('recommended-list');

    if (!list) return;

    if (recommendations.length === 0) {
        list.innerHTML = `
            <div class="recommendations-empty">
                ${options.canViewProgress
                    ? 'Brak polecanych zadan dla wybranej kategorii. Sprobuj inna kategorie lub rozwiaz wiecej zadan!'
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
            <div class="rec-title math-content">${truncateTitle(task.title, 80)}</div>
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
