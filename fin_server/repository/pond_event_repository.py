from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
import logging
from fin_server.utils.time_utils import get_time_date_dt

class PondEventRepository(BaseRepository):
    def __init__(self, db=None, collection_name="pond_events"):
        self.collection_name = collection_name
        print("Initializing PondEventRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        data['created_at'] = get_time_date_dt(include_time=True)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_many(self, query=None):
        """Return a list of pond events matching the query (alias for find)."""
        return self.find(query)

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = get_time_date_dt(include_time=True)
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)

    def get_events_by_pond(self, pond_id):
        return list(self.collection.find({'pond_id': pond_id}))
