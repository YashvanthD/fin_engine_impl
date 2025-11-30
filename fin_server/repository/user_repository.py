from pymongo import MongoClient


class MongoDBRepository:
    _instance = None

    def __new__(cls, uri=None, db_name=None):
        if cls._instance is None:
            cls._instance = super(MongoDBRepository, cls).__new__(cls)
            cls._instance._init(uri, db_name)
        return cls._instance

    def _init(self, uri, db_name):
        self.uri = uri or 'mongodb+srv://finuser:finpass@yashmongo1.pdwb1iv.mongodb.net/?appName=yashmongo1'
        self.db_name = db_name or 'user_db'
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]

    def get_collection(self, collection_name):
        return self.db[collection_name]

    def create(self, collection_name, document):
        # Check for duplicate user_key before insert
        user_key = document.get('user_key')
        if user_key:
            existing = self.get_collection(collection_name).find_one({'user_key': user_key})
            if existing:
                raise ValueError(f"Duplicate user_key '{user_key}' not allowed.")
        return str(self.get_collection(collection_name).insert_one(document).inserted_id)

    def find(self, collection_name, query=None):
        if query is None:
            query = {}
        return list(self.get_collection(collection_name).find(query))

    def find_many(self, collection_name, query=None):
        if query is None:
            query = {}
        return list(self.get_collection(collection_name).find(query))

    def update(self, collection_name, query, update_fields):
        result = self.get_collection(collection_name).update_many(query, {'$set': update_fields})
        return result.modified_count

    def delete(self, collection_name, query):
        result = self.get_collection(collection_name).delete_many(query)
        return result.deleted_count

    def find_one(self, collection_name, query):
        return self.get_collection(collection_name).find_one(query)


# Singleton instance for DB reuse
mongo_db_repository = MongoDBRepository()
