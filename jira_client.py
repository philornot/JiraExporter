"""
Jira Cloud REST API client.

This module handles all interactions with the Jira Cloud REST API,
including authentication, project listing, and issue retrieval with
pagination support.

Note: The ADF to Markdown converter is a proof-of-concept implementation
that handles common structures but may not perfectly render all ADF content.

Updated to use /rest/api/3/search/jql endpoint (the old /rest/api/3/search
was deprecated and removed in May 2025).
"""

import logging
from typing import List, Dict, Any, Optional

import requests
from requests.auth import HTTPBasicAuth


class JiraClient:
    """Client for interacting with Jira Cloud REST API.

    Provides methods for authenticating with Jira Cloud, retrieving
    projects, and fetching issues with automatic pagination using the
    ``/search/jql`` endpoint.
    """

    def __init__(
            self,
            domain: str,
            email: str,
            api_token: str,
            logger: Optional[logging.Logger] = None,
    ):
        """Initialize the Jira client.

        Args:
            domain (str): Jira Cloud domain (e.g., yourcompany.atlassian.net).
            email (str): User email address for authentication.
            api_token (str): Atlassian API token for authentication.
            logger (Optional[logging.Logger]): Logger instance for debugging.
        """
        self.base_url = f"https://{domain}/rest/api/3"
        self.auth = HTTPBasicAuth(email, api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.logger = logger or logging.getLogger(__name__)

    def test_connection(self) -> bool:
        """Test the connection to Jira Cloud.

        Returns:
            bool: True if connection is successful.

        Raises:
            Exception: If authentication fails or connection cannot be established.
        """
        url = f"{self.base_url}/myself"
        self.logger.debug(f"Testing connection to {self.base_url}")

        response = requests.get(url, auth=self.auth, headers=self.headers)

        if response.status_code != 200:
            self.logger.error(f"Authentication failed: {response.status_code}")
            raise Exception(f"Authentication failed with status {response.status_code}")

        self.logger.debug("Connection test successful")
        return True

    def get_all_projects(self) -> List[Dict[str, str]]:
        """Retrieve all accessible Jira projects with pagination.

        Only returns active (non-archived) projects.

        Returns:
            List[Dict[str, str]]: List of projects, each with ``key`` and
                ``name`` fields.
        """
        all_projects = []
        start_at = 0
        max_results = 50

        self.logger.debug("Starting project retrieval with pagination")

        while True:
            url = f"{self.base_url}/project/search"
            params = {
                'startAt': start_at,
                'maxResults': max_results,
                'status': 'live',
            }

            self.logger.debug(f"Fetching projects: startAt={start_at}, maxResults={max_results}")

            response = requests.get(url, auth=self.auth, headers=self.headers, params=params)
            response.raise_for_status()

            data = response.json()
            projects = data.get('values', [])

            if not projects:
                break

            for project in projects:
                all_projects.append({'key': project['key'], 'name': project['name']})

            self.logger.debug(f"Retrieved {len(projects)} projects in this batch")

            if data.get('isLast', True):
                break

            start_at += max_results

        self.logger.info(f"Total projects retrieved: {len(all_projects)}")
        return all_projects

    def get_project_name(self, project_key: str) -> str:
        """Get the name of a specific project.

        Args:
            project_key (str): The project key (e.g., 'PROJ').

        Returns:
            str: The project name.

        Raises:
            Exception: If the project is not found, inaccessible, or archived.
        """
        url = f"{self.base_url}/project/{project_key}"
        self.logger.debug(f"Fetching project details for {project_key}")

        response = requests.get(url, auth=self.auth, headers=self.headers)

        if response.status_code == 404:
            self.logger.error(f"Project {project_key} not found")
            raise Exception(
                f"We couldn't find project '{project_key}' — it may have been deleted "
                "or you may not have access to it."
            )

        response.raise_for_status()

        project_data = response.json()

        if project_data.get('archived', False):
            self.logger.warning(f"Project {project_key} is archived")
            raise Exception(
                f"Project '{project_key}' is archived. Archived projects are read-only "
                "and cannot be exported via the API. Please choose an active project or "
                "ask your Jira admin to restore it."
            )

        return project_data['name']

    def get_issue_count(self, project_key: str) -> int:
        """Get the total number of issues in a project without fetching them.

        Uses a JQL query with ``maxResults=0`` to retrieve only the total
        count. Fast even for very large projects (single API call, no issue
        data transferred).

        Args:
            project_key (str): The project key (e.g., 'PROJ').

        Returns:
            int: Total number of issues in the project.
        """
        url = f"{self.base_url}/search/jql"
        payload = {
            "jql": f"project={project_key}",
            "maxResults": 0,
        }

        self.logger.debug(f"Fetching issue count for {project_key}")
        response = requests.post(url, auth=self.auth, headers=self.headers, json=payload)
        response.raise_for_status()

        total = response.json().get('total', 0)
        self.logger.info(f"Project {project_key} has {total} issues")
        return total

    def get_all_issues(self, project_key: str) -> List[Dict[str, Any]]:
        """Retrieve all issues for a given project with pagination.

        Args:
            project_key (str): The project key to fetch issues from.

        Returns:
            List[Dict[str, Any]]: All issues with processed fields, ordered
                by issue key.
        """
        return self._fetch_issues_by_jql(
            jql=f"project={project_key} ORDER BY key ASC"
        )

    def get_issues_in_key_range(
            self,
            project_key: str,
            key_from: int,
            key_to: int,
    ) -> List[Dict[str, Any]]:
        """Retrieve issues within a specific key-number range for a project.

        The range is inclusive on both ends.

        Args:
            project_key (str): The project key (e.g., 'PROJ').
            key_from (int): First issue number to include (e.g., 1 for PROJ-1).
            key_to (int): Last issue number to include (e.g., 200 for PROJ-200).

        Returns:
            List[Dict[str, Any]]: Processed issues within the range, ordered
                by key.
        """
        jql = (
            f"project={project_key} "
            f"AND issuekey >= {project_key}-{key_from} "
            f"AND issuekey <= {project_key}-{key_to} "
            f"ORDER BY key ASC"
        )
        self.logger.info(
            f"Fetching issues for {project_key} in range "
            f"{project_key}-{key_from} to {project_key}-{key_to}"
        )
        return self._fetch_issues_by_jql(jql=jql)

    def _fetch_issues_by_jql(self, jql: str) -> List[Dict[str, Any]]:
        """Fetch all issues matching a JQL query, handling pagination automatically.

        Uses ``nextPageToken``-based pagination. The loop continues until the
        token is absent from the response — this is the authoritative
        end-of-results signal. ``isLast`` is checked as a secondary guard.

        Args:
            jql (str): A valid JQL query string.

        Returns:
            List[Dict[str, Any]]: All matching issues as processed dicts.
        """
        all_issues = []
        next_page_token = None
        page_count = 0
        max_results = 100
        url = f"{self.base_url}/search/jql"

        while True:
            page_count += 1

            payload = {
                "jql": jql,
                "maxResults": max_results,
                "fields": ["summary", "description", "status", "parent"],
            }

            if next_page_token:
                payload["nextPageToken"] = next_page_token

            self.logger.debug(f"Fetching page {page_count} (nextPageToken={next_page_token!r})")

            response = requests.post(url, auth=self.auth, headers=self.headers, json=payload)

            if response.status_code == 404:
                self.logger.error("Search endpoint not found - API might have changed")
                raise Exception(
                    "Search API endpoint not found. "
                    "Please check that you're using the latest version of the application."
                )

            response.raise_for_status()

            data = response.json()
            issues = data.get('issues', [])
            total = data.get('total', 0)

            if not issues:
                self.logger.debug("No issues returned - reached end of results")
                break

            self.logger.debug(
                f"Page {page_count}: got {len(issues)} issues "
                f"(total so far: {len(all_issues) + len(issues)}/{total})"
            )

            for issue in issues:
                all_issues.append(self._process_issue(issue))

            # Primary stop condition: absence of nextPageToken is authoritative.
            # isLast is NOT the primary check — /search/jql doesn't always return it.
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                self.logger.debug("No nextPageToken in response - reached last page")
                break

            if data.get('isLast', False):
                self.logger.debug("isLast=True received from API")
                break

            # Safety stop: prevent infinite loops (max 1 000 pages = 100 000 issues).
            if page_count >= 1000:
                self.logger.warning(
                    f"Reached maximum page limit ({page_count} pages). "
                    f"Stopping with {len(all_issues)}/{total} issues fetched."
                )
                break

        self.logger.info(f"Total issues retrieved: {len(all_issues)}")
        return all_issues

    def _process_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Process a raw Jira API issue into a simplified dict.

        Args:
            issue (Dict[str, Any]): Raw issue data from Jira API.

        Returns:
            Dict[str, Any]: Processed issue with key fields extracted.
        """
        fields = issue['fields']

        processed = {
            'key': issue['key'],
            'summary': fields.get('summary', ''),
            'status': fields.get('status', {}).get('name', ''),
            'description': self._convert_adf_to_markdown(fields.get('description')),
            'parent': None,
        }

        if 'parent' in fields and fields['parent']:
            processed['parent'] = {
                'key': fields['parent']['key'],
                'summary': fields['parent']['fields'].get('summary', ''),
            }

        return processed

    def _convert_adf_to_markdown(self, adf_content: Optional[Dict[str, Any]]) -> str:
        """Convert Atlassian Document Format (ADF) content to Markdown.

        Args:
            adf_content (Optional[Dict[str, Any]]): ADF content object or None.

        Returns:
            str: Converted Markdown text, or empty string for empty input.
        """
        if not adf_content:
            return ''
        return self._process_adf_node(adf_content).strip()

    def _process_adf_node(
            self,
            node: Dict[str, Any],
            level: int = 0,
            list_index: Optional[int] = None,
    ) -> str:
        """Process a single ADF node recursively into Markdown.

        Handles all common ADF node types. Unknown node types degrade
        gracefully by recursing into their children so that text content
        is never silently lost (JE-28 catch-all fix).

        Args:
            node (Dict[str, Any]): ADF node to process.
            level (int): Current nesting level for indentation.
            list_index (Optional[int]): 1-based index for ordered list items,
                or None for bullet list items.

        Returns:
            str: Markdown representation of the node.
        """
        if not isinstance(node, dict):
            return ''

        node_type = node.get('type', '')
        content = node.get('content', [])
        text = node.get('text', '')
        attrs = node.get('attrs', {})

        result = []

        # ------------------------------------------------------------------ #
        # Block-level nodes                                                    #
        # ------------------------------------------------------------------ #

        if node_type == 'doc':
            for child in content:
                result.append(self._process_adf_node(child, level))

        elif node_type == 'paragraph':
            paragraph_text = ''.join(
                self._process_adf_node(child, level) for child in content
            )
            if paragraph_text.strip():
                result.append(paragraph_text + '\n\n')

        elif node_type == 'heading':
            heading_level = attrs.get('level', 1)
            heading_text = ''.join(
                self._process_adf_node(child, level) for child in content
            )
            result.append(f"{'#' * heading_level} {heading_text}\n\n")

        elif node_type == 'bulletList':
            for child in content:
                result.append(self._process_adf_node(child, level))
            result.append('\n')

        elif node_type == 'orderedList':
            for idx, child in enumerate(content, 1):
                result.append(self._process_adf_node(child, level, idx))
            result.append('\n')

        elif node_type == 'listItem':
            indent = '  ' * level
            item_parts = []
            for child in content:
                child_text = self._process_adf_node(child, level + 1)
                if child_text.strip():
                    item_parts.append(child_text.strip())
            item_text = ' '.join(item_parts)
            if list_index is not None:
                result.append(f"{indent}{list_index}. {item_text}\n")
            else:
                result.append(f"{indent}- {item_text}\n")

        elif node_type == 'codeBlock':
            code_text = ''.join(child.get('text', '') for child in content)
            language = attrs.get('language', '')
            result.append(f"```{language}\n{code_text}\n```\n\n")

        elif node_type == 'blockquote':
            quote_text = ''.join(
                self._process_adf_node(child, level) for child in content
            )
            quoted_lines = ['> ' + line for line in quote_text.split('\n') if line.strip()]
            result.append('\n'.join(quoted_lines) + '\n\n')

        elif node_type == 'rule':
            result.append('---\n\n')

        elif node_type == 'hardBreak':
            result.append('  \n')

        # ------------------------------------------------------------------ #
        # JE-21: Table support (GFM-style)                                    #
        # ------------------------------------------------------------------ #

        elif node_type == 'table':
            result.append(self._process_table_node(node))

        elif node_type in ('tableRow', 'tableCell', 'tableHeader'):
            # Should be reached only through _process_table_node, but handle
            # gracefully if called standalone.
            for child in content:
                result.append(self._process_adf_node(child, level))

        # ------------------------------------------------------------------ #
        # JE-21: Inline nodes                                                 #
        # ------------------------------------------------------------------ #

        elif node_type == 'text':
            marks = node.get('marks', [])
            formatted_text = text
            for mark in marks:
                mark_type = mark.get('type')
                if mark_type == 'strong':
                    formatted_text = f"**{formatted_text}**"
                elif mark_type == 'em':
                    formatted_text = f"*{formatted_text}*"
                elif mark_type == 'code':
                    formatted_text = f"`{formatted_text}`"
                elif mark_type == 'link':
                    href = mark.get('attrs', {}).get('href', '')
                    formatted_text = f"[{formatted_text}]({href})"
                elif mark_type == 'strike':
                    formatted_text = f"~~{formatted_text}~~"
            result.append(formatted_text)

        elif node_type == 'mention':
            # Jira mentions carry a display name in attrs.
            display_name = attrs.get('text', attrs.get('displayName', 'unknown'))
            result.append(f"@{display_name}")

        elif node_type == 'emoji':
            # attrs.shortName is ":smile:" style; attrs.text is the actual
            # Unicode character when available.
            emoji_char = attrs.get('text') or attrs.get('shortName', '')
            result.append(emoji_char)

        elif node_type in ('inlineCard', 'blockCard'):
            url = attrs.get('url', '')
            result.append(f"[{url}]({url})")

        # ------------------------------------------------------------------ #
        # JE-21: Media                                                        #
        # ------------------------------------------------------------------ #

        elif node_type in ('mediaSingle', 'media'):
            result.append("<!-- media attachment -->\n\n")

        # ------------------------------------------------------------------ #
        # JE-21: Expand / nestedExpand → <details>                           #
        # ------------------------------------------------------------------ #

        elif node_type in ('expand', 'nestedExpand'):
            title = attrs.get('title', 'Details')
            inner = ''.join(self._process_adf_node(child, level) for child in content)
            result.append(f"<details>\n<summary>{title}</summary>\n\n{inner}\n</details>\n\n")

        # ------------------------------------------------------------------ #
        # JE-28: Catch-all — recurse into children so text is never lost     #
        # ------------------------------------------------------------------ #

        else:
            if node_type:
                self.logger.debug(f"Unknown ADF node type '{node_type}' — recursing into children")
            for child in content:
                result.append(self._process_adf_node(child, level))

        return ''.join(result)

    def _process_table_node(self, table_node: Dict[str, Any]) -> str:
        """Convert an ADF table node to a GitHub-Flavored Markdown table.

        The first row of the table is always treated as the header row,
        regardless of whether the cells use ``tableHeader`` or ``tableCell``
        nodes, because GFM requires exactly one header row.

        Args:
            table_node (Dict[str, Any]): The ADF ``table`` node.

        Returns:
            str: GFM table string including a trailing blank line.
        """
        rows = table_node.get('content', [])
        if not rows:
            return ''

        md_rows: List[List[str]] = []

        for row in rows:
            cells = []
            for cell in row.get('content', []):
                cell_text = ''.join(
                    self._process_adf_node(child) for child in cell.get('content', [])
                ).strip().replace('\n', ' ')
                cells.append(cell_text)
            md_rows.append(cells)

        if not md_rows:
            return ''

        # Normalize column count across all rows.
        col_count = max(len(r) for r in md_rows)
        for row in md_rows:
            while len(row) < col_count:
                row.append('')

        # Header row + separator row
        lines = ['| ' + ' | '.join(md_rows[0]) + ' |', '| ' + ' | '.join(['---'] * col_count) + ' |']
        # Data rows
        for row in md_rows[1:]:
            lines.append('| ' + ' | '.join(row) + ' |')

        return '\n'.join(lines) + '\n\n'
