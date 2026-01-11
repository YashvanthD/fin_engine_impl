"""Company repository for company data management.

This module provides CRUD operations for company documents.
"""
from fin_server.repository.base_repository import BaseRepository


class CompanyRepository(BaseRepository):
    """Repository for company collection operations."""

    _instance = None

    def __new__(cls, db, collection_name="companies"):
        if cls._instance is None:
            cls._instance = super(CompanyRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="companies"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def create(self, data):
        """Create a new company document."""
        account_key = data.get('account_key')
        if account_key:
            existing = self.find_one({'account_key': account_key})
            if existing:
                raise ValueError(f"Company with account_key '{account_key}' already exists.")
        return str(self.collection.insert_one(data).inserted_id)

    def find(self, query=None, *args, **kwargs):
        """Find companies matching query."""
        return self.find_many(query)

    def find_one(self, query):
        """Find a single company."""
        return self.collection.find_one(query)

    def find_many(self, query=None, limit=0, skip=0, sort=None):
        """Find multiple companies."""
        if query is None:
            query = {}
        cursor = self.collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def update(self, query, update_fields, multi=False):
        """Update company document(s)."""
        if multi:
            return self.collection.update_many(query, {'$set': update_fields}).modified_count
        return self.collection.update_one(query, {'$set': update_fields}).modified_count

    def update_one(self, query, update_doc, upsert=False):
        """Update a single company with custom update document."""
        return self.collection.update_one(query, update_doc, upsert=upsert)

    def delete(self, query, multi=False):
        """Delete company document(s)."""
        if multi:
            return self.collection.delete_many(query).deleted_count
        return self.collection.delete_one(query).deleted_count

    def insert_one(self, data, **kwargs):
        """Insert a single company document."""
        return self.collection.insert_one(data, **kwargs)

    # ==========================================================================
    # Company-specific methods
    # ==========================================================================

    def get_by_account_key(self, account_key):
        """Get company by account_key."""
        return self.find_one({'account_key': account_key})

    def get_by_admin_user_key(self, admin_user_key):
        """Get company by admin user key."""
        return self.find_one({'admin_user_key': admin_user_key})

    def update_users_list(self, account_key, users_list, employee_count=None):
        """Update the users list and employee count for a company."""
        update_doc = {'$set': {'users': users_list}}
        if employee_count is not None:
            update_doc['$set']['employee_count'] = employee_count
        return self.update_one({'account_key': account_key}, update_doc)

    def add_user_to_company(self, account_key, user_info):
        """Add a user to the company's users list."""
        return self.collection.update_one(
            {'account_key': account_key},
            {'$push': {'users': user_info}, '$inc': {'employee_count': 1}}
        )

    def remove_user_from_company(self, account_key, user_key):
        """Remove a user from the company's users list."""
        return self.collection.update_one(
            {'account_key': account_key},
            {'$pull': {'users': {'user_key': user_key}}, '$inc': {'employee_count': -1}}
        )

    def get_company_users(self, account_key):
        """Get users list for a company."""
        company = self.find_one({'account_key': account_key})
        return company.get('users', []) if company else []

    def update_company_name(self, account_key, company_name):
        """Update company name."""
        return self.update({'account_key': account_key}, {'company_name': company_name})

