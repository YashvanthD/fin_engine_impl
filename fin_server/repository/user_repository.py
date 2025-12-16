from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton

class UserRepository(BaseRepository):
    def __init__(self, db=None, collection_name="users"):
        self.collection_name = collection_name
        print("Initializing User, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        # Check for duplicate user_key before insert
        user_key = data.get('user_key')
        if user_key:
            existing = self.find_one({'user_key': user_key})
            if existing:
                raise ValueError(f"Duplicate user_key '{user_key}' not allowed.")
        return str(self.collection.insert_one(data).inserted_id)

    def find(self, query=None):
        if query is None:
            query = {}
        return list(self.collection.find(query))

    def find_one(self, query):
        return self.collection.find_one(query)

    def find_many(self, query=None, limit=0, skip=0, sort=None):
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
        if multi:
            return self.collection.update_many(query, {'$set': update_fields}).modified_count
        else:
            return self.collection.update_one(query, {'$set': update_fields}).modified_count

    def delete(self, query, multi=False):
        if multi:
            return self.collection.delete_many(query).deleted_count
        else:
            return self.collection.delete_one(query).deleted_count

    def find_many_by_user_keys(self, user_keys):
        return list(self.collection.find({'user_key': {'$in': user_keys}}))

    def get_by_user_key(self, user_key):
        return self.find_one({'user_key': user_key})

    def get_by_account_key(self, account_key):
        return self.find({'account_key': account_key})

    def get_by_email(self, email):
        return self.find_one({'email': email})

    def get_by_username(self, username):
        return self.find_one({'username': username})

    def get_by_phone(self, phone):
        return self.find_one({'phone': phone})
