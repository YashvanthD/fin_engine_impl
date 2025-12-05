from datetime import datetime, timezone

class NotificationRepository:
    def __init__(self, db):
        self.collection = db['notifications']

    def save_notification(self, notification_data):
        notification_data['created_at'] = datetime.now(timezone.utc)
        notification_data['delivered'] = False
        return self.collection.insert_one(notification_data)

    def get_undelivered_notifications(self, user_key):
        return list(self.collection.find({'user_key': user_key, 'delivered': False}))

    def mark_as_delivered(self, notification_id):
        self.collection.update_one({'_id': notification_id}, {'$set': {'delivered': True}})

    def list_notifications(self, query=None):
        return list(self.collection.find(query or {}))

