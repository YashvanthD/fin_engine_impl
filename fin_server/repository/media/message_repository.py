from fin_server.repository.base_repository import BaseRepository
from fin_server.utils.time_utils import get_time_date_dt

class MessageRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection="message"):
        if cls._instance is None:
            cls._instance = super(MessageRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="message"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

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

    def find(self, query=None, *args, **kwargs):
        return list(self.collection.find(query or {}, *args, **kwargs))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields, multi: bool = False, *args, **kwargs):
        if multi:
            return self.collection.update_many(query, {'$set': update_fields}, *args, **kwargs)
        return self.collection.update_one(query, {'$set': update_fields}, *args, **kwargs)

    def delete(self, query, multi: bool = False, *args, **kwargs):
        if multi:
            return self.collection.delete_many(query, *args, **kwargs)
        return self.collection.delete_one(query, *args, **kwargs)

    def get_undelivered_messages(self, to_user_key):
        return list(self.collection.find({'to_user_key': to_user_key, 'delivered': False}))

    def mark_as_delivered(self, message_id):
        self.collection.update_one({'_id': message_id}, {'$set': {'delivered': True}})
