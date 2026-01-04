from fin_server.repository.base_repository import BaseRepository
from fin_server.utils.time_utils import get_time_date_dt

class FeedingRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(FeedingRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db, collection="feeding"):
        super().__init__(db)
        self.collection_name = collection
        print(f"Initializing {self.collection_name} collection:")
        self.collection = db[collection]

    def create(self, data):
        data = dict(data)
        data['created_at'] = get_time_date_dt(include_time=True)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def delete(self, query):
        return self.collection.delete_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = get_time_date_dt(include_time=True)
        return self.collection.update_one(query, {'$set': update_fields})
