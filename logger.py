"""
Centralized logging configuration for JiraExporter.

This module provides a configured logger that writes to both console
and rotating log files with proper formatting and security measures.
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logger(name='jira_exporter'):
    """
    Set up and configure the application logger.

    Creates a logger that writes to both console and file, with rotation
    to prevent log files from growing too large. All sensitive data is
    automatically masked.

    Args:
        name (str): Name of the logger.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Create logs directory if it doesn't exist
    logs_dir = 'logs'
    os.makedirs(logs_dir, exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler - INFO level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler - DEBUG level with rotation
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(logs_dir, f'{timestamp}.log')

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Log startup info (without sensitive data)
    logger.info('=' * 60)
    logger.info('JiraExporter Logger Initialized')
    logger.info(f'Log file: {log_file}')
    logger.info('=' * 60)

    return logger


def mask_sensitive_data(data, show_chars=4):
    """
    Mask sensitive data for safe logging.

    Args:
        data (str): Sensitive data to mask.
        show_chars (int): Number of characters to show at the end.

    Returns:
        str: Masked string (e.g., "***AB8")
    """
    if not data:
        return '<empty>'

    if len(data) <= show_chars:
        return '*' * len(data)

    return '*' * (len(data) - show_chars) + data[-show_chars:]


def log_config_status(logger, email, token, domain):
    """
    Log configuration status without exposing sensitive data.

    Args:
        logger (logging.Logger): Logger instance.
        email (str): Email address.
        token (str): API token.
        domain (str): Jira domain.
    """
    logger.info('Configuration Status:')
    logger.info(f'  JIRA_EMAIL: {"✓ Set" if email else "✗ Missing"}')
    if email:
        # Only show domain part of email
        email_parts = email.split('@')
        if len(email_parts) == 2:
            masked_email = f"{email_parts[0][0]}***@{email_parts[1]}"
        else:
            masked_email = mask_sensitive_data(email)
        logger.info(f'    Value: {masked_email}')

    logger.info(f'  JIRA_API_TOKEN: {"✓ Set" if token else "✗ Missing"}')
    if token:
        logger.info(f'    Length: {len(token)} characters')
        logger.info(f'    Preview: {mask_sensitive_data(token, 4)}')

    logger.info(f'  JIRA_DOMAIN: {"✓ Set" if domain else "✗ Missing"}')
    if domain:
        logger.info(f'    Value: {domain}')


# Create default logger instance
default_logger = setup_logger()