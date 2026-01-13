"""Version control utilities for optimistic locking.

This module provides utilities for implementing optimistic locking
using version fields (_v) on high-write collections like:
- ponds (metadata.total_fish updates)
- bank_accounts (balance updates)
- fish (current_stock updates)

Usage:
    from fin_server.utils.versioning import (
        increment_version,
        versioned_update,
        add_version_to_doc,
        VERSION_FIELD
    )
"""
from typing import Any, Dict, Optional
from datetime import datetime, timezone


VERSION_FIELD = '_v'


def add_version_to_doc(doc: Dict[str, Any], initial_version: int = 1) -> Dict[str, Any]:
    """Add version field to a document if not present.

    Args:
        doc: Document to add version to
        initial_version: Starting version number (default: 1)

    Returns:
        Document with version field added
    """
    if VERSION_FIELD not in doc:
        doc[VERSION_FIELD] = initial_version
    return doc


def increment_version(update_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Add version increment to an update document.

    Args:
        update_doc: MongoDB update document (with $set, $inc, etc.)

    Returns:
        Update document with version increment added
    """
    if '$inc' not in update_doc:
        update_doc['$inc'] = {}
    update_doc['$inc'][VERSION_FIELD] = 1
    return update_doc


def versioned_update(
    collection,
    query: Dict[str, Any],
    update_doc: Dict[str, Any],
    expected_version: Optional[int] = None
) -> Dict[str, Any]:
    """Perform an update with optimistic locking.

    If expected_version is provided, the update will only succeed
    if the document's current version matches.

    Args:
        collection: MongoDB collection object
        query: Query to find the document
        update_doc: Update operations to apply
        expected_version: Expected version for optimistic locking

    Returns:
        Dict with 'success', 'modified_count', and optional 'version_mismatch'
    """
    # Add version check to query if expected_version provided
    if expected_version is not None:
        query = {**query, VERSION_FIELD: expected_version}

    # Add version increment to update
    update_doc = increment_version(update_doc)

    # Also update updated_at timestamp
    if '$set' not in update_doc:
        update_doc['$set'] = {}
    update_doc['$set']['updated_at'] = datetime.utcnow()

    result = collection.update_one(query, update_doc)

    response = {
        'success': result.modified_count > 0,
        'modified_count': result.modified_count
    }

    # If we expected a version but no docs were modified, it's likely a version mismatch
    if expected_version is not None and result.modified_count == 0:
        response['version_mismatch'] = True

    return response


def get_version(doc: Dict[str, Any]) -> int:
    """Get the version from a document.

    Args:
        doc: Document to get version from

    Returns:
        Version number (0 if not present)
    """
    return doc.get(VERSION_FIELD, 0)


def ensure_version_index(collection, background: bool = True):
    """Ensure version field is indexed (useful for version-based queries).

    Args:
        collection: MongoDB collection object
        background: Create index in background (default: True)
    """
    try:
        collection.create_index(VERSION_FIELD, background=background)
    except Exception:
        pass  # Index might already exist


# =============================================================================
# High-Write Collection Helpers
# =============================================================================

def update_pond_with_version(
    pond_collection,
    pond_id: str,
    inc_fields: Dict[str, int] = None,
    set_fields: Dict[str, Any] = None,
    expected_version: Optional[int] = None
) -> Dict[str, Any]:
    """Update pond with optimistic locking.

    Args:
        pond_collection: Ponds collection
        pond_id: Pond ID to update
        inc_fields: Fields to increment (e.g., {'metadata.total_fish': 100})
        set_fields: Fields to set
        expected_version: Expected version for locking

    Returns:
        Update result with success status
    """
    query = {'pond_id': pond_id}
    update_doc = {}

    if inc_fields:
        update_doc['$inc'] = inc_fields
    if set_fields:
        update_doc['$set'] = set_fields

    return versioned_update(pond_collection, query, update_doc, expected_version)


def update_bank_balance_with_version(
    bank_collection,
    account_key: str,
    amount: float,
    direction: str = 'out',
    expected_version: Optional[int] = None,
    account_type: str = 'organization'
) -> Dict[str, Any]:
    """Update bank balance with optimistic locking.

    Args:
        bank_collection: Bank accounts collection
        account_key: Account key
        amount: Amount to add (positive) or subtract (negative)
        direction: 'in' for credit, 'out' for debit
        expected_version: Expected version for locking
        account_type: 'organization' or 'user'

    Returns:
        Update result with success status
    """
    query = {'account_key': account_key, 'type': account_type}

    # Determine increment value based on direction
    balance_change = amount if direction == 'in' else -abs(amount)

    update_doc = {
        '$inc': {'balance': balance_change}
    }

    return versioned_update(bank_collection, query, update_doc, expected_version)


def update_fish_stock_with_version(
    fish_collection,
    species_code: str,
    count_change: int,
    expected_version: Optional[int] = None
) -> Dict[str, Any]:
    """Update fish stock with optimistic locking.

    Args:
        fish_collection: Fish collection
        species_code: Species code to update
        count_change: Amount to add (positive) or subtract (negative)
        expected_version: Expected version for locking

    Returns:
        Update result with success status
    """
    query = {'$or': [{'_id': species_code}, {'species_code': species_code}]}

    update_doc = {
        '$inc': {'current_stock': count_change}
    }

    return versioned_update(fish_collection, query, update_doc, expected_version)

