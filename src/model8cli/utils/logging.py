"""
Logging utilities for 200Model8CLI
"""
import structlog

def get_logger(name: str):
    """Get a structured logger instance"""
    return structlog.get_logger(name)
