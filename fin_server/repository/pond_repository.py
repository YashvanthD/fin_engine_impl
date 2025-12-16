from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
import logging
from datetime import datetime, timezone

class PondRepository(BaseRepository):
    def __init__(self, db=None, collection_name="ponds"):
        self.collection_name = collection_name
        print("Initializing PondRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        logging.info(f"Inserting pond data: {data}")
        data['created_at'] = datetime.now(timezone.utc)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = datetime.now(timezone.utc)
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)

    def get_pond(self, pond_id):
        return self.find_one({'pond_id': pond_id})

    def atomic_update_metadata(self, pond_id, inc_fields=None, set_fields=None, unset_fields=None):
        """Perform an atomic update on pond metadata using $inc/$set/$unset.
        inc_fields: dict of fields to increment
        set_fields: dict of fields to set
        unset_fields: dict of fields to unset
        """
        update = {}
        if inc_fields:
            update['$inc'] = inc_fields
        if set_fields:
            update['$set'] = set_fields
        if unset_fields:
            update['$unset'] = unset_fields
        if not update:
            return None
        return self.collection.update_one({'pond_id': pond_id}, update, upsert=False)
