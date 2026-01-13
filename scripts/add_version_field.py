"""Migration script: Add version field (_v) to high-write collections.

This script adds a version field to collections that have high write frequency
to support optimistic concurrency control.

Collections updated:
- ponds
- bank_accounts
- fish

Usage:
    python scripts/add_version_field.py

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


def add_version_field(collection_name: str, version: int = 1):
    """Add version field to documents that don't have it."""
    repo = get_collection(collection_name)
    if repo is None:
        logger.error(f'{collection_name}: Failed to get collection')
        return 0

    # Get the underlying collection
    coll = getattr(repo, 'collection', repo)

    # Count documents without _v field
    query = {'_v': {'$exists': False}}
    count = coll.count_documents(query)

    if count == 0:
        logger.info(f'{collection_name}: All documents already have _v field')
        return 0

    logger.info(f'{collection_name}: Found {count} documents without _v field')

    # Update all documents without _v field
    result = coll.update_many(query, {'$set': {'_v': version}})

    logger.info(f'{collection_name}: Updated {result.modified_count} documents')
    return result.modified_count


def main():
    collections = ['pond', 'fish']  # Repository names
    total_updated = 0

    logger.info('Starting version field migration...')
    logger.info('=' * 50)

    for collection in collections:
        try:
            updated = add_version_field(collection)
            total_updated += updated
        except Exception as e:
            logger.error(f'{collection}: Error - {e}')

    # bank_accounts - try to get it
    try:
        updated = add_version_field('bank_accounts')
        total_updated += updated
    except Exception as e:
        logger.error(f'bank_accounts: Error - {e}')

    logger.info('=' * 50)
    logger.info(f'Migration complete. Total documents updated: {total_updated}')


if __name__ == '__main__':
    main()

