from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from datetime import datetime, timezone

class MessageRepository(BaseRepository):
    def __init__(self, db=None, collection_name="messages"):
        self.collection_name = collection_name
        print("Initializing MessageRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        doc = {
            'from_user_key': data['from_user_key'],
            'to_user_key': data['to_user_key'],
            'message': data['message'],
            'timestamp': int(datetime.now(timezone.utc).timestamp()),
            'delivered': data.get('delivered', False)
        }
        return self.collection.insert_one(doc)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)

    def get_undelivered_messages(self, to_user_key):
        return list(self.collection.find({'to_user_key': to_user_key, 'delivered': False}))

    def mark_as_delivered(self, message_id):
        self.collection.update_one({'_id': message_id}, {'$set': {'delivered': True}})
