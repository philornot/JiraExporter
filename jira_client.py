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

import requests
from requests.auth import HTTPBasicAuth
from typing import List, Dict, Any, Optional
import logging


class JiraClient:
    """
    Client for interacting with Jira Cloud REST API.

    This class provides methods for authenticating with Jira Cloud,
    retrieving projects, and fetching issues with automatic pagination
    using the new /search/jql endpoint.
    """

    def __init__(self, domain: str, email: str, api_token: str, logger: Optional[logging.Logger] = None):
        """
        Initialize the Jira client.

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
            "Content-Type": "application/json"
        }
        self.logger = logger or logging.getLogger(__name__)

    def test_connection(self) -> bool:
        """
        Test the connection to Jira Cloud.

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
        """
        Retrieve all accessible Jira projects with pagination.

        This method handles pagination to ensure all projects are retrieved,
        which is important for large Jira instances. Only returns active
        (non-archived) projects.

        Returns:
            List[Dict[str, str]]: List of projects with key and name.
                Each project is a dict with 'key' and 'name' fields.
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
                'status': 'live'  # Only fetch non-archived projects
            }

            self.logger.debug(f"Fetching projects: startAt={start_at}, maxResults={max_results}")

            response = requests.get(
                url,
                auth=self.auth,
                headers=self.headers,
                params=params
            )
            response.raise_for_status()

            data = response.json()
            projects = data.get('values', [])

            if not projects:
                self.logger.debug("No more projects to fetch")
                break

            for project in projects:
                all_projects.append({
                    'key': project['key'],
                    'name': project['name']
                })

            self.logger.debug(f"Retrieved {len(projects)} projects in this batch")

            # Check if we've retrieved all projects
            if data.get('isLast', True):
                break

            start_at += max_results

        self.logger.info(f"Total projects retrieved: {len(all_projects)}")
        return all_projects

    def get_project_name(self, project_key: str) -> str:
        """
        Get the name of a specific project.

        Args:
            project_key (str): The project key (e.g., 'PROJ').

        Returns:
            str: The project name.

        Raises:
            requests.exceptions.HTTPError: If project doesn't exist or is archived.
        """
        url = f"{self.base_url}/project/{project_key}"
        self.logger.debug(f"Fetching project details for {project_key}")

        response = requests.get(url, auth=self.auth, headers=self.headers)

        if response.status_code == 404:
            self.logger.error(f"Project {project_key} not found")
            raise Exception(
                f"Project '{project_key}' not found. It may have been deleted or you don't have access to it.")

        response.raise_for_status()

        project_data = response.json()

        # Check if project is archived
        if project_data.get('archived', False):
            self.logger.warning(f"Project {project_key} is archived")
            raise Exception(
                f"Project '{project_key}' is archived and cannot be exported. Please choose an active project.")

        return project_data['name']

    def get_issue_count(self, project_key: str) -> int:
        """
        Get the total number of issues in a project without fetching them all.

        Uses a JQL query with maxResults=0 to retrieve only the total count,
        which is fast even for very large projects.

        Args:
            project_key (str): The project key (e.g., 'PROJ').

        Returns:
            int: Total number of issues in the project.
        """
        url = f"{self.base_url}/search/jql"
        payload = {
            "jql": f"project={project_key} ORDER BY key ASC",
            "maxResults": 0,
            "fields": []
        }

        self.logger.debug(f"Fetching issue count for {project_key}")
        response = requests.post(url, auth=self.auth, headers=self.headers, json=payload)
        response.raise_for_status()

        total = response.json().get('total', 0)
        self.logger.info(f"Project {project_key} has {total} issues")
        return total

    def get_all_issues(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Retrieve all issues for a given project with pagination.

        This method uses the /rest/api/3/search/jql endpoint with
        nextPageToken-based pagination. Issues are ordered by key for
        deterministic output suitable for version control.

        Args:
            project_key (str): The project key to fetch issues from.

        Returns:
            List[Dict[str, Any]]: List of all issues with processed fields,
                ordered by issue key.
        """
        return self._fetch_issues_by_jql(
            jql=f"project={project_key} ORDER BY key ASC"
        )

    def get_issues_in_key_range(
            self,
            project_key: str,
            key_from: int,
            key_to: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve issues within a specific key-number range for a project.

        Useful for exporting a subset of a large project without fetching
        every issue. The range is inclusive on both ends.

        Args:
            project_key (str): The project key (e.g., 'PROJ').
            key_from (int): First issue number to include (e.g., 1 for PROJ-1).
            key_to (int): Last issue number to include (e.g., 200 for PROJ-200).

        Returns:
            List[Dict[str, Any]]: List of processed issues within the range,
                ordered by key.
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
        """
        Fetch all issues matching a JQL query, handling pagination automatically.

        Uses nextPageToken-based pagination introduced with the /search/jql
        endpoint. The loop continues until there is no nextPageToken in the
        response — this is the authoritative end-of-results signal, because
        the isLast field is not always returned by the API.

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
                "fields": ["summary", "description", "status", "parent"]
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

            # Primary stop condition: absence of nextPageToken is the authoritative
            # signal that there are no more pages. isLast is NOT used as the primary
            # check because the /search/jql endpoint does not always return it,
            # and defaulting it to True caused the original pagination bug where
            # only the first 100 issues were ever returned.
            next_page_token = data.get('nextPageToken')
            if not next_page_token:
                self.logger.debug("No nextPageToken in response - reached last page")
                break

            # Secondary stop: explicit isLast=True from the API
            if data.get('isLast', False):
                self.logger.debug("isLast=True received from API")
                break

            # Safety stop: prevent infinite loops (max 1 000 pages = 100 000 issues)
            if page_count >= 1000:
                self.logger.warning(
                    f"Reached maximum page limit ({page_count} pages). "
                    f"Stopping with {len(all_issues)}/{total} issues fetched."
                )
                break

        self.logger.info(f"Total issues retrieved: {len(all_issues)}")
        return all_issues

    def _process_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a raw issue from Jira API into a simplified format.

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
            'description': self._convert_adf_to_markdown(
                fields.get('description')
            ),
            'parent': None
        }

        # Extract parent information if it exists
        if 'parent' in fields and fields['parent']:
            processed['parent'] = {
                'key': fields['parent']['key'],
                'summary': fields['parent']['fields'].get('summary', '')
            }

        return processed

    def _convert_adf_to_markdown(self, adf_content: Optional[Dict[str, Any]]) -> str:
        """
        Convert Atlassian Document Format to Markdown.

        This is a proof-of-concept converter that handles common ADF structures
        like paragraphs, headings, lists, and links. It may not perfectly render
        all ADF content, especially complex nested structures.

        Args:
            adf_content (Optional[Dict[str, Any]]): ADF content object or None.

        Returns:
            str: Converted Markdown text.
        """
        if not adf_content:
            return ''

        return self._process_adf_node(adf_content).strip()

    def _process_adf_node(
            self,
            node: Dict[str, Any],
            level: int = 0,
            list_index: Optional[int] = None
    ) -> str:
        """
        Process a single ADF node recursively.

        Args:
            node (Dict[str, Any]): ADF node to process.
            level (int): Current nesting level for indentation.
            list_index (Optional[int]): Index for ordered list items.

        Returns:
            str: Markdown representation of the node.
        """
        if not isinstance(node, dict):
            return ''

        node_type = node.get('type', '')
        content = node.get('content', [])
        text = node.get('text', '')

        result = []

        if node_type == 'doc':
            for child in content:
                result.append(self._process_adf_node(child, level))

        elif node_type == 'paragraph':
            paragraph_text = ''.join([
                self._process_adf_node(child, level) for child in content
            ])
            if paragraph_text.strip():
                result.append(paragraph_text + '\n\n')

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

        elif node_type == 'heading':
            heading_level = node.get('attrs', {}).get('level', 1)
            heading_text = ''.join([
                self._process_adf_node(child, level) for child in content
            ])
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
            code_text = ''.join([
                child.get('text', '') for child in content
            ])
            language = node.get('attrs', {}).get('language', '')
            result.append(f"```{language}\n{code_text}\n```\n\n")

        elif node_type == 'blockquote':
            quote_text = ''.join([
                self._process_adf_node(child, level) for child in content
            ])
            quoted_lines = ['> ' + line for line in quote_text.split('\n') if line.strip()]
            result.append('\n'.join(quoted_lines) + '\n\n')

        elif node_type == 'hardBreak':
            result.append('  \n')

        elif node_type == 'rule':
            result.append('---\n\n')

        return ''.join(result)
