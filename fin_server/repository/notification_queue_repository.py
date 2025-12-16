from datetime import datetime, timezone
from fin_server.repository.mongo_helper import MongoRepositorySingleton

class NotificationQueueRepository:
    def __init__(self, db=None, collection_name="notifications_queue"):
        self.collection_name = collection_name
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def enqueue(self, notification):
        notification['status'] = 'pending'
        notification['created_at'] = datetime.now(timezone.utc)
        return self.collection.insert_one(notification)

    def mark_sent(self, notification_id):
        return self.collection.update_one(
            {'_id': notification_id},
            {'$set': {'status': 'sent', 'sent_at': datetime.now(timezone.utc)}}
        )

    def get_pending(self, user_key=None):
        query = {'status': 'pending'}
        if user_key:
            query['user_key'] = user_key
        return list(self.collection.find(query))

    def get_for_user(self, user_key, limit=50):
        return list(self.collection.find({'user_key': user_key}).sort('created_at', -1).limit(limit))

