from fin_server.utils.time_utils import get_time_date_dt

class NotificationQueueRepository:
    def __init__(self, db, collection="notification_queue"):
        self.collection_name = collection
        print(f"Initializing {self.collection_name} collection:")
        self.collection = db[collection]

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
