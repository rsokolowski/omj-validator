// OMJ Validator - Frontend JavaScript

let selectedFiles = [];

/**
 * Progress bar controller for validation process.
 * Simulates progress over expected duration with realistic phases.
 */
class ValidationProgress {
    constructor(containerId, expectedDuration = 50000) {
        this.container = document.getElementById(containerId);
        this.expectedDuration = expectedDuration;
        this.startTime = null;
        this.animationFrame = null;
        this.phases = [
            { at: 0, label: 'Przesyłanie zdjęć...' },
            { at: 15, label: 'Przesyłanie do Gemini...' },
            { at: 30, label: 'Analizowanie treści zadania...' },
            { at: 50, label: 'Sprawdzanie rozwiązania...' },
            { at: 70, label: 'Weryfikowanie kroków...' },
            { at: 85, label: 'Generowanie oceny...' },
            { at: 95, label: 'Finalizowanie...' }
        ];
    }

    show() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="progress-wrapper">
                <div class="progress-bar">
                    <div class="progress-fill"></div>
                </div>
                <div class="progress-info">
                    <span class="progress-label">Przygotowywanie...</span>
                    <span class="progress-percent">0%</span>
                </div>
                <div class="progress-time">Szacowany czas: ~${Math.round(this.expectedDuration / 1000)}s</div>
            </div>
        `;
        this.container.style.display = 'block';

        this.fillEl = this.container.querySelector('.progress-fill');
        this.labelEl = this.container.querySelector('.progress-label');
        this.percentEl = this.container.querySelector('.progress-percent');
        this.timeEl = this.container.querySelector('.progress-time');

        this.startTime = Date.now();
        this.animate();
    }

    animate() {
        const elapsed = Date.now() - this.startTime;

        // Linear progress, capped at 95% until complete() is called
        // Note: Phases are time-based estimates, not real backend status
        const progress = Math.min(0.95, elapsed / this.expectedDuration);
        const percent = Math.round(progress * 100);

        // Update progress bar
        this.fillEl.style.width = `${percent}%`;
        this.percentEl.textContent = `${percent}%`;

        // Update label based on phase
        const phase = this.phases.filter(p => p.at <= percent).pop();
        if (phase) {
            this.labelEl.textContent = phase.label;
        }

        // Update time remaining
        const remaining = Math.max(0, this.expectedDuration - elapsed);
        if (remaining > 0) {
            this.timeEl.textContent = `Pozostało: ~${Math.ceil(remaining / 1000)}s`;
        } else {
            this.timeEl.textContent = 'Prawie gotowe...';
        }

        // Continue animation (keep updating time display even after hitting 95%)
        this.animationFrame = requestAnimationFrame(() => this.animate());
    }

    complete() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }

        if (this.fillEl) {
            this.fillEl.style.width = '100%';
            this.percentEl.textContent = '100%';
            this.labelEl.textContent = 'Gotowe!';
            this.timeEl.textContent = '';
        }

        // Hide after short delay
        setTimeout(() => this.hide(), 500);
    }

    hide() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        if (this.container) {
            this.container.style.display = 'none';
        }
    }

    error(message) {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }

        if (this.fillEl) {
            this.fillEl.style.background = 'var(--color-danger, #dc3545)';
            this.labelEl.textContent = message || 'Wystąpił błąd';
            this.timeEl.textContent = '';
        }
    }
}

/**
 * Toggle collapsible section (Skills, Hints).
 * @param {HTMLElement} button - The collapsible header button
 */
function toggleCollapsible(button) {
    const section = button.closest('.collapsible-section');
    section.classList.toggle('expanded');

    // If expanding, render any math content that hasn't been rendered yet
    if (section.classList.contains('expanded')) {
        const mathElements = section.querySelectorAll('.math-content:not([data-math-rendered])');
        mathElements.forEach(el => {
            renderMathInContent(el);
            el.dataset.mathRendered = 'true';
        });
    }
}

/**
 * Toggle hint visibility with progressive reveal.
 * @param {HTMLElement} button - The hint toggle button
 */
function toggleHint(button) {
    const hintItem = button.closest('.hint-item');
    const hintIndex = parseInt(hintItem.dataset.hintIndex);
    const allHints = document.querySelectorAll('.hint-item');

    // If clicking on an already revealed hint, just toggle it
    if (hintItem.classList.contains('revealed')) {
        hintItem.classList.remove('revealed');
        return;
    }

    // Reveal this hint and all previous hints
    allHints.forEach((item, index) => {
        if (index <= hintIndex) {
            item.classList.add('revealed');
            // Render math in the revealed hint content
            const content = item.querySelector('.hint-content');
            if (content && !content.dataset.mathRendered) {
                renderMathInContent(content);
                content.dataset.mathRendered = 'true';
            }
        }
    });
}

/**
 * Render math in a single element using KaTeX.
 * @param {HTMLElement} element - The DOM element to render math in
 */
function renderMathInContent(element) {
    if (typeof renderMathInElement !== 'undefined') {
        renderMathInElement(element, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '\\(', right: '\\)', display: false},
                {left: '\\[', right: '\\]', display: true}
            ],
            throwOnError: false
        });
    }
}

/**
 * Render feedback with Markdown and KaTeX math support.
 * @param {string} text - The feedback text with optional LaTeX ($...$) and Markdown
 * @param {HTMLElement} element - The DOM element to render into
 */
function renderFeedback(text, element) {
    // Configure marked for safe rendering
    marked.setOptions({
        breaks: true,  // Convert \n to <br>
        gfm: true,     // GitHub Flavored Markdown
    });

    // Render Markdown first
    element.innerHTML = marked.parse(text);

    // Then render KaTeX math expressions
    if (typeof renderMathInElement !== 'undefined') {
        renderMathInElement(element, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '\\(', right: '\\)', display: false},
                {left: '\\[', right: '\\]', display: true}
            ],
            throwOnError: false
        });
    }
}

/**
 * Initialize math tooltips with KaTeX rendering.
 * Creates DOM-based tooltips for elements with data-math-tooltip attribute.
 */
function initMathTooltips() {
    document.querySelectorAll('[data-math-tooltip]').forEach(el => {
        let tooltipEl = null;

        el.addEventListener('mouseenter', function() {
            const tooltipText = this.getAttribute('data-math-tooltip');
            if (!tooltipText) return;

            tooltipEl = document.createElement('div');
            tooltipEl.className = 'math-tooltip-popup';
            tooltipEl.textContent = tooltipText;
            this.appendChild(tooltipEl);

            // Render KaTeX in the tooltip
            if (typeof renderMathInElement !== 'undefined') {
                renderMathInElement(tooltipEl, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false},
                        {left: '\\(', right: '\\)', display: false},
                        {left: '\\[', right: '\\]', display: true}
                    ],
                    throwOnError: false
                });
            }
        });

        el.addEventListener('mouseleave', function() {
            if (tooltipEl && tooltipEl.parentNode) {
                tooltipEl.parentNode.removeChild(tooltipEl);
                tooltipEl = null;
            }
        });
    });
}

/**
 * Initialize Markdown and math rendering for all feedback elements on page load.
 */
function initFeedbackRendering() {
    // Check if libraries are available
    if (typeof renderMathInElement === 'undefined' || typeof marked === 'undefined') {
        console.warn('KaTeX or marked not loaded yet, retrying...');
        setTimeout(initFeedbackRendering, 100);
        return;
    }

    // Configure marked for safe rendering
    marked.setOptions({
        breaks: true,
        gfm: true,
    });

    // Render Markdown and math in all existing feedback elements
    document.querySelectorAll('.submission-feedback').forEach(el => {
        // Get text content and render as markdown
        const text = el.textContent || '';
        el.innerHTML = marked.parse(text);

        // Then render math
        renderMathInElement(el, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '\\(', right: '\\)', display: false},
                {left: '\\[', right: '\\]', display: true}
            ],
            throwOnError: false
        });
    });

    // Render math in task content and titles
    document.querySelectorAll('.math-content').forEach(el => {
        renderMathInElement(el, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '\\(', right: '\\)', display: false},
                {left: '\\[', right: '\\]', display: true}
            ],
            throwOnError: false
        });
    });
}

function initTaskPage(year, etap, taskNumber) {
    const form = document.getElementById('submit-form');
    const fileInput = document.getElementById('images');
    const filePreview = document.getElementById('file-preview');
    const submitBtn = document.getElementById('submit-btn');
    const resultContainer = document.getElementById('result-container');

    // Handle file selection
    fileInput.addEventListener('change', function(e) {
        const newFiles = Array.from(e.target.files);
        selectedFiles = [...selectedFiles, ...newFiles];
        updateFilePreview();
    });

    // Update file preview
    function updateFilePreview() {
        filePreview.innerHTML = '';

        selectedFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'file-preview-item';

            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.alt = file.name;

            const removeBtn = document.createElement('button');
            removeBtn.className = 'file-preview-remove';
            removeBtn.innerHTML = '&times;';
            removeBtn.type = 'button';
            removeBtn.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                selectedFiles.splice(index, 1);
                updateFilePreview();
            };

            item.appendChild(img);
            item.appendChild(removeBtn);
            filePreview.appendChild(item);
        });
    }

    // Initialize progress bar (50s expected duration based on actual API timing)
    const progress = new ValidationProgress('validation-progress', 50000);

    // Handle form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        if (selectedFiles.length === 0) {
            alert('Wybierz przynajmniej jedno zdjęcie rozwiązania.');
            return;
        }

        // Show loading state
        const btnText = submitBtn.querySelector('.btn-text');
        const btnLoading = submitBtn.querySelector('.btn-loading');
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline';
        submitBtn.disabled = true;
        resultContainer.style.display = 'none';

        // Start progress bar
        progress.show();

        try {
            const formData = new FormData();
            selectedFiles.forEach(file => {
                formData.append('images', file);
            });

            const response = await fetch(`/task/${year}/${etap}/${taskNumber}/submit`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Complete progress bar
                progress.complete();

                // Show result
                const scoreEl = document.getElementById('result-score');
                const feedbackEl = document.getElementById('result-feedback');

                scoreEl.textContent = data.score;
                scoreEl.className = 'score-value score-' + data.score;
                renderFeedback(data.feedback, feedbackEl);
                resultContainer.style.display = 'block';

                // Clear selected files
                selectedFiles = [];
                fileInput.value = '';
                updateFilePreview();

                // Scroll to result
                resultContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                progress.error('Błąd walidacji');
                setTimeout(() => progress.hide(), 2000);
                alert(data.error || 'Wystąpił błąd podczas wysyłania rozwiązania.');
            }
        } catch (error) {
            console.error('Submit error:', error);
            progress.error('Błąd połączenia');
            setTimeout(() => progress.hide(), 2000);
            alert('Wystąpił błąd połączenia. Spróbuj ponownie.');
        } finally {
            // Reset button state
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
            submitBtn.disabled = false;
        }
    });

    // Allow dropping files on the label
    const fileLabel = document.querySelector('.file-label');
    if (fileLabel) {
        fileLabel.addEventListener('dragover', function(e) {
            e.preventDefault();
            fileLabel.style.borderColor = 'var(--color-primary)';
            fileLabel.style.background = 'var(--color-gray-50)';
        });

        fileLabel.addEventListener('dragleave', function(e) {
            e.preventDefault();
            fileLabel.style.borderColor = '';
            fileLabel.style.background = '';
        });

        fileLabel.addEventListener('drop', function(e) {
            e.preventDefault();
            fileLabel.style.borderColor = '';
            fileLabel.style.background = '';

            const droppedFiles = Array.from(e.dataTransfer.files).filter(
                file => file.type.startsWith('image/')
            );

            if (droppedFiles.length > 0) {
                selectedFiles = [...selectedFiles, ...droppedFiles];
                updateFilePreview();
            }
        });
    }
}
