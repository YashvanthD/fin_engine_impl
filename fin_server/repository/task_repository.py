from pymongo import MongoClient
from fin_server.repository.user_repository import mongo_db_repository
from bson import ObjectId
import uuid

class TaskRepository:
    def __init__(self):
        self.collection = mongo_db_repository.get_collection('tasks')

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

    def create_task(self, task_data):
        # Ensure user_key is used for consistency
        if 'userkey' in task_data:
            task_data['user_key'] = task_data.pop('userkey')
        # Generate incremental 7-digit task_id
        task_data['task_id'] = self.get_next_task_id()
        return str(self.collection.insert_one(task_data).inserted_id)

    def get_tasks_by_user(self, user_key):
        return list(self.collection.find({'user_key': user_key}))

    def get_task(self, task_id):
        return self.collection.find_one({'task_id': task_id})

    def update_task(self, task_id, update_fields):
        return self.collection.update_one({'task_id': task_id}, {'$set': update_fields}).modified_count

    def delete_task(self, task_id):
        return self.collection.delete_one({'task_id': task_id}).deleted_count

task_repository = TaskRepository()
