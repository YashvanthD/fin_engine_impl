from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton

class TaskRepository(BaseRepository):
    def __init__(self, db=None, collection_name="tasks"):
        self.collection_name = collection_name
        print("Initializing TaskRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

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

    def find_by_any_id(self, task_id: str):
        """Flexibly resolve a task by business task_id or Mongo _id string.

        This lets API routes accept either the logical task_id (e.g. "0001008")
        or the underlying ObjectId string that TaskDTO exposes as id.
        """
        doc = self.find_one({'task_id': task_id})
        if doc:
            return doc
        # Fallback: try _id as raw string; callers can cast to ObjectId if desired
        return self.find_one({'_id': task_id})

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
