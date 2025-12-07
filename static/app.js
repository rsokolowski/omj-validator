// OMJ Validator - Frontend JavaScript

let selectedFiles = [];

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
                alert(data.error || 'Wystąpił błąd podczas wysyłania rozwiązania.');
            }
        } catch (error) {
            console.error('Submit error:', error);
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
