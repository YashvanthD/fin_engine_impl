"""Migration script: Remove embedded users array from companies collection.

This script removes the embedded users[] array from company documents
since users are now tracked via account_key in the users collection.

Usage:
    python scripts/remove_embedded_users.py

Ensure MONGO_URI and MONGO_DB environment variables are set.
"""
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fin_server.repository.mongo_helper import get_collection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def remove_embedded_users():
    """Remove embedded users array from company documents."""
    companies_repo = get_collection('companies')
    if companies_repo is None:
        logger.error('Failed to get companies collection')
        return 0

    # Get the underlying collection
    companies = getattr(companies_repo, 'collection', companies_repo)

    # Count documents with users array
    query = {'users': {'$exists': True}}
    count = companies.count_documents(query)

    if count == 0:
        logger.info('companies: No documents have embedded users array')
        return 0

    logger.info(f'companies: Found {count} documents with embedded users array')

    # Remove the users field from all documents
    result = companies.update_many(
        query,
        {'$unset': {'users': ''}}
    )

    logger.info(f'companies: Removed users array from {result.modified_count} documents')
    return result.modified_count


def sync_employee_counts():
    """Sync employee counts based on users collection."""
    users_repo = get_collection('users')
    companies_repo = get_collection('companies')

    if users_repo is None or companies_repo is None:
        logger.error('Failed to get users or companies collection')
        return 0

    # Get the underlying collections
    users = getattr(users_repo, 'collection', users_repo)
    companies = getattr(companies_repo, 'collection', companies_repo)

    # Get all unique account_keys from users
    pipeline = [
        {'$group': {'_id': '$account_key', 'count': {'$sum': 1}}},
    ]

    counts = list(users.aggregate(pipeline))
    updated = 0

    for item in counts:
        account_key = item['_id']
        count = item['count']

        if account_key:
            result = companies.update_one(
                {'account_key': account_key},
                {'$set': {'employee_count': count}}
            )
            if result.modified_count > 0:
                updated += 1
                logger.info(f'  Updated employee_count for {account_key}: {count}')

    logger.info(f'companies: Updated employee_count for {updated} companies')
    return updated


def main():
    logger.info('Starting embedded users removal migration...')
    logger.info('=' * 50)

    # Remove embedded users array
    remove_embedded_users()

    logger.info('')

    # Sync employee counts
    logger.info('Syncing employee counts from users collection...')
    sync_employee_counts()

    logger.info('=' * 50)
    logger.info('Migration complete.')


if __name__ == '__main__':
    main()

