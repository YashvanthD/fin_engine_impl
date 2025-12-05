from datetime import datetime, timezone
from pymongo import MongoClient

class PondRepository:
    def __init__(self, db):
        self.collection = db['ponds']

    def create_pond(self, pond_data):
        pond_data['created_at'] = datetime.now(timezone.utc)
        return self.collection.insert_one(pond_data)

    def get_pond(self, pond_id):
        return self.collection.find_one({'_id': pond_id})

    def update_pond(self, pond_id, update_fields):
        update_fields['updated_at'] = datetime.now(timezone.utc)
        return self.collection.update_one({'_id': pond_id}, {'$set': update_fields})

    def delete_pond(self, pond_id):
        return self.collection.delete_one({'_id': pond_id})

    def list_ponds(self, query=None):
        return list(self.collection.find(query or {}))

