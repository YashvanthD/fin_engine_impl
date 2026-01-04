from fin_server.repository.base_repository import BaseRepository
import logging
from fin_server.utils.time_utils import get_time_date_dt

class PondEventRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="pond_event"):
        if cls._instance is None:
            cls._instance = super(PondEventRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="pond_event"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def create(self, data):
        data['created_at'] = get_time_date_dt(include_time=True)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_many(self, query=None):
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
