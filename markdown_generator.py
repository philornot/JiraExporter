"""
Markdown file generator for Jira exports.

This module handles the generation of formatted Markdown files from
processed Jira issue data.
"""

from typing import List, Dict, Any
from datetime import datetime


class MarkdownGenerator:
    """
    Generator for creating Markdown files from Jira data.

    This class takes processed Jira issues and generates a well-formatted
    Markdown document suitable for offline viewing and version control.
    """

    def generate(self, project_name: str, issues: List[Dict[str, Any]]) -> str:
        """
        Generate a complete Markdown document from project issues.

        Args:
            project_name (str): Name of the Jira project.
            issues (List[Dict[str, Any]]): List of processed issues.

        Returns:
            str: Complete Markdown document as a string.
        """
        lines = []

        # Add header
        lines.append(f"# {project_name}")
        lines.append("")
        lines.append(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Issues: {len(issues)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Add each issue
        for issue in issues:
            lines.extend(self._format_issue(issue))
            lines.append("")

        return '\n'.join(lines)

    def _format_issue(self, issue: Dict[str, Any]) -> List[str]:
        """
        Format a single issue as Markdown.

        Args:
            issue (Dict[str, Any]): Processed issue data.

        Returns:
            List[str]: List of lines representing the formatted issue.
        """
        lines = []

        # Issue header
        lines.append(f"## {issue['key']}: {issue['summary']}")
        lines.append("")

        # Status
        if issue.get('status'):
            lines.append(f"**Status:** {issue['status']}")
            lines.append("")

        # Parent information
        if issue.get('parent'):
            parent = issue['parent']
            lines.append(f"**Parent:** {parent['key']} - {parent['summary']}")
            lines.append("")

        # Description
        if issue.get('description'):
            lines.append("**Description:**")
            lines.append("")
            lines.append(issue['description'])
            lines.append("")

        lines.append("---")

        return lines