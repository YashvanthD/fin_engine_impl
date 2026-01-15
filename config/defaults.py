"""Defaults configuration - loads and saves defaults from JSON files.

Simple file-based approach:
- JSON files in data/ are the source of truth
- GET: Loads from JSON file (with caching)
- PUT: Updates the JSON file

Files:
- data/default_permissions.json
- data/default_roles.json
- data/default_expense_categories.json
- data/default_feed_types.json
- data/default_settings.json
"""
import json
import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Data directory path
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

# Default file mappings
DEFAULT_FILES = {
    'permissions': 'default_permissions.json',
    'roles': 'default_roles.json',
    'expense_categories': 'default_expense_categories.json',
    'feed_types': 'default_feed_types.json',
    'settings': 'default_settings.json',
}


class DefaultsConfig:
    """Simple file-based defaults configuration."""

    _cache: Dict[str, Any] = {}

    @classmethod
    def _get_filepath(cls, key: str) -> Optional[str]:
        """Get file path for a default key."""
        filename = DEFAULT_FILES.get(key)
        if not filename:
            return None
        return os.path.join(DATA_DIR, filename)

    @classmethod
    def _load_from_file(cls, key: str) -> Optional[Any]:
        """Load default from JSON file."""
        filepath = cls._get_filepath(key)
        if not filepath or not os.path.exists(filepath):
            logger.warning(f'Default file not found: {filepath}')
            return None

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.exception(f'Error loading {filepath}: {e}')
            return None

    @classmethod
    def _save_to_file(cls, key: str, data: Any) -> bool:
        """Save default to JSON file."""
        filepath = cls._get_filepath(key)
        if not filepath:
            logger.warning(f'Unknown default key: {key}')
            return False

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Update cache
            cls._cache[key] = data
            return True
        except Exception as e:
            logger.exception(f'Error saving {filepath}: {e}')
            return False

    @classmethod
    def get(cls, key: str, use_cache: bool = True) -> Optional[Any]:
        """Get a default value from file.

        Args:
            key: Default key (permissions, roles, etc.)
            use_cache: Whether to use cached value

        Returns:
            Default data or None
        """
        # Check cache
        if use_cache and key in cls._cache:
            return cls._cache[key]

        # Load from file
        data = cls._load_from_file(key)

        # Cache the result
        if data is not None:
            cls._cache[key] = data

        return data

    @classmethod
    def set(cls, key: str, data: Any) -> bool:
        """Set a default value (saves to file).

        Args:
            key: Default key
            data: Data to save

        Returns:
            True if successful
        """
        return cls._save_to_file(key, data)

    @classmethod
    def reload(cls, key: str) -> Optional[Any]:
        """Reload a default from file (bypass cache)."""
        cls._cache.pop(key, None)
        return cls.get(key, use_cache=False)

    @classmethod
    def reload_all(cls) -> Dict[str, bool]:
        """Reload all defaults from files."""
        cls._cache.clear()
        results = {}
        for key in DEFAULT_FILES.keys():
            data = cls.get(key, use_cache=False)
            results[key] = data is not None
        return results

    @classmethod
    def clear_cache(cls):
        """Clear the defaults cache."""
        cls._cache.clear()

    @classmethod
    def list_keys(cls) -> List[str]:
        """List all available default keys."""
        return list(DEFAULT_FILES.keys())

    # =========================================================================
    # Convenience getters
    # =========================================================================

    @classmethod
    def get_permissions(cls) -> List[Dict]:
        """Get default permissions."""
        return cls.get('permissions') or []

    @classmethod
    def get_roles(cls) -> List[Dict]:
        """Get default roles."""
        return cls.get('roles') or []

    @classmethod
    def get_expense_categories(cls) -> List[Dict]:
        """Get default expense categories."""
        return cls.get('expense_categories') or []

    @classmethod
    def get_feed_types(cls) -> List[Dict]:
        """Get default feed types."""
        return cls.get('feed_types') or []

    @classmethod
    def get_settings(cls) -> Dict:
        """Get default settings."""
        return cls.get('settings') or {}

    # =========================================================================
    # Convenience setters
    # =========================================================================

    @classmethod
    def set_permissions(cls, data: List[Dict]) -> bool:
        """Set default permissions."""
        return cls.set('permissions', data)

    @classmethod
    def set_roles(cls, data: List[Dict]) -> bool:
        """Set default roles."""
        return cls.set('roles', data)

    @classmethod
    def set_expense_categories(cls, data: List[Dict]) -> bool:
        """Set default expense categories."""
        return cls.set('expense_categories', data)

    @classmethod
    def set_feed_types(cls, data: List[Dict]) -> bool:
        """Set default feed types."""
        return cls.set('feed_types', data)

    @classmethod
    def set_settings(cls, data: Dict) -> bool:
        """Set default settings."""
        return cls.set('settings', data)


# Export singleton-style access
defaults = DefaultsConfig

