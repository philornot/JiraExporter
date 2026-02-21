"""
Main Flask application for JiraExporter.

This module provides a web-based UI for exporting Jira Cloud projects
to Markdown files. It handles authentication, project listing, and
export orchestration with proper session management.
"""

import os
import sys
from flask import Flask, render_template, jsonify, request, send_file, session
from jira_client import JiraClient
from markdown_generator import MarkdownGenerator
from logger import setup_logger, log_config_status
import io
import secrets

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ Loaded .env file")
except ImportError:
    print("⚠ python-dotenv not installed. Install with: pip install python-dotenv")
    print("  Environment variables must be set manually or via Docker.")

# Set up logger
logger = setup_logger('jira_exporter')

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', None)

# JE-25: Warn clearly when FLASK_SECRET_KEY is not set. Without a stable key
# every container restart invalidates all existing sessions, silently logging
# users out. We generate a temporary key so the app still starts, but we make
# the risk impossible to miss.
if not app.secret_key:
    app.secret_key = secrets.token_hex(32)
    logger.warning(
        "FLASK_SECRET_KEY is not set. A random key was generated for this run. "
        "Every restart will invalidate all sessions (users will need to re-authenticate). "
        "Set FLASK_SECRET_KEY in your .env file to avoid this. See .env.example."
    )
    print(
        "\n⚠  WARNING: FLASK_SECRET_KEY is not set.\n"
        "   All sessions will be lost on container restart.\n"
        "   Add FLASK_SECRET_KEY=<random-32-char-string> to your .env file.\n"
    )

# Get credentials from environment variables
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
JIRA_DOMAIN = os.getenv('JIRA_DOMAIN')

# JE-3: Configurable threshold above which the range-selector UI is shown.
LARGE_PROJECT_THRESHOLD = int(os.getenv('LARGE_PROJECT_THRESHOLD', '500'))

# Log configuration status (with masked sensitive data)
log_config_status(logger, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN)

if not all([JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN]):
    logger.warning("Missing required environment variables!")


def get_jira_client():
    """Get or create a Jira client for the current request.

    Creates a new client instance per request using credentials from
    environment variables. This avoids global state and session issues.

    Returns:
        JiraClient: Initialized Jira client instance.

    Raises:
        ValueError: If required credentials are missing.
    """
    if not all([JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN]):
        missing = [
            name
            for name, val in [
                ('JIRA_EMAIL', JIRA_EMAIL),
                ('JIRA_API_TOKEN', JIRA_API_TOKEN),
                ('JIRA_DOMAIN', JIRA_DOMAIN),
            ]
            if not val
        ]
        error_msg = f'Missing required environment variables: {", ".join(missing)}'
        logger.error(error_msg)
        raise ValueError(error_msg)

    return JiraClient(JIRA_DOMAIN, JIRA_EMAIL, JIRA_API_TOKEN, logger=logger)


@app.route('/')
def index():
    """Render the main application page.

    Returns:
        str: Rendered HTML template for the main UI.
    """
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get configuration status for debugging.

    Returns:
        tuple: JSON response with config status and HTTP status code.
    """
    masked_email = None
    if JIRA_EMAIL:
        email_parts = JIRA_EMAIL.split('@')
        if len(email_parts) == 2:
            masked_email = f"{email_parts[0][0]}***@{email_parts[1]}"
        else:
            masked_email = "***"

    return jsonify({
        'email_set': bool(JIRA_EMAIL),
        'token_set': bool(JIRA_API_TOKEN),
        'domain_set': bool(JIRA_DOMAIN),
        'email': masked_email,
        'domain': JIRA_DOMAIN if JIRA_DOMAIN else None,
        'token_length': len(JIRA_API_TOKEN) if JIRA_API_TOKEN else 0,
        'large_project_threshold': LARGE_PROJECT_THRESHOLD,
    }), 200


@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    """Authenticate with Jira Cloud using environment-variable credentials.

    This endpoint verifies the connection to Jira Cloud and marks
    the session as authenticated if successful.

    Returns:
        tuple: JSON response with authentication status and HTTP status code.
    """
    try:
        logger.info("Authentication attempt started")
        jira_client = get_jira_client()
        jira_client.test_connection()
        logger.info("Authentication successful")
        session['authenticated'] = True
        return jsonify({'success': True}), 200
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Configuration error: {error_msg}")
        return jsonify({
            'success': False,
            'error': error_msg,
            'setup_url': 'https://id.atlassian.com/manage-profile/security/api-tokens',
        }), 400
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Authentication failed: {error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 401


@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Retrieve list of all accessible Jira projects.

    Returns:
        tuple: JSON response with projects list and HTTP status code.
    """
    if not session.get('authenticated'):
        logger.warning("Unauthorized access attempt to /api/projects")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        logger.info("Fetching projects list")
        jira_client = get_jira_client()
        projects = jira_client.get_all_projects()
        logger.info(f"Found {len(projects)} projects")
        return jsonify({'success': True, 'projects': projects}), 200
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to fetch projects: {error_msg}", exc_info=True)
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/projects/<string:project_key>/stats', methods=['GET'])
def get_project_stats(project_key: str):
    """Return lightweight statistics for a single project.

    Calls ``JiraClient.get_issue_count()`` which issues a single JQL
    request with ``maxResults=0`` — no issue data is fetched, so the
    response arrives in ~200 ms even for very large projects.

    This endpoint is consumed by the frontend immediately after the user
    selects a project from the dropdown. When the total exceeds the
    configured threshold the UI shows a warning banner and a range slider.

    Args:
        project_key (str): Jira project key, e.g. ``PROJ``.

    Returns:
        tuple: JSON payload and HTTP status code.

        Success (200)::

            {"success": true, "project_key": "PROJ", "total": 847,
             "large_project_threshold": 500}

        Error (401/500)::

            {"success": false, "error": "..."}
    """
    if not session.get('authenticated'):
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        logger.info(f"Fetching stats for project {project_key}")
        jira_client = get_jira_client()
        total = jira_client.get_issue_count(project_key)
        logger.info(f"Project {project_key} stats: {total} issues")
        return jsonify({
            'success': True,
            'project_key': project_key,
            'total': total,
            'large_project_threshold': LARGE_PROJECT_THRESHOLD,
        }), 200
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to fetch stats for {project_key}: {error_msg}", exc_info=True)
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/export', methods=['POST'])
def export_project():
    """Export a Jira project (or a key-range subset) to a Markdown file.

    Accepts an optional ``key_from`` / ``key_to`` pair to limit the export
    to a specific numeric key range. When omitted the full project is
    exported as before (backwards-compatible).

    Expected JSON payload::

        {
            "project_key": "PROJ",
            "key_from": 1,    // optional
            "key_to": 200     // optional
        }

    The generated filename includes the range when a subset is requested:
    ``jira-PROJ-1-200.md`` instead of the default ``jira-PROJ.md``.

    Returns:
        Response: Markdown file download on success, JSON error otherwise.
    """
    if not session.get('authenticated'):
        logger.warning("Unauthorized access attempt to /api/export")
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    try:
        data = request.get_json()
        project_key = data.get('project_key')

        if not project_key:
            return jsonify({'success': False, 'error': 'Project key is required'}), 400

        # JE-17: optional range parameters
        key_from = data.get('key_from')
        key_to = data.get('key_to')
        use_range = key_from is not None and key_to is not None

        logger.info(
            f"Starting export for project: {project_key}"
            + (f" (range {project_key}-{key_from} to {project_key}-{key_to})" if use_range else "")
        )

        jira_client = get_jira_client()

        logger.debug(f"Fetching project details for {project_key}")
        project_name = jira_client.get_project_name(project_key)
        logger.info(f"Project name: {project_name}")

        if use_range:
            logger.info(f"Fetching issues {project_key}-{key_from} to {project_key}-{key_to}")
            issues = jira_client.get_issues_in_key_range(project_key, int(key_from), int(key_to))
            filename = f"jira-{project_key}-{key_from}-{key_to}.md"
        else:
            logger.info(f"Fetching all issues for {project_key}")
            issues = jira_client.get_all_issues(project_key)
            filename = f"jira-{project_key}.md"

        logger.info(f"Successfully fetched {len(issues)} issues")

        logger.debug("Generating Markdown content")
        generator = MarkdownGenerator()
        markdown_content = generator.generate(project_name, issues)
        logger.info(f"Generated Markdown file ({len(markdown_content)} characters)")

        file_content = io.BytesIO(markdown_content.encode('utf-8'))
        logger.info(f"Export completed successfully: {filename}")

        return send_file(
            file_content,
            mimetype='text/markdown',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Export failed: {error_msg}", exc_info=True)
        return jsonify({'success': False, 'error': error_msg}), 500


if __name__ == '__main__':
    if not all([JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN]):
        logger.error("Cannot start - missing environment variables!")
        print("\n" + "!" * 60)
        print("ERROR: Cannot start - missing environment variables!")
        print("!" * 60)
        print("\nPlease create a .env file with:")
        print("  JIRA_EMAIL=your-email@example.com")
        print("  JIRA_API_TOKEN=your-token")
        print("  JIRA_DOMAIN=yourcompany.atlassian.net")
        print("\nGet your API token from:")
        print("  https://id.atlassian.com/manage-profile/security/api-tokens")
        print("\nThen install python-dotenv:")
        print("  pip install python-dotenv")
        print("\n" + "!" * 60 + "\n")
        sys.exit(1)

    logger.info("Starting Flask application")
    app.run(host='0.0.0.0', port=5000, debug=False)