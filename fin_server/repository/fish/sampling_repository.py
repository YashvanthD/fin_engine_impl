from fin_server.repository.base_repository import BaseRepository
from fin_server.utils.time_utils import get_time_date_dt

class SamplingRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(SamplingRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db, collection="sampling"):
        # Use BaseRepository to set self.collection
        super().__init__(db=db, collection_name=collection)
        self.collection_name = collection
        print(f"Initializing {self.collection_name} collection:")

    def create(self, data):
        doc = dict(data)
        doc['created_at'] = get_time_date_dt(include_time=True)
        res = self.collection.insert_one(doc)
        return getattr(res, 'inserted_id', None)

    def find(self, query=None, *args, **kwargs):
        # Return a Cursor so callers can chain sort()/limit()
        return super().find(query or {}, *args, **kwargs)

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields, multi: bool = False):
        update_fields = dict(update_fields)
        update_fields['updated_at'] = get_time_date_dt(include_time=True)
        if multi:
            res = self.collection.update_many(query, {'$set': update_fields})
        else:
            res = self.collection.update_one(query, {'$set': update_fields})
        return getattr(res, 'modified_count', None)

    def delete(self, query, multi: bool = False):
        if multi:
            res = self.collection.delete_many(query)
        else:
            res = self.collection.delete_one(query)
        return getattr(res, 'deleted_count', None)
