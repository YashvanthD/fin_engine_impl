from fin_server.repository.base_repository import BaseRepository
from bson import ObjectId

class TaskRepository(BaseRepository):
    def __init__(self, db, collection="task"):
        self.collection_name = collection
        print(f"Initializing {self.collection_name} collection:")
        self.collection = db[collection]

    def create(self, data):
        # Ensure user_key is used for consistency
        if 'userkey' in data:
            data['user_key'] = data.pop('userkey')
        # Generate incremental 7-digit task_id
        data['task_id'] = self.get_next_task_id()
        return str(self.collection.insert_one(data).inserted_id)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def find_by_any_id(self, any_id: str):
        """Flexibly resolve a task by:

        - business task_id (e.g. "0001008")
        - Mongo _id stored as string
        - Mongo ObjectId parsed from the string

        This is used by routes so they can accept either the logical task id
        or the raw database id that TaskDTO may expose as `id`.
        """
        # 1) Try business task_id
        doc = self.find_one({'task_id': any_id})
        if doc:
            return doc
        # 2) Try _id as plain string
        doc = self.find_one({'_id': any_id})
        if doc:
            return doc
        # 3) Try to interpret as ObjectId
        try:
            oid = ObjectId(any_id)
            doc = self.find_one({'_id': oid})
            if doc:
                return doc
        except Exception:
            pass
        return None

    def update(self, query, update_fields):
        return self.collection.update_one(query, {'$set': update_fields}).modified_count

    def delete(self, query):
        return self.collection.delete_one(query).deleted_count

    def get_next_task_id(self):
        # Find the max task_id in the collection, default to 999 if none
        last = self.collection.find_one(
            {'task_id': {'$exists': True}},
            sort=[('task_id', -1)]
        )
        if last and str(last.get('task_id', '')).isdigit():
            next_id = int(last['task_id']) + 1
        else:
            next_id = 1000
        # Ensure 7 digits
        return str(next_id).zfill(7)
