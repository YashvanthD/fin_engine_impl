from datetime import datetime, timezone

class MessageRepository:
    def __init__(self, db):
        self.collection = db['messages']

    def save_message(self, from_user_key, to_user_key, message, delivered=False):
        doc = {
            'from_user_key': from_user_key,
            'to_user_key': to_user_key,
            'message': message,
            'timestamp': int(datetime.now(timezone.utc).timestamp()),
            'delivered': delivered
        }
        return self.collection.insert_one(doc)

    def get_undelivered_messages(self, to_user_key):
        return list(self.collection.find({'to_user_key': to_user_key, 'delivered': False}))

    def mark_as_delivered(self, message_id):
        self.collection.update_one({'_id': message_id}, {'$set': {'delivered': True}})

