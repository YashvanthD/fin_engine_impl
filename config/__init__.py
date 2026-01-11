"""Configuration module for the application.

Supports multiple environments:
- development (default)
- staging
- production

Usage:
    from config import config

    # Access config values
    debug = config.DEBUG
    mongo_uri = config.MONGO_URI

    # Check environment
    if config.IS_DEV:
        print("Running in development mode")

Set environment via:
- FLASK_ENV=production
- APP_ENV=staging
"""
from .settings import config, Config, is_dev, is_prod, get_env

__all__ = ['config', 'Config', 'is_dev', 'is_prod', 'get_env']

