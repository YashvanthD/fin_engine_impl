from datetime import datetime, timezone
from pymongo import MongoClient

class FishRepository:
    def __init__(self, db):
        self.collection = db['fish']

    def create_fish(self, fish_data):
        fish_data['created_at'] = datetime.now(timezone.utc)
        # Ensure account_key is present for mapping
        if 'account_key' not in fish_data:
            raise ValueError('account_key is required for fish mapping')
        return self.collection.insert_one(fish_data)

    def get_fish(self, fish_id):
        return self.collection.find_one({'_id': fish_id})

    def update_fish(self, fish_id, update_fields):
        update_fields['updated_at'] = datetime.now(timezone.utc)
        return self.collection.update_one({'_id': fish_id}, {'$set': update_fields})

    def delete_fish(self, fish_id):
        return self.collection.delete_one({'_id': fish_id})

    def list_fish(self, query=None):
        return list(self.collection.find(query or {}))

    def list_fish_by_account(self, account_key):
        return list(self.collection.find({'account_key': account_key}))
