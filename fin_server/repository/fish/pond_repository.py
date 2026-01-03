from fin_server.repository.base_repository import BaseRepository
import logging
from fin_server.utils.time_utils import get_time_date_dt

class PondRepository(BaseRepository):
    def __init__(self, db, collection="pond"):
        self.collection_name = collection
        print(f"Initializing {self.collection_name} collection:")
        self.collection = db[collection]

    def create(self, data):
        logging.info(f"Inserting pond data: {data}")
        data['created_at'] = get_time_date_dt(include_time=True)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = get_time_date_dt(include_time=True)
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)

    def get_pond(self, pond_id):
        return self.find_one({'pond_id': pond_id})

    def _pond_query(self, pond_id):
        """Return a query that matches a pond by either pond_id or _id."""
        return {'$or': [{'pond_id': pond_id}, {'_id': pond_id}]}

    def atomic_update_metadata(self, pond_id, inc_fields=None, set_fields=None, unset_fields=None):
        update = {}
        if inc_fields:
            update['$inc'] = inc_fields
        if set_fields:
            update['$set'] = set_fields
        if unset_fields:
            update['$unset'] = unset_fields
        if not update:
            return None
        return self.collection.update_one(self._pond_query(pond_id), update, upsert=False)
