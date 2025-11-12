"""Logging utilities."""

import logging
import sys
import os
from typing import Optional


def setup_logger(
    name: str,
    level: str = "INFO",
    log_format: Optional[str] = None,
    log_file: Optional[str] = "logs/server.log"
) -> logging.Logger:
    """
    Setup a logger with both console + file output.

    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom log format string
        log_file: Path to log file

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers (avoid duplicate logs)
    logger.handlers.clear()

    if log_format is None:
        log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    formatter = logging.Formatter(log_format)

    # Console handler - CRITICAL: Use stderr for MCP protocol compatibility
    # MCP requires stdout to be PURE JSON-RPC messages only
    # All logging MUST go to stderr
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(getattr(logging, level.upper()))
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler (optional)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setLevel(getattr(logging, level.upper()))
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger
