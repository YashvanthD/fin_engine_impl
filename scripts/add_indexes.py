"""Migration script: Add missing indexes for common queries.

This script creates indexes for:
1. Query performance optimization
2. Common query patterns

Note: TTL indexes are NOT added - all data is retained for 5+ years for analytics.

Usage:
    python scripts/add_indexes.py

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


def get_underlying_collection(collection_name: str):
    """Get the underlying pymongo collection from a repository."""
    repo = get_collection(collection_name)
    if repo is None:
        return None
    return getattr(repo, 'collection', repo)


def create_index_safe(coll, index_spec, **kwargs):
    """Create an index, handling if it already exists."""
    if coll is None:
        logger.warning(f'  Collection is None, skipping index')
        return False
    try:
        index_name = coll.create_index(index_spec, **kwargs)
        logger.info(f'  Created index: {index_name}')
        return True
    except Exception as e:
        if 'already exists' in str(e).lower():
            logger.info(f'  Index already exists: {index_spec}')
            return False
        else:
            logger.error(f'  Error creating index {index_spec}: {e}')
            return False



def add_query_indexes():
    """Add indexes for common queries."""
    logger.info('Adding query indexes...')

    # Tasks - for reminder queries (scheduler)
    logger.info('tasks: Adding reminder query index')
    coll = get_underlying_collection('task')
    if coll:
        create_index_safe(
            coll,
            [('reminder_time', 1), ('status', 1), ('reminder', 1)],
            background=True
        )
        logger.info('tasks: Adding assignee query index')
        create_index_safe(
            coll,
            [('assignee', 1), ('account_key', 1)],
            background=True
        )

    # Messages - for conversation listing
    logger.info('messages: Adding conversation listing index')
    coll = get_underlying_collection('message')
    if coll:
        create_index_safe(
            coll,
            [('conversation_id', 1), ('created_at', -1)],
            background=True
        )
        logger.info('messages: Adding unread count index')
        create_index_safe(
            coll,
            [('conversation_id', 1), ('sender_key', 1), ('created_at', -1)],
            background=True
        )

    # Expenses - for date range reports
    logger.info('expenses: Adding report query index')
    coll = get_underlying_collection('expenses')
    if coll:
        create_index_safe(
            coll,
            [('account_key', 1), ('created_at', 1), ('category', 1)],
            background=True
        )

    # Fish analytics - for harvest prediction
    logger.info('fish_analytics: Adding harvest prediction index')
    coll = get_underlying_collection('fish_analytics')
    if coll:
        create_index_safe(
            coll,
            [('expected_harvest_date', 1), ('account_key', 1)],
            background=True
        )

    # Ponds - for account queries
    logger.info('ponds: Adding account query index')
    coll = get_underlying_collection('pond')
    if coll:
        create_index_safe(
            coll,
            [('account_key', 1), ('deleted_at', 1)],
            background=True
        )

    # Sampling - for pond queries
    logger.info('sampling: Adding pond query index')
    coll = get_underlying_collection('sampling')
    if coll:
        create_index_safe(
            coll,
            [('pond_id', 1), ('created_at', -1)],
            background=True
        )

    # Pond events - for species history
    logger.info('pond_event: Adding species history index')
    coll = get_underlying_collection('pond_event')
    if coll:
        create_index_safe(
            coll,
            [('account_key', 1), ('fish_id', 1)],
            background=True
        )


def add_deleted_at_field():
    """Add deleted_at field to collections that need soft delete."""
    logger.info('Adding deleted_at field to collections...')

    collection_names = ['fish', 'feeding', 'fish_analytics']

    for coll_name in collection_names:
        coll = get_underlying_collection(coll_name)
        if coll is None:
            logger.warning(f'  {coll_name}: Collection not found')
            continue

        query = {'deleted_at': {'$exists': False}}
        count = coll.count_documents(query)

        if count == 0:
            logger.info(f'  {coll_name}: All documents already have deleted_at field')
            continue

        result = coll.update_many(query, {'$set': {'deleted_at': None}})
        logger.info(f'  {coll_name}: Added deleted_at to {result.modified_count} documents')


def main():
    logger.info('Starting index migration...')
    logger.info('=' * 50)
    logger.info('Note: No TTL indexes - all data retained for 5+ years analytics')
    logger.info('')

    # Add query indexes
    add_query_indexes()
    logger.info('')

    # Add deleted_at field
    add_deleted_at_field()

    logger.info('=' * 50)
    logger.info('Index migration complete.')



if __name__ == '__main__':
    main()


