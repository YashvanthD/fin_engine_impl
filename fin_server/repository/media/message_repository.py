from fin_server.repository.base_repository import BaseRepository
from fin_server.utils.time_utils import get_time_date_dt

class MessageRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(MessageRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db, collection="message"):
        super().__init__(db)
        self.collection_name = collection
        print(f"Initializing {self.collection_name} collection:")
        self.collection = db[collection]

    def create(self, data):
        doc = {
            'from_user_key': data['from_user_key'],
            'to_user_key': data['to_user_key'],
            'message': data['message'],
            # Use get_time_date_dt (IST-aware) then convert to epoch seconds for storage
            'timestamp': int(get_time_date_dt(include_time=True).timestamp()),
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
