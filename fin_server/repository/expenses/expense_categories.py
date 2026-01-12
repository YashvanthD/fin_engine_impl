"""Expense Category Repository for managing hierarchical expense categories.

This repository manages the expense categories from the expenses.json catalog
and provides methods to:
- Get category hierarchy
- Validate categories
- Get category path
- Search categories
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import json
import os
from functools import lru_cache

from fin_server.repository.base_repository import BaseRepository


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
EXPENSES_CATALOG_PATH = os.path.join(PROJECT_ROOT, 'data', 'expesnses.json')


@lru_cache(maxsize=1)
def load_expense_catalog() -> Dict[str, Any]:
    """Load the expense catalog from JSON file."""
    try:
        with open(EXPENSES_CATALOG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def flatten_categories(catalog: Dict[str, Any], prefix: str = '') -> List[Dict[str, Any]]:
    """Flatten the hierarchical catalog into a list of category objects with paths."""
    result = []
    for key, value in catalog.items():
        current_path = f"{prefix}/{key}" if prefix else key
        category_obj = {
            'name': key,
            'path': current_path,
            'level': current_path.count('/'),
            'has_children': bool(value) and isinstance(value, dict) and len(value) > 0
        }
        result.append(category_obj)

        if isinstance(value, dict) and value:
            result.extend(flatten_categories(value, current_path))

    return result


def get_top_level_categories() -> List[str]:
    """Get the top-level expense categories."""
    catalog = load_expense_catalog()
    return list(catalog.keys())


def get_subcategories(parent_path: str) -> List[Dict[str, Any]]:
    """Get subcategories for a given parent path."""
    catalog = load_expense_catalog()
    parts = parent_path.split('/') if parent_path else []

    # Navigate to the parent
    current = catalog
    for part in parts:
        if part and isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return []

    if not isinstance(current, dict):
        return []

    return [
        {
            'name': key,
            'path': f"{parent_path}/{key}" if parent_path else key,
            'has_children': bool(value) and isinstance(value, dict) and len(value) > 0
        }
        for key, value in current.items()
    ]


def validate_category_path(path: str) -> Tuple[bool, Optional[str]]:
    """Validate if a category path exists in the catalog.

    Returns (is_valid, error_message)
    """
    if not path:
        return False, "Category path is required"

    catalog = load_expense_catalog()
    parts = path.split('/')

    current = catalog
    for i, part in enumerate(parts):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            return False, f"Invalid category at level {i+1}: '{part}'"
        current = current[part]

    return True, None


def search_categories(query: str) -> List[Dict[str, Any]]:
    """Search categories by name (case-insensitive partial match)."""
    catalog = load_expense_catalog()
    all_categories = flatten_categories(catalog)
    query_lower = query.lower()

    return [
        cat for cat in all_categories
        if query_lower in cat['name'].lower()
    ]


def get_category_suggestions(partial: str, limit: int = 10) -> List[str]:
    """Get category path suggestions based on partial input."""
    catalog = load_expense_catalog()
    all_categories = flatten_categories(catalog)
    partial_lower = partial.lower()

    matches = [
        cat['path'] for cat in all_categories
        if partial_lower in cat['path'].lower()
    ]

    return sorted(matches, key=len)[:limit]


class ExpenseCategoryRepository(BaseRepository):
    """Repository for expense categories stored in MongoDB.

    This allows custom categories to be added per account while
    still using the base catalog as a reference.
    """
    _instance = None

    def __new__(cls, db=None, collection_name="expense_categories"):
        if cls._instance is None:
            cls._instance = super(ExpenseCategoryRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db=None, collection_name="expense_categories"):
        if not getattr(self, "_initialized", False):
            if db is not None:
                super().__init__(db=db, collection_name=collection_name)
                self.collection_name = collection_name
                try:
                    self.collection.create_index([('account_key', 1), ('path', 1)], name='category_account_path', unique=True)
                    self.collection.create_index([('account_key', 1), ('name', 1)], name='category_account_name')
                except Exception:
                    pass
            self._initialized = True

    def get_catalog(self) -> Dict[str, Any]:
        """Get the base expense catalog."""
        return load_expense_catalog()

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """Get all categories flattened."""
        return flatten_categories(self.get_catalog())

    def get_top_level(self) -> List[str]:
        """Get top-level categories."""
        return get_top_level_categories()

    def get_subcategories(self, parent_path: str) -> List[Dict[str, Any]]:
        """Get subcategories for a parent."""
        return get_subcategories(parent_path)

    def validate_path(self, path: str) -> Tuple[bool, Optional[str]]:
        """Validate a category path."""
        return validate_category_path(path)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search categories."""
        return search_categories(query)

    def suggest(self, partial: str, limit: int = 10) -> List[str]:
        """Get category suggestions."""
        return get_category_suggestions(partial, limit)

    def add_custom_category(self, account_key: str, name: str, parent_path: str = None, metadata: Dict = None) -> Any:
        """Add a custom category for an account."""
        path = f"{parent_path}/{name}" if parent_path else name
        doc = {
            'account_key': account_key,
            'name': name,
            'path': path,
            'parent_path': parent_path,
            'is_custom': True,
            'metadata': metadata or {},
            'created_at': datetime.now(timezone.utc)
        }
        return self.collection.insert_one(doc)

    def get_account_categories(self, account_key: str) -> List[Dict[str, Any]]:
        """Get all categories (base + custom) for an account."""
        base_categories = self.get_all_categories()

        # Add custom categories from DB
        try:
            custom = list(self.collection.find({'account_key': account_key}))
            for c in custom:
                c['_id'] = str(c.get('_id'))
                base_categories.append({
                    'name': c.get('name'),
                    'path': c.get('path'),
                    'level': c.get('path', '').count('/'),
                    'has_children': False,
                    'is_custom': True
                })
        except Exception:
            pass

        return base_categories


# Module-level helper functions for use without repository instance
def get_expense_category_options() -> Dict[str, List[str]]:
    """Get expense category options for forms/dropdowns.

    Returns a dict with top-level categories as keys and their
    immediate children as values.
    """
    catalog = load_expense_catalog()
    options = {}

    for top_key, top_value in catalog.items():
        if isinstance(top_value, dict):
            options[top_key] = list(top_value.keys())
        else:
            options[top_key] = []

    return options


def normalize_expense_category(category: str, subcategory: str = None, detail: str = None) -> Dict[str, str]:
    """Normalize expense category fields and build the full path.

    Returns a dict with:
    - category: Top-level category
    - subcategory: Second-level category
    - detail: Third-level detail
    - path: Full path string
    """
    result = {
        'category': category,
        'subcategory': subcategory,
        'detail': detail,
        'path': category
    }

    if subcategory:
        result['path'] = f"{category}/{subcategory}"
        if detail:
            result['path'] = f"{category}/{subcategory}/{detail}"

    return result

