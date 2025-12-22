from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.utils.time_utils import get_time_date_dt
import logging

class NotificationRepository(BaseRepository):
    def __init__(self, db=None, collection_name="notifications"):
        self.collection_name = collection_name
        print("Initializing NotificationRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        data['created_at'] = get_time_date_dt(include_time=True)
        data['delivered'] = False
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)

    def get_undelivered_notifications(self, user_key):
        return list(self.collection.find({'user_key': user_key, 'delivered': False}))

    def mark_as_delivered(self, notification_id):
        self.collection.update_one({'_id': notification_id}, {'$set': {'delivered': True}})
