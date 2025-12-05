from datetime import datetime, timezone

class NotificationRepository:
    def __init__(self, db):
        self.collection = db['notifications']

    def save_notification(self, account_key, user_key, notification, delivered=False):
        doc = {
            'account_key': account_key,
            'user_key': user_key,
            'notification': notification,
            'timestamp': int(datetime.now(timezone.utc).timestamp()),
            'delivered': delivered
        }
        return self.collection.insert_one(doc)

    def get_undelivered_notifications(self, user_key):
        return list(self.collection.find({'user_key': user_key, 'delivered': False}))

    def mark_as_delivered(self, notification_id):
        self.collection.update_one({'_id': notification_id}, {'$set': {'delivered': True}})
