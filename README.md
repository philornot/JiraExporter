# JiraExporter

Local, Docker-based web application for exporting Jira Cloud projects to Markdown files.

## Features

* Export all issues from a Jira Cloud project to Markdown
* Convert Atlassian Document Format (ADF) to Markdown
* Include issue key, summary, status, description, and parent information
* Automatic pagination for projects and issues
* Deterministic issue ordering (`key ASC`) for version-control-friendly output
* Browser-based file download
* Detailed application logging
* Automatic masking of sensitive data in logs
* Docker support for easy deployment

## Requirements

### Docker deployment

* Docker Engine
* Docker Compose v2
* Jira Cloud account with access to the projects you want to export
* Jira Cloud API token

### Local development

* Python 3.11+
* Jira Cloud account with API token

---

## Configuration

### 1. Create a Jira API token

Create an API token in your Atlassian account:

[Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

1. Click **Create API token**
2. Give the token a descriptive label, for example `JiraExporter`
3. Copy the generated token

> Keep your API token secret. Never commit `.env` or the token to Git.

### 2. Configure environment variables

Create your local `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env`:

```env
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=ATATT3xFfGF0...your-token-here
JIRA_DOMAIN=yourcompany.atlassian.net
FLASK_SECRET_KEY=your-random-secret-key-here
```

#### Configuration reference

| Variable           | Required | Description                                                       |
| ------------------ | -------- | ----------------------------------------------------------------- |
| `JIRA_EMAIL`       | Yes      | Email address associated with your Atlassian account              |
| `JIRA_API_TOKEN`   | Yes      | Jira Cloud API token                                              |
| `JIRA_DOMAIN`      | Yes      | Jira domain, e.g. `company.atlassian.net`                         |
| `FLASK_SECRET_KEY` | No       | Secret used by Flask sessions; generated automatically if omitted |

`JIRA_DOMAIN` must contain only the hostname:

```env
JIRA_DOMAIN=company.atlassian.net
```

Not:

```env
JIRA_DOMAIN=https://company.atlassian.net
```

---

# Running with Docker

Docker Compose is the recommended way to run JiraExporter.

### Start the application

```bash
docker compose up --build
```

The application will be available at:

```text
http://localhost:5000
```

### Run in the background

```bash
docker compose up --build -d
```

### View logs

```bash
docker compose logs -f
```

### Stop the application

```bash
docker compose down
```

### Rebuild the image

If you changed the application code or dependencies:

```bash
docker compose up --build
```

To force a clean rebuild without using the Docker build cache:

```bash
docker compose build --no-cache
docker compose up
```

### Check running containers

```bash
docker compose ps
```

### Raspberry Pi

JiraExporter can be run on a Raspberry Pi 4 as long as the installed Docker image and its dependencies support your Pi's architecture.

Check the architecture with:

```bash
uname -m
```

Typical Raspberry Pi 4 installations using 64-bit Raspberry Pi OS will report:

```text
aarch64
```

Check Docker:

```bash
docker --version
docker compose version
```

If `docker compose` works, no separate `docker-compose` package is required.

---

# Running locally without Docker

Local Python execution is useful for development and debugging.

## 1. Create a virtual environment

```bash
python3 -m venv .venv
```

Activate it:

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows

```powershell
.venv\Scripts\activate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

If `python-dotenv` is not already included in `requirements.txt`, install it manually:

```bash
pip install python-dotenv
```

## 3. Configure `.env`

Make sure `.env` exists in the project root:

```bash
ls -la .env
```

## 4. Start the application

```bash
python app.py
```

The application will:

1. Load configuration from `.env`
2. Validate the required Jira configuration
3. Start the Flask server
4. Listen on:

```text
http://localhost:5000
```

---

# Usage

1. Open:

   ```text
   http://localhost:5000
   ```

2. Click **Connect to Jira**

3. Select a Jira project

4. Click **Export to Markdown**

5. The generated Markdown file will be downloaded

The exported file follows the naming convention:

```text
jira-[PROJECT_KEY].md
```

---

# Logging

JiraExporter uses centralized logging for application diagnostics.

### Console

Console logging provides general application activity at `INFO` level.

When running with Docker:

```bash
docker compose logs -f
```

### Log files

Detailed logs are written to:

```text
logs/[timestamp].log
```

Log files contain `DEBUG`-level information useful for troubleshooting.

Sensitive information such as API tokens and email addresses is automatically masked where applicable.

### Log rotation

Log files are rotated when they reach 10 MB.

Up to 5 backup files are retained.

### Inspect logs

```bash
ls -lt logs/
```

Follow the latest log file:

```bash
tail -f logs/[latest-timestamp].log
```

---

# Troubleshooting

## `docker-compose: command not found`

If you see:

```text
-bash: docker-compose: command not found
```

you are using the legacy Compose command.

Use Docker Compose v2 instead:

```bash
docker compose up --build
```

Notice the space between `docker` and `compose`.

Check whether Compose v2 is installed:

```bash
docker compose version
```

If it is not available, install the Docker Compose plugin using your operating system's Docker packages.

---

## `Missing required environment variables`

### Symptoms

The application reports missing values for:

* `JIRA_EMAIL`
* `JIRA_API_TOKEN`
* `JIRA_DOMAIN`

### Local Python installation

Make sure `.env` exists:

```bash
ls -la .env
```

Make sure `python-dotenv` is installed:

```bash
pip install python-dotenv
```

Then restart the application:

```bash
python app.py
```

### Docker

Restart the container:

```bash
docker compose down
docker compose up --build
```

### Verify `.env`

Correct:

```env
JIRA_EMAIL=user@example.com
JIRA_API_TOKEN=ATATT3xFfGF0...
JIRA_DOMAIN=company.atlassian.net
```

Avoid unnecessary spaces:

```env
JIRA_EMAIL = user@example.com
```

Do not include the Jira URL scheme:

```env
JIRA_DOMAIN=https://company.atlassian.net
```

The expected format is:

```env
JIRA_DOMAIN=company.atlassian.net
```

---

## Authentication fails with valid credentials

Possible causes include:

1. The API token was revoked or expired
2. The email does not match the Atlassian account
3. The Jira domain is incorrect
4. The Atlassian account does not have access to the requested Jira resources

Create a new API token if necessary:

[Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

Then update:

```env
JIRA_API_TOKEN=your-new-token
```

Restart the application.

---

## `410 Client Error: Gone` / Project is archived

Jira returns HTTP `410 Gone` when attempting to access certain archived projects.

### Possible solutions

1. Select an active project
2. Ask a Jira administrator to restore the archived project
3. Verify that the project is not archived in Jira

The project selector is intended to show active projects, so this error should normally not occur when selecting a project from the UI.

---

## No projects found

Possible causes:

* Your Jira account does not have access to any projects
* All accessible projects are archived
* Jira configuration is incorrect
* The API token belongs to a different Atlassian account

Verify that you can see the projects in Jira Cloud using the same Atlassian account.

If necessary, ask your Jira administrator to grant the required project permissions.

---

## Export fails or takes a long time

Large Jira projects can take a significant amount of time to export.

For projects with thousands of issues:

* Monitor the application logs
* Allow additional time for the export
* Check whether the browser connection has timed out while the backend is still processing the export

For example:

```bash
docker compose logs -f
```

The current implementation performs the export as a single blocking operation.

---

# Known limitations

## Session management

Authentication state is stored in Flask sessions.

Sessions are lost when the container is restarted.

This is acceptable for local or single-user usage, but the current implementation is not designed for a production multi-user deployment.

## Atlassian Document Format conversion

The ADF-to-Markdown converter supports common structures such as:

* Paragraphs
* Headings
* Lists
* Links
* Code blocks
* Blockquotes

Complex nested content and less common ADF node types may not be converted perfectly.

## Progress tracking

The progress bar in the UI is currently simulated on the frontend.

The actual backend export runs as one blocking operation and does not currently provide real-time progress updates.

For actual export progress, monitor the application logs.

## Large projects

Projects containing thousands of issues may take several minutes to export.

Very large exports may also exceed browser or reverse-proxy timeout limits.

A future implementation could use background jobs and asynchronous progress reporting.

---

# Architecture

The application consists of a Flask web application and a Jira API client.

Key design points:

* Jira credentials are provided through environment variables
* Jira API access is encapsulated in `JiraClient`
* Each API request creates a new `JiraClient` instance
* Projects are fetched using Jira's `/project/search` endpoint with pagination
* Issues are fetched with `ORDER BY key ASC`
* Deterministic ordering makes generated Markdown suitable for version control
* Flask sessions are used for authentication state
* Logging is centralized and supports sensitive-data masking

---

# Project structure

```text
JiraExporter/
├── static/
│   ├── script.js
│   └── styles.css
├── templates/
│   └── index.html
├── logs/
│   └── [generated log files]
├── .env
├── .env.example
├── app.py
├── docker-compose.yml
├── Dockerfile
├── jira_client.py
├── markdown_generator.py
├── README.md
└── requirements.txt
```

> `.env` and generated log files should not be committed to version control.

---

# Development

## Start a development environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Alternatively, use Docker:

```bash
docker compose up --build
```

## Adding real-time progress tracking

The current implementation performs exports synchronously.

Possible approaches for real-time progress reporting include:

* Server-Sent Events (SSE)
* WebSockets
* Background job processing
* Celery
* RQ

A background job architecture would be particularly useful for large Jira projects.

---

# Security considerations

* Never commit `.env` to Git
* Never expose your Jira API token in source code
* Never publish application logs containing unmasked credentials
* Use a strong, randomly generated `FLASK_SECRET_KEY` for deployments that persist sessions
* Restrict access to the application if it is exposed beyond the local machine
* Rotate the Jira API token if it is accidentally exposed

A production deployment should additionally use HTTPS and appropriate authentication/access controls.

---

# License

MIT

# Support

If you encounter a problem:

1. Check the **Troubleshooting** section
2. Check the application logs
3. Verify your Jira credentials and API token
4. Verify that your Jira account can access the relevant project
5. Check that Docker and Docker Compose are working:

```bash
docker --version
docker compose version
```

For Jira API token management:

[Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
