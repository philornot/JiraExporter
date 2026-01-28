let isAuthenticated = false;
let selectedProjectKey = null;

/**
 * Authenticate with Jira Cloud.
 *
 * Sends authentication request to the server and updates UI
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
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (data.success) {
            isAuthenticated = true;
            authStatus.innerHTML = '<div class="status-message status-success">Successfully authenticated!</div>';
            showProjectsSection();
        } else {
            let errorHtml = `<div class="status-message status-error">Authentication failed: ${data.error}`;

            // Add setup link if configuration is missing
            if (data.setup_url) {
                errorHtml += `<br><br>To create an API token, visit:<br>`;
                errorHtml += `<a href="${data.setup_url}" target="_blank" style="color: #0052cc; word-break: break-all;">${data.setup_url}</a>`;
                errorHtml += `<br><br>Then add it to your .env file:`;
                errorHtml += `<br><code style="background: #f4f5f7; padding: 10px; display: block; margin-top: 5px;">`;
                errorHtml += `JIRA_EMAIL=your-email@example.com<br>`;
                errorHtml += `JIRA_API_TOKEN=your-token-here<br>`;
                errorHtml += `JIRA_DOMAIN=yourcompany.atlassian.net`;
                errorHtml += `</code>`;
                errorHtml += `<br>Make sure to install python-dotenv:<br>`;
                errorHtml += `<code style="background: #f4f5f7; padding: 5px; display: inline-block; margin-top: 5px;">pip install python-dotenv</code>`;
            }

            errorHtml += '</div>';
            authStatus.innerHTML = errorHtml;
            authBtn.disabled = false;
        }
    } catch (error) {
        authStatus.innerHTML = `<div class="status-message status-error">Error: ${error.message}</div>`;
        authBtn.disabled = false;
    }
}

/**
 * Show the projects section and load available projects.
 */
async function showProjectsSection() {
    const projectsSection = document.getElementById('projects-section');
    const projectsLoading = document.getElementById('projects-loading');
    const projectSelect = document.getElementById('project-select');
    const exportBtn = document.getElementById('export-btn');

    projectsSection.style.display = 'block';

    try {
        const response = await fetch('/api/projects', {
            credentials: 'same-origin'
        });
        const data = await response.json();

        if (data.success) {
            projectsLoading.style.display = 'none';
            projectSelect.style.display = 'block';
            exportBtn.style.display = 'block';

            if (data.projects.length === 0) {
                projectsLoading.style.display = 'block';
                projectsLoading.innerHTML = '<div class="status-message status-info">No projects found. Make sure you have access to at least one Jira project.</div>';
                return;
            }

            // Populate project select
            data.projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.key;
                option.textContent = `${project.key} - ${project.name}`;
                projectSelect.appendChild(option);
            });

            // Add change listener
            projectSelect.addEventListener('change', (e) => {
                selectedProjectKey = e.target.value;
                exportBtn.disabled = !selectedProjectKey;
            });

            exportBtn.disabled = true;
        } else {
            projectsLoading.innerHTML = `<div class="status-message status-error">Failed to load projects: ${data.error}</div>`;
        }
    } catch (error) {
        projectsLoading.innerHTML = `<div class="status-message status-error">Error: ${error.message}</div>`;
    }
}

/**
 * Export the selected project to Markdown.
 *
 * Initiates the export process and handles file download.
 *
 * Note: Progress bar is currently simulated on the frontend.
 * Backend does not provide real-time progress updates.
 */
async function exportProject() {
    if (!selectedProjectKey) {
        return;
    }

    const exportBtn = document.getElementById('export-btn');
    const exportStatus = document.getElementById('export-status');
    const progressSection = document.getElementById('progress-section');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    exportBtn.disabled = true;
    exportStatus.innerHTML = '';
    progressSection.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Starting export...';

    // Simulate progress (backend doesn't provide real progress)
    const progressInterval = setInterval(() => {
        const currentWidth = parseInt(progressFill.style.width) || 0;
        if (currentWidth < 90) {
            progressFill.style.width = (currentWidth + 10) + '%';
            if (currentWidth < 30) {
                progressText.textContent = 'Connecting to Jira...';
            } else if (currentWidth < 60) {
                progressText.textContent = 'Fetching issues...';
            } else {
                progressText.textContent = 'Processing data...';
            }
        }
    }, 500);

    try {
        const response = await fetch('/api/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                project_key: selectedProjectKey
            })
        });

        clearInterval(progressInterval);

        if (response.ok) {
            progressFill.style.width = '100%';
            progressText.textContent = 'Generating file...';

            // Get the blob from response
            const blob = await response.blob();

            progressText.textContent = 'Download ready!';

            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `jira-${selectedProjectKey}.md`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            exportStatus.innerHTML = '<div class="status-message status-success">Export completed successfully!</div>';

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
        clearInterval(progressInterval);
        exportStatus.innerHTML = `<div class="status-message status-error">Export failed: ${error.message}</div>`;
        progressSection.style.display = 'none';
        exportBtn.disabled = false;
    }
}