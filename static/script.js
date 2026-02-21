/**
 * JiraExporter frontend controller.
 *
 * Handles authentication, project selection with on-the-fly stats fetching,
 * optional range-selector UI for large projects, and export orchestration.
 */

let isAuthenticated = false;
let selectedProjectKey = null;
let projectTotal = 0;         // total issues in the selected project
let largeProjectThreshold = 500; // overwritten by /api/config on load
let rangeFrom = 1;
let rangeTo = 1;

// ─── Authentication ───────────────────────────────────────────────────────────

/**
 * Authenticate with Jira Cloud.
 *
 * Sends an authentication request to the server and updates the UI
 * based on the response.
 */
async function authenticate() {
    const authBtn = document.getElementById('auth-btn');
    const authStatus = document.getElementById('auth-status');

    authBtn.disabled = true;
    authStatus.innerHTML = '<div class="status-message status-info">Authenticating...</div>';

    try {
        const response = await fetch('/api/authenticate', {
            method: 'POST',
            credentials: 'same-origin',
        });

        const data = await response.json();

        if (data.success) {
            isAuthenticated = true;
            authStatus.innerHTML =
                '<div class="status-message status-success">Successfully authenticated!</div>';
            showProjectsSection();
        } else {
            let errorHtml =
                `<div class="status-message status-error">Authentication failed: ${data.error}`;

            if (data.setup_url) {
                errorHtml += `<br><br>To create an API token, visit:<br>`;
                errorHtml += `<a href="${data.setup_url}" target="_blank" style="color:#0052cc;word-break:break-all;">${data.setup_url}</a>`;
                errorHtml += `<br><br>Then add it to your .env file:`;
                errorHtml += `<br><code style="background:#f4f5f7;padding:10px;display:block;margin-top:5px;">`;
                errorHtml += `JIRA_EMAIL=your-email@example.com<br>`;
                errorHtml += `JIRA_API_TOKEN=your-token-here<br>`;
                errorHtml += `JIRA_DOMAIN=yourcompany.atlassian.net`;
                errorHtml += `</code>`;
                errorHtml += `<br>Make sure to install python-dotenv:<br>`;
                errorHtml += `<code style="background:#f4f5f7;padding:5px;display:inline-block;margin-top:5px;">pip install python-dotenv</code>`;
            }

            errorHtml += '</div>';
            authStatus.innerHTML = errorHtml;
            authBtn.disabled = false;
        }
    } catch (error) {
        authStatus.innerHTML =
            `<div class="status-message status-error">Error: ${error.message}</div>`;
        authBtn.disabled = false;
    }
}

// ─── Project selection ────────────────────────────────────────────────────────

/**
 * Show the projects section and populate the project dropdown.
 */
async function showProjectsSection() {
    const projectsSection = document.getElementById('projects-section');
    const projectsLoading = document.getElementById('projects-loading');
    const projectSelect = document.getElementById('project-select');
    const exportBtn = document.getElementById('export-btn');

    projectsSection.style.display = 'block';

    try {
        const response = await fetch('/api/projects', { credentials: 'same-origin' });
        const data = await response.json();

        if (data.success) {
            projectsLoading.style.display = 'none';
            projectSelect.style.display = 'block';
            exportBtn.style.display = 'block';

            if (data.projects.length === 0) {
                projectsLoading.style.display = 'block';
                projectsLoading.innerHTML =
                    '<div class="status-message status-info">No projects found. ' +
                    'Make sure you have access to at least one Jira project.</div>';
                return;
            }

            data.projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.key;
                option.textContent = `${project.key} - ${project.name}`;
                projectSelect.appendChild(option);
            });

            projectSelect.addEventListener('change', onProjectSelected);
            exportBtn.disabled = true;
        } else {
            projectsLoading.innerHTML =
                `<div class="status-message status-error">Failed to load projects: ${data.error}</div>`;
        }
    } catch (error) {
        projectsLoading.innerHTML =
            `<div class="status-message status-error">Error: ${error.message}</div>`;
    }
}

/**
 * Handle project dropdown change.
 *
 * Fetches issue stats for the chosen project, shows a warning banner for
 * large projects, and conditionally renders the range-selector slider.
 *
 * @param {Event} e - The change event from the project <select>.
 */
async function onProjectSelected(e) {
    selectedProjectKey = e.target.value;
    const exportBtn = document.getElementById('export-btn');
    const statsSection = document.getElementById('stats-section');
    const rangeSection = document.getElementById('range-section');

    // Reset previous state
    statsSection.innerHTML = '';
    rangeSection.style.display = 'none';
    exportBtn.disabled = !selectedProjectKey;

    if (!selectedProjectKey) return;

    statsSection.innerHTML =
        '<div class="status-message status-info">Checking project size…</div>';

    try {
        const response = await fetch(
            `/api/projects/${selectedProjectKey}/stats`,
            { credentials: 'same-origin' }
        );
        const data = await response.json();

        if (!data.success) {
            statsSection.innerHTML =
                `<div class="status-message status-error">Could not fetch project stats: ${data.error}</div>`;
            return;
        }

        projectTotal = data.total;

        if (projectTotal > largeProjectThreshold) {
            statsSection.innerHTML =
                `<div class="status-message status-info">` +
                `This project contains <strong>${projectTotal}</strong> issues. ` +
                `The export may take several minutes. ` +
                `You can narrow the range below.</div>`;
            renderRangeSlider(projectTotal);
        } else {
            statsSection.innerHTML =
                `<div class="status-message status-info">` +
                `${projectTotal} issue${projectTotal !== 1 ? 's' : ''} found. Ready to export.</div>`;
            // Full export, no range needed
            rangeFrom = 1;
            rangeTo = projectTotal || 1;
        }
    } catch (error) {
        statsSection.innerHTML =
            `<div class="status-message status-error">Error fetching stats: ${error.message}</div>`;
    }
}

// ─── Range slider (JE-15) ─────────────────────────────────────────────────────

/**
 * Render a dual-handle range slider inside #range-section.
 *
 * The slider represents the numeric key suffix of Jira issues
 * (e.g., 1 … 847 for a project with 847 issues). Both handles are
 * implemented with native <input type="range"> elements overlaid on top
 * of each other; the active handle is determined by which one the user
 * last moved.
 *
 * @param {number} total - Total number of issues (= max key suffix).
 */
function renderRangeSlider(total) {
    rangeFrom = 1;
    rangeTo = total;

    const rangeSection = document.getElementById('range-section');
    rangeSection.style.display = 'block';
    rangeSection.innerHTML = `
        <div class="range-slider-wrapper">
            <div class="range-labels">
                <span id="label-from">${selectedProjectKey}-1</span>
                <span id="label-to">${selectedProjectKey}-${total}</span>
            </div>
            <div class="range-track-container">
                <div class="range-track-fill" id="range-fill"></div>
                <input type="range" id="slider-from" min="1" max="${total}"
                       value="1" step="1" class="range-input range-input-from">
                <input type="range" id="slider-to"   min="1" max="${total}"
                       value="${total}" step="1" class="range-input range-input-to">
            </div>
            <p class="range-summary" id="range-summary">
                Exporting <strong>${total}</strong> of <strong>${total}</strong> issues
            </p>
        </div>`;

    const sliderFrom = document.getElementById('slider-from');
    const sliderTo = document.getElementById('slider-to');

    sliderFrom.addEventListener('input', () => onSliderChange(sliderFrom, sliderTo));
    sliderTo.addEventListener('input', () => onSliderChange(sliderFrom, sliderTo));

    updateRangeUI(sliderFrom, sliderTo, total);
}

/**
 * Handle a slider input event, clamping handles to avoid crossing.
 *
 * @param {HTMLInputElement} sliderFrom - The left (From) handle.
 * @param {HTMLInputElement} sliderTo   - The right (To) handle.
 */
function onSliderChange(sliderFrom, sliderTo) {
    let from = parseInt(sliderFrom.value, 10);
    let to = parseInt(sliderTo.value, 10);

    // Prevent handles from crossing
    if (from > to) {
        if (document.activeElement === sliderFrom) {
            sliderFrom.value = to;
            from = to;
        } else {
            sliderTo.value = from;
            to = from;
        }
    }

    rangeFrom = from;
    rangeTo = to;
    updateRangeUI(sliderFrom, sliderTo, parseInt(sliderFrom.max, 10));
}

/**
 * Refresh the range track fill and text labels to match current slider values.
 *
 * @param {HTMLInputElement} sliderFrom - The left (From) handle.
 * @param {HTMLInputElement} sliderTo   - The right (To) handle.
 * @param {number} total                - Total issue count (= slider max).
 */
function updateRangeUI(sliderFrom, sliderTo, total) {
    const from = parseInt(sliderFrom.value, 10);
    const to = parseInt(sliderTo.value, 10);
    const pctFrom = ((from - 1) / (total - 1 || 1)) * 100;
    const pctTo = ((to - 1) / (total - 1 || 1)) * 100;

    const fill = document.getElementById('range-fill');
    if (fill) {
        fill.style.left = pctFrom + '%';
        fill.style.width = (pctTo - pctFrom) + '%';
    }

    const labelFrom = document.getElementById('label-from');
    const labelTo = document.getElementById('label-to');
    if (labelFrom) labelFrom.textContent = `${selectedProjectKey}-${from}`;
    if (labelTo) labelTo.textContent = `${selectedProjectKey}-${to}`;

    const summary = document.getElementById('range-summary');
    if (summary) {
        const count = to - from + 1;
        summary.innerHTML =
            `Exporting <strong>${count}</strong> of <strong>${total}</strong> issues`;
    }
}

// ─── Export ───────────────────────────────────────────────────────────────────

/**
 * Export the selected project (or range) to Markdown and trigger a download.
 *
 * Sends key_from / key_to only when the range slider is visible,
 * so small projects continue to use the full-export path unchanged.
 */
async function exportProject() {
    if (!selectedProjectKey) return;

    const exportBtn = document.getElementById('export-btn');
    const exportStatus = document.getElementById('export-status');
    const progressSection = document.getElementById('progress-section');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    exportBtn.disabled = true;
    exportStatus.innerHTML = '';
    progressSection.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Starting export…';

    // Indeterminate progress message — avoids the misleading fake-fill (JE-27 mitigation).
    progressFill.style.width = '15%';
    progressText.textContent = 'Connecting to Jira… (this may take a few minutes for large projects)';

    const body = { project_key: selectedProjectKey };

    // Include range params only when the slider is shown.
    const rangeSection = document.getElementById('range-section');
    if (rangeSection && rangeSection.style.display !== 'none') {
        body.key_from = rangeFrom;
        body.key_to = rangeTo;
    }

    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify(body),
        });

        if (response.ok) {
            progressFill.style.width = '100%';
            progressText.textContent = 'Generating file…';

            const blob = await response.blob();
            progressText.textContent = 'Download ready!';

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // Use ranged filename when applicable.
            a.download = (body.key_from != null)
                ? `jira-${selectedProjectKey}-${body.key_from}-${body.key_to}.md`
                : `jira-${selectedProjectKey}.md`;

            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            exportStatus.innerHTML =
                '<div class="status-message status-success">Export completed successfully!</div>';

            setTimeout(() => {
                progressSection.style.display = 'none';
                progressFill.style.width = '0%';
                exportBtn.disabled = false;
            }, 2000);
        } else {
            const data = await response.json();
            throw new Error(data.error || 'Export failed');
        }
    } catch (error) {
        exportStatus.innerHTML =
            `<div class="status-message status-error">Export failed: ${error.message}</div>`;
        progressSection.style.display = 'none';
        exportBtn.disabled = false;
    }
}