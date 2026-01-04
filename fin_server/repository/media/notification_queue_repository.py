from fin_server.repository.base_repository import BaseRepository
from fin_server.utils.time_utils import get_time_date_dt

class NotificationQueueRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="notification_queue"):
        if cls._instance is None:
            cls._instance = super(NotificationQueueRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="notification_queue"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            # Ensure backward-compatible attribute used in some repos
            self.coll = self.collection_name
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def enqueue(self, notification):
        notification['status'] = 'pending'
        notification['created_at'] = get_time_date_dt(include_time=True)
        return self.collection.insert_one(notification)

    def mark_sent(self, notification_id):
        return self.collection.update_one(
            {'_id': notification_id},
            {'$set': {'status': 'sent', 'sent_at': get_time_date_dt(include_time=True)}}
        )

    def get_pending(self, user_key=None):
        query = {'status': 'pending'}
        if user_key:
            query['user_key'] = user_key
        return list(self.collection.find(query))

    def get_for_user(self, user_key, limit=50):
        return list(self.collection.find({'user_key': user_key}).sort('created_at', -1).limit(limit))
