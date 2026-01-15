"""Migration script: Seed default roles and permissions.

This script populates the roles and permissions collections with default values.
Run once to initialize the RBAC system.

Defaults are loaded from:
1. MongoDB (if already synced)
2. JSON files in data/ directory

Collections created in user_db:
- roles: Role definitions
- permissions: Permission catalog
- user_permissions: User-specific overrides
- permission_requests: Access requests

Usage:
    python scripts/seed_roles_permissions.py
"""
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fin_server.repository.mongo_helper import MongoRepo
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.utils.generator import generate_uuid_hex
from config.defaults import defaults

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def seed_permissions(db):
    """Seed default permissions from defaults config."""
    logger.info('Seeding permissions...')
    permissions_coll = db['permissions']

    # Get permissions from defaults (MongoDB -> JSON file fallback)
    permissions_list = defaults.get_permissions()
    logger.info(f'  Loaded {len(permissions_list)} permissions from defaults')

    now = get_time_date_dt(include_time=True)
    inserted = 0

    for perm in permissions_list:
        # Check if already exists
        existing = permissions_coll.find_one({'permission_code': perm['code']})
        if existing:
            continue

        perm_id = generate_uuid_hex(24)
        doc = {
            '_id': perm_id,
            'permission_id': perm_id,
            'permission_code': perm['code'],
            'name': perm['name'],
            'description': perm.get('description', ''),
            'category': perm.get('category', 'general'),
            'scope': 'global',
            'account_key': None,
            'is_system': True,
            'active': True,
            'created_by': 'system',
            'created_at': now,
            'updated_at': now
        }
        permissions_coll.insert_one(doc)
        inserted += 1

    logger.info(f'  Inserted {inserted} permissions')
    return inserted


def seed_roles(db):
    """Seed default roles from defaults config."""
    logger.info('Seeding roles...')
    roles_coll = db['roles']

    # Get roles from defaults (MongoDB -> JSON file fallback)
    roles_list = defaults.get_roles()
    logger.info(f'  Loaded {len(roles_list)} roles from defaults')

    # Get all permission codes for expanding "*"
    all_permissions = [p['code'] for p in defaults.get_permissions()]

    now = get_time_date_dt(include_time=True)
    inserted = 0

    for role in roles_list:
        # Check if already exists
        existing = roles_coll.find_one({'role_code': role['role_code'], 'scope': 'global'})
        if existing:
            continue

        # Expand "*" to all permissions
        permissions = role.get('permissions', [])
        if '*' in permissions:
            permissions = all_permissions

        role_id = generate_uuid_hex(24)
        doc = {
            '_id': role_id,
            'role_id': role_id,
            'role_code': role['role_code'],
            'name': role['name'],
            'description': role.get('description', ''),
            'level': role.get('level', 5),
            'permissions': permissions,
            'scope': 'global',
            'account_key': None,
            'is_system': role.get('is_system', True),
            'active': True,
            'created_by': 'system',
            'created_at': now,
            'updated_at': now
        }
        roles_coll.insert_one(doc)
        inserted += 1

    logger.info(f'  Inserted {inserted} roles')
    return inserted


def create_indexes(db):
    """Create indexes for permission collections."""
    logger.info('Creating indexes...')

    # Permissions collection indexes
    db['permissions'].create_index('permission_code', unique=True)
    db['permissions'].create_index('category')
    db['permissions'].create_index('account_key')
    logger.info('  Created permissions indexes')

    # Roles collection indexes
    db['roles'].create_index([('role_code', 1), ('account_key', 1)], unique=True)
    db['roles'].create_index('level')
    db['roles'].create_index('scope')
    logger.info('  Created roles indexes')

    # User permissions collection indexes
    db['user_permissions'].create_index([('user_key', 1), ('account_key', 1)], unique=True)
    db['user_permissions'].create_index('account_key')
    logger.info('  Created user_permissions indexes')

    # Permission requests collection indexes
    db['permission_requests'].create_index('request_id', unique=True)
    db['permission_requests'].create_index([('user_key', 1), ('account_key', 1)])
    db['permission_requests'].create_index([('account_key', 1), ('status', 1)])
    db['permission_requests'].create_index('created_at')
    logger.info('  Created permission_requests indexes')


def sync_defaults_to_db():
    """Sync JSON files to MongoDB defaults collection."""
    logger.info('Syncing defaults to MongoDB...')
    results = defaults.sync_all_to_db()
    for key, success in results.items():
        status = '✓' if success else '✗'
        logger.info(f'  {key}: {status}')
    return results


def main():
    logger.info('=' * 60)
    logger.info('Seeding Roles and Permissions')
    logger.info('=' * 60)

    mongo_repo = MongoRepo.get_instance()
    if mongo_repo is None or not hasattr(mongo_repo, 'user_db') or mongo_repo.user_db is None:
        logger.error('Failed to connect to user database')
        return

    db = mongo_repo.user_db

    # Sync defaults from JSON files to MongoDB
    sync_defaults_to_db()

    # Create indexes
    create_indexes(db)

    # Seed permissions
    seed_permissions(db)

    # Seed roles
    seed_roles(db)

    logger.info('=' * 60)
    logger.info('Seeding complete!')
    logger.info('')
    logger.info('Collections updated:')
    logger.info('  - defaults: JSON files synced to DB')
    logger.info('  - permissions: Permission catalog')
    logger.info('  - roles: Role definitions')
    logger.info('=' * 60)


if __name__ == '__main__':
    main()

