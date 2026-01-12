"""Audit trail utilities for tracking changes to documents.

This module provides:
- Audit log creation
- Change history tracking
- Soft delete support
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger(__name__)

# Audit log collection
AUDIT_COLLECTION = 'audit_logs'


def create_audit_log(
    action: str,
    collection_name: str,
    document_id: str,
    user_key: str,
    account_key: str,
    changes: Dict[str, Any] = None,
    old_values: Dict[str, Any] = None,
    new_values: Dict[str, Any] = None,
    metadata: Dict[str, Any] = None
) -> Optional[str]:
    """Create an audit log entry.

    Args:
        action: The action performed (create, update, delete, soft_delete, restore)
        collection_name: The collection that was modified
        document_id: The ID of the document that was modified
        user_key: The user who performed the action
        account_key: The organization account
        changes: Summary of changes made
        old_values: Previous values (for updates)
        new_values: New values (for updates)
        metadata: Additional metadata

    Returns:
        The inserted audit log ID, or None on failure
    """
    try:
        audit_repo = get_collection(AUDIT_COLLECTION)

        audit_doc = {
            'action': action,
            'collection': collection_name,
            'document_id': str(document_id),
            'user_key': user_key,
            'account_key': account_key,
            'timestamp': get_time_date_dt(include_time=True),
            'changes': changes,
            'old_values': old_values,
            'new_values': new_values,
            'metadata': metadata or {},
            'ip_address': None,  # Can be populated by caller
            'user_agent': None   # Can be populated by caller
        }

        # Remove None values
        audit_doc = {k: v for k, v in audit_doc.items() if v is not None}

        result = audit_repo.insert_one(audit_doc)
        return str(getattr(result, 'inserted_id', None))
    except Exception:
        logger.exception(f'Failed to create audit log for {action} on {collection_name}/{document_id}')
        return None


def get_audit_history(
    collection_name: str = None,
    document_id: str = None,
    user_key: str = None,
    account_key: str = None,
    action: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get audit history with optional filters.

    Returns:
        List of audit log entries
    """
    try:
        audit_repo = get_collection(AUDIT_COLLECTION)

        query = {}
        if collection_name:
            query['collection'] = collection_name
        if document_id:
            query['document_id'] = str(document_id)
        if user_key:
            query['user_key'] = user_key
        if account_key:
            query['account_key'] = account_key
        if action:
            query['action'] = action

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['timestamp'] = date_query

        cursor = audit_repo.find(query).sort('timestamp', -1).limit(limit)

        results = []
        for doc in cursor:
            doc['_id'] = str(doc.get('_id'))
            results.append(doc)

        return results
    except Exception:
        logger.exception('Failed to get audit history')
        return []


def compute_changes(old_doc: Dict[str, Any], new_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the differences between two documents.

    Returns:
        Dict with 'added', 'removed', 'modified' keys
    """
    changes = {
        'added': {},
        'removed': {},
        'modified': {}
    }

    # Skip internal fields
    skip_fields = {'_id', 'created_at', 'updated_at', 'updated_by'}

    old_keys = set(old_doc.keys()) - skip_fields
    new_keys = set(new_doc.keys()) - skip_fields

    # Added fields
    for key in new_keys - old_keys:
        changes['added'][key] = new_doc[key]

    # Removed fields
    for key in old_keys - new_keys:
        changes['removed'][key] = old_doc[key]

    # Modified fields
    for key in old_keys & new_keys:
        if old_doc[key] != new_doc[key]:
            changes['modified'][key] = {
                'old': old_doc[key],
                'new': new_doc[key]
            }

    # Remove empty sections
    return {k: v for k, v in changes.items() if v}


# =============================================================================
# Soft Delete Support
# =============================================================================

def soft_delete_document(
    collection_name: str,
    document_id: str,
    user_key: str,
    account_key: str,
    reason: str = None
) -> bool:
    """Soft delete a document by setting deleted_at and deleted_by fields.

    Returns:
        True if successful, False otherwise
    """
    try:
        repo = get_collection(collection_name)
        coll = getattr(repo, 'collection', repo)

        # Try to find by _id or document-specific id field
        from bson import ObjectId
        try:
            query = {'_id': ObjectId(document_id)}
        except Exception:
            query = {'_id': document_id}

        doc = coll.find_one(query)
        if not doc:
            # Try alternative ID fields
            for id_field in ['pond_id', 'event_id', 'sampling_id', 'expense_id', 'user_key']:
                doc = coll.find_one({id_field: document_id})
                if doc:
                    query = {id_field: document_id}
                    break

        if not doc:
            logger.warning(f'Document not found for soft delete: {collection_name}/{document_id}')
            return False

        # Set soft delete fields
        update_fields = {
            'deleted_at': get_time_date_dt(include_time=True),
            'deleted_by': user_key,
            'is_deleted': True
        }
        if reason:
            update_fields['deletion_reason'] = reason

        result = coll.update_one(query, {'$set': update_fields})

        if result.modified_count > 0:
            # Create audit log
            create_audit_log(
                action='soft_delete',
                collection_name=collection_name,
                document_id=document_id,
                user_key=user_key,
                account_key=account_key,
                metadata={'reason': reason}
            )
            return True

        return False
    except Exception:
        logger.exception(f'Failed to soft delete {collection_name}/{document_id}')
        return False


def restore_document(
    collection_name: str,
    document_id: str,
    user_key: str,
    account_key: str
) -> bool:
    """Restore a soft-deleted document.

    Returns:
        True if successful, False otherwise
    """
    try:
        repo = get_collection(collection_name)
        coll = getattr(repo, 'collection', repo)

        from bson import ObjectId
        try:
            query = {'_id': ObjectId(document_id), 'is_deleted': True}
        except Exception:
            query = {'_id': document_id, 'is_deleted': True}

        doc = coll.find_one(query)
        if not doc:
            logger.warning(f'Deleted document not found for restore: {collection_name}/{document_id}')
            return False

        # Unset soft delete fields
        result = coll.update_one(
            query,
            {
                '$unset': {
                    'deleted_at': '',
                    'deleted_by': '',
                    'deletion_reason': ''
                },
                '$set': {
                    'is_deleted': False,
                    'restored_at': get_time_date_dt(include_time=True),
                    'restored_by': user_key
                }
            }
        )

        if result.modified_count > 0:
            # Create audit log
            create_audit_log(
                action='restore',
                collection_name=collection_name,
                document_id=document_id,
                user_key=user_key,
                account_key=account_key
            )
            return True

        return False
    except Exception:
        logger.exception(f'Failed to restore {collection_name}/{document_id}')
        return False


def add_not_deleted_filter(query: Dict[str, Any]) -> Dict[str, Any]:
    """Add filter to exclude soft-deleted documents.

    Use this helper to modify queries to exclude deleted documents.
    """
    query = dict(query)
    query['$or'] = query.get('$or', []) + [
        {'is_deleted': {'$ne': True}},
        {'is_deleted': {'$exists': False}}
    ]
    return query


# =============================================================================
# Decorators for automatic auditing
# =============================================================================

def audit_action(action: str, collection_name: str):
    """Decorator to automatically create audit logs for route handlers.

    Usage:
        @audit_action('create', 'ponds')
        def create_pond(auth_payload):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            # Try to extract audit info from context
            try:
                from flask import request, g
                user_key = getattr(g, 'user_key', None)
                account_key = getattr(g, 'account_key', None)

                # Try to get document ID from result
                doc_id = None
                if isinstance(result, tuple) and len(result) >= 1:
                    response_data = result[0]
                    if isinstance(response_data, dict):
                        doc_id = (response_data.get('data', {}).get('id') or
                                  response_data.get('id') or
                                  response_data.get('_id'))

                if user_key and doc_id:
                    create_audit_log(
                        action=action,
                        collection_name=collection_name,
                        document_id=str(doc_id),
                        user_key=user_key,
                        account_key=account_key
                    )
            except Exception:
                logger.exception('Failed to create automatic audit log')

            return result

        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

