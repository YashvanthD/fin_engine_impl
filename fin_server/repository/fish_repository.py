from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
import logging
from datetime import datetime, timezone

class FishRepository(BaseRepository):
    def __init__(self, db=None, collection_name="fish"):
        self.collection_name = collection_name
        print("Initializing FishRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        logging.info(f"Inserting fish data: {data}")
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

    def list_fish_by_account(self, account_key):
        return list(self.collection.find({'account_key': account_key}))

    def get_fields(self):
        """Return a set of all field names in the fish collection."""
        sample = self.collection.find_one()
        if not sample:
            return set()
        return set(sample.keys())

    def get_distinct_values(self, field):
        """Return all distinct values for a given field in the fish collection."""
        return self.collection.distinct(field)

    def get_field_stats(self, field):
        """Return min, max, avg for a numeric field in the fish collection."""
        pipeline = [
            {"$group": {
                "_id": None,
                "min": {"$min": f"${field}"},
                "max": {"$max": f"${field}"},
                "avg": {"$avg": f"${field}"}
            }}
        ]
        result = list(self.collection.aggregate(pipeline))
        if result:
            return result[0]
        return {"min": None, "max": None, "avg": None}

    def create_or_update(self, fish_entity):
        species_id = fish_entity['_id']
        self.collection.update_one({'_id': species_id}, {'$set': fish_entity}, upsert=True)
