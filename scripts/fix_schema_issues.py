"""Migration script: Add scope field to fish collection and fix schema issues.

This script:
1. Adds 'scope' field to fish documents (default: 'global')
2. Adds 'deleted_at' field to collections missing it
3. Fixes circular references by choosing single direction

Usage:
    python scripts/fix_schema_issues.py

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


def add_scope_to_fish():
    """Add scope field to fish documents that don't have it."""
    logger.info('Adding scope field to fish collection...')
    coll = get_underlying_collection('fish')
    if coll is None:
        logger.error('  fish: Collection not found')
        return 0

    # Count documents without scope field
    query = {'scope': {'$exists': False}}
    count = coll.count_documents(query)

    if count == 0:
        logger.info('  fish: All documents already have scope field')
        return 0

    logger.info(f'  fish: Found {count} documents without scope field')

    # Update documents - set scope based on account_key
    # If account_key exists, it's account-specific; otherwise global
    result_global = coll.update_many(
        {'scope': {'$exists': False}, 'account_key': {'$exists': False}},
        {'$set': {'scope': 'global'}}
    )
    result_account = coll.update_many(
        {'scope': {'$exists': False}, 'account_key': {'$exists': True}},
        {'$set': {'scope': 'account'}}
    )

    total = result_global.modified_count + result_account.modified_count
    logger.info(f'  fish: Added scope to {total} documents (global: {result_global.modified_count}, account: {result_account.modified_count})')
    return total


def add_deleted_at_to_collections():
    """Add deleted_at field to collections that need soft delete."""
    logger.info('Adding deleted_at field to collections...')

    collections = ['fish', 'feeding', 'fish_analytics', 'sampling', 'pond_event']
    total = 0

    for coll_name in collections:
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
        total += result.modified_count

    return total


def add_sender_info_to_messages():
    """Add sender_info field to existing messages for denormalization."""
    logger.info('Adding sender_info field to messages...')

    messages_coll = get_underlying_collection('message')
    users_coll = get_underlying_collection('users')

    if messages_coll is None:
        logger.warning('  messages: Collection not found')
        return 0

    # Get messages without sender_info
    query = {'sender_info': {'$exists': False}}
    count = messages_coll.count_documents(query)

    if count == 0:
        logger.info('  messages: All documents already have sender_info field')
        return 0

    logger.info(f'  messages: Found {count} messages without sender_info')

    # Build user lookup cache
    user_cache = {}
    if users_coll:
        for user in users_coll.find({}, {'user_key': 1, 'username': 1, 'avatar_url': 1, 'profile_image': 1}):
            user_key = user.get('user_key')
            if user_key:
                user_cache[user_key] = {
                    'user_key': user_key,
                    'username': user.get('username'),
                    'avatar_url': user.get('avatar_url') or user.get('profile_image')
                }

    # Update messages in batches
    updated = 0
    for msg in messages_coll.find(query, {'_id': 1, 'sender_key': 1}):
        sender_key = msg.get('sender_key')
        sender_info = user_cache.get(sender_key, {'user_key': sender_key, 'username': None, 'avatar_url': None})

        messages_coll.update_one(
            {'_id': msg['_id']},
            {'$set': {'sender_info': sender_info}}
        )
        updated += 1

        if updated % 100 == 0:
            logger.info(f'  messages: Updated {updated} documents...')

    logger.info(f'  messages: Added sender_info to {updated} documents')
    return updated


def add_unread_counts_to_conversations():
    """Add unread_counts field to conversations."""
    logger.info('Adding unread_counts field to conversations...')

    coll = get_underlying_collection('message')  # Get from message repo since conversations might be there
    if coll is None:
        logger.warning('  conversations: Collection not found')
        return 0

    # Try to get conversations collection from the same database
    try:
        conversations_coll = coll.database['conversations']
    except Exception:
        logger.warning('  conversations: Could not access conversations collection')
        return 0

    query = {'unread_counts': {'$exists': False}}
    count = conversations_coll.count_documents(query)

    if count == 0:
        logger.info('  conversations: All documents already have unread_counts field')
        return 0

    # Initialize unread_counts to empty dict for all participants
    result = conversations_coll.update_many(
        query,
        {'$set': {'unread_counts': {}}}
    )

    logger.info(f'  conversations: Added unread_counts to {result.modified_count} documents')
    return result.modified_count


def main():
    logger.info('Starting schema fixes migration...')
    logger.info('=' * 50)

    # Add scope to fish
    add_scope_to_fish()
    logger.info('')

    # Add deleted_at to collections
    add_deleted_at_to_collections()
    logger.info('')

    # Add sender_info to messages
    add_sender_info_to_messages()
    logger.info('')

    # Add unread_counts to conversations
    add_unread_counts_to_conversations()

    logger.info('=' * 50)
    logger.info('Schema fixes migration complete.')


if __name__ == '__main__':
    main()

