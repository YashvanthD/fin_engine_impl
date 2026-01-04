from fin_server.repository.base_repository import BaseRepository
from fin_server.utils.time_utils import get_time_date_dt
import logging

class NotificationRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(NotificationRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db, collection="notification"):
        super().__init__(db)
        self.collection_name = collection
        print(f"Initializing {self.collection_name} collection:")
        self.collection = db[collection]

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
