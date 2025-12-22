from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from datetime import datetime, timezone

class FeedingRepository(BaseRepository):
    def __init__(self, db=None, collection_name="feeding"):
        self.collection_name = collection_name
        print("Initializing FeedingRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        data = dict(data)
        data['created_at'] = datetime.now(timezone.utc)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def delete(self, query):
        return self.collection.delete_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = datetime.now(timezone.utc)
        return self.collection.update_one(query, {'$set': update_fields})

