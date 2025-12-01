from pymongo import MongoClient
from fin_server.repository.user_repository import mongo_db_repository

class TaskRepository:
    def __init__(self):
        self.collection = mongo_db_repository.get_collection('tasks')

    def create_task(self, task_data):
        # Ensure user_key is used for consistency
        if 'userkey' in task_data:
            task_data['user_key'] = task_data.pop('userkey')
        return str(self.collection.insert_one(task_data).inserted_id)

    def get_tasks_by_user(self, user_key):
        return list(self.collection.find({'user_key': user_key}))

    def update_task(self, task_id, update_fields):
        return self.collection.update_one({'_id': task_id}, {'$set': update_fields}).modified_count

    def delete_task(self, task_id):
        return self.collection.delete_one({'_id': task_id}).deleted_count

    def get_task(self, task_id):
        return self.collection.find_one({'_id': task_id})

task_repository = TaskRepository()
