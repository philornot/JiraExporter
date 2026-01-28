# JiraExporter

Local Docker-based application for exporting Jira Cloud projects to Markdown files.

## Prerequisites

- Docker and Docker Compose installed (for Docker deployment)
- Python 3.11+ (for local development)
- Jira Cloud account with API token

## Setup

### 1. Create a Jira API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label (e.g., "JiraExporter")
4. Copy the generated token

### 2. Configure Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your information:
```env
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=ATATT3xFfGF0...your-token-here
JIRA_DOMAIN=yourcompany.atlassian.net
FLASK_SECRET_KEY=your-random-secret-key-here
```

**Important Notes:**
- `JIRA_DOMAIN` should be just the domain part (e.g., `company.atlassian.net`), not the full URL
- `JIRA_API_TOKEN` starts with `ATATT3xFfGF0` and is quite long (usually 200+ characters)
- `FLASK_SECRET_KEY` is optional - one will be generated automatically if not provided

## Running with Docker (Recommended)

Start the application:
```bash
docker-compose up --build
```

Open your browser and navigate to:
```
http://localhost:5000
```

Stop the application:
```bash
docker-compose down
```

## Running Locally (Development)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Important:** Make sure `python-dotenv` is installed to load the `.env` file:
```bash
pip install python-dotenv
```

### 2. Run the Application

```bash
python app.py
```

The application will:
1. Load environment variables from `.env` file
2. Display configuration status in the console
3. Start the Flask server on `http://localhost:5000`

## Usage

1. Open `http://localhost:5000` in your browser
2. Click "Connect to Jira" to authenticate
3. Select a project from the dropdown list
4. Click "Export to Markdown" to download the file
5. The file will be saved as `jira-[PROJECT_KEY].md`

## Logging

The application uses centralized logging that writes to both console and files:

- **Console**: INFO level messages for general operation
- **Log files**: DEBUG level with full details in `logs/[timestamp].log`
- **Sensitive data**: Automatically masked (tokens, emails partially hidden)

Log files are automatically rotated when they reach 10MB, with up to 5 backup files kept.

To view logs:
```bash
# View the latest log file
ls -lt logs/
tail -f logs/[latest-timestamp].log
```

## Troubleshooting

### "Project is archived" Error (HTTP 410)

**Symptoms:**
- Export fails with "410 Client Error: Gone"
- Error message mentions archived project

**Explanation:**
Jira returns HTTP 410 (Gone) for archived projects. These projects cannot be accessed via the API, even if you can still see them in the Jira interface.

**Solutions:**
1. Choose a different, active project from the list
2. Ask your Jira admin to restore the archived project
3. The project list only shows active projects, so this error shouldn't occur if you select from the dropdown

### "Missing required environment variables" Error

**Symptoms:**
- Authentication fails with "Missing required environment variables"
- Console shows `✗ Missing` for JIRA_EMAIL, JIRA_API_TOKEN, or JIRA_DOMAIN

**Solutions:**

1. **If running locally with Python:**
   ```bash
   # Install python-dotenv
   pip install python-dotenv
   
   # Verify .env file exists
   ls -la .env
   
   # Check .env content (make sure there are no extra spaces)
   cat .env
   ```

2. **If running with Docker:**
   ```bash
   # Stop and restart with fresh environment
   docker-compose down
   docker-compose up --build
   ```

3. **Verify .env file format:**
   - No spaces around `=` signs
   - No quotes around values (unless the value contains spaces)
   - No comments on the same line as variables
   
   ✓ Correct:
   ```env
   JIRA_EMAIL=user@example.com
   JIRA_API_TOKEN=ATATT3xFfGF0...
   JIRA_DOMAIN=company.atlassian.net
   ```
   
   ✗ Incorrect:
   ```env
   JIRA_EMAIL = user@example.com  # Extra spaces
   JIRA_API_TOKEN="ATATT3xFfGF0..."  # Unnecessary quotes
   JIRA_DOMAIN=https://company.atlassian.net  # Should not include https://
   ```

### Authentication Fails with Valid Credentials

**Possible causes:**
1. API token has expired or been revoked
2. Email address doesn't match the Atlassian account
3. Domain is incorrect

**Solutions:**
1. Create a new API token at https://id.atlassian.com/manage-profile/security/api-tokens
2. Verify email matches your Atlassian account
3. Check console output for detailed error messages

### No Projects Found

**Possible causes:**
1. Account has no access to any Jira projects
2. All projects are archived

**Solutions:**
1. Log in to Jira Cloud and verify you can see projects
2. Ask your Jira admin to grant you access to projects

### Export Fails or Takes Too Long

**For very large projects (5000+ issues):**
1. The export may take several minutes
2. Browser may show a timeout - check console logs for progress
3. Consider implementing streaming or background job processing

## Features

- Export all issues from a Jira project
- Converts Atlassian Document Format to Markdown
- Includes issue key, summary, status, description, and parent information
- Handles pagination automatically for both projects and issues
- Deterministic ordering (issues sorted by key) for version control
- Browser-based file download
- Detailed logging and error messages

## Known Limitations

### Session Management
Authentication state is stored in Flask sessions, which are lost on container restart. This is acceptable for local, single-user usage but not suitable for production multi-user scenarios.

### ADF Conversion
The Atlassian Document Format to Markdown converter is a proof-of-concept implementation. It handles common structures (paragraphs, headings, lists, links, code blocks, blockquotes) but may not perfectly render complex nested content or all ADF node types.

### Progress Tracking
The UI shows a progress bar, but it's currently simulated on the frontend. The backend performs the export as a single blocking operation without real-time progress updates. Check the console logs to see actual progress.

### Large Projects
For projects with thousands of issues, the export may take significant time and the browser connection might timeout. The console will show progress even if the browser times out.

## Architecture Notes

- Each API request creates a new JiraClient instance to avoid global state issues
- Projects are fetched with pagination using `/project/search` endpoint
- Issues are fetched with `ORDER BY key ASC` for deterministic output
- Session-based authentication (credentials from environment variables)
- Detailed console logging for debugging

## Development

### Project Structure
```
JiraExporter/
├── static/
│   ├── script.js       # Frontend JavaScript
│   └── styles.css      # UI styles
├── templates/
│   └── index.html      # Main UI template
├── .env                # Environment variables (create from .env.example)
├── .env.example        # Example environment variables
├── app.py              # Flask application
├── docker-compose.yml  # Docker Compose configuration
├── Dockerfile          # Docker image definition
├── jira_client.py      # Jira API client
├── markdown_generator.py  # Markdown file generator
├── README.md           # This file
└── requirements.txt    # Python dependencies
```

### Adding Features

To add real-time progress tracking, consider:
1. Server-Sent Events (SSE) for streaming updates
2. WebSocket connection
3. Background job queue (Celery, RQ)

## License

MIT

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review console output for detailed error messages
3. Verify your API token at https://id.atlassian.com/manage-profile/security/api-tokens