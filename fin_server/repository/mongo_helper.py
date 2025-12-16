from pymongo import MongoClient
import os
import logging

from fin_server.repository.fish_mapping_repository import FishMappingRepository


class MongoRepositorySingleton:
    _instance = None
    _db_instance = None

    @classmethod
    def get_db(cls):
        """
        Singleton utility to get the MongoDB database object using the MONGO_URI env variable.
        Returns the same database instance for use in any repository or route.
        Logs the URI being used for debugging.
        """
        if cls._db_instance is not None:
            return cls._db_instance
        mongo_uri = os.getenv('MONGO_URI', 'mongodb+srv://finuser:finpass@yashmongo1.pdwb1iv.mongodb.net/?appName=yashmongo1')
        db_name = os.getenv('MONGO_DB', 'user_db')
        print(f"[MongoRepositorySingleton] Connecting to MongoDB URI: {mongo_uri}, DB: {db_name}")
        logging.info(f"[MongoRepositorySingleton] Connecting to MongoDB URI: {mongo_uri}, DB: {db_name}")
        client = MongoClient(mongo_uri)
        cls._db_instance = client[db_name]
        return cls._db_instance

    @classmethod
    def get_collection(cls, collection_name, db=None):
        """
        Get a collection from the database, creating it if it does not exist.
        Logs creation and errors. Returns the collection object.
        """
        if db is None:
            db = cls.get_db()
        try:
            if collection_name not in db.list_collection_names():
                db.create_collection(collection_name)
                logging.info(f"Created '{collection_name}' collection in DB.")
        except Exception as e:
            logging.warning(f"Error ensuring '{collection_name}' collection exists: {e}")
        return db[collection_name]

    @classmethod
    def get_instance(cls):
        return cls.__new__(cls)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            print("Initializing MongoRepositorySingleton instance.")
            cls._instance._init_repositories()
        return cls._instance

    def _init_repositories(self):
        from fin_server.repository.fish_repository import FishRepository
        from fin_server.repository.pond_repository import PondRepository
        from fin_server.repository.pond_event_repository import PondEventRepository
        from fin_server.repository.user_repository import UserRepository
        from fin_server.repository.task_repository import TaskRepository
        from fin_server.repository.message_repository import MessageRepository
        from fin_server.repository.notification_repository import NotificationRepository
        from .fish_mapping_repository import FishMappingRepository

        db = self.get_db()
        self.fish = FishRepository(db)
        self.pond = PondRepository(db)
        self.pond_event = PondEventRepository(db)
        self.user = UserRepository(db)
        self.task = TaskRepository(db)
        self.message = MessageRepository(db)
        self.notification = NotificationRepository(db)
        self.fish_mapping = FishMappingRepository(self.get_collection('fish_mapping', db))
