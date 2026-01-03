from typing import Optional, Any, Dict
from pymongo import MongoClient
from pymongo.database import Database
import os
import logging
import importlib
import json


logger = logging.getLogger(__name__)

class MongoRepo:
    _instance = None
    _client = None
    _mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    _is_initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MongoRepo, cls).__new__(cls)
            cls._client = MongoClient(cls._mongo_uri)
            cls._is_initialized = True
        return cls._instance

    def __init__(self):

        self.user_db_name = 'user_db'
        self.media_db_name = 'media_db'
        self.expenses_db_name = 'expenses_db'
        self.fish_db_name = 'fish_db'
        self.analytics_db_name = 'analytics_db'

        self.user_db = self._client[self.user_db_name]
        self.media_db = self._client[self.media_db_name]
        self.expenses_db = self._client[self.expenses_db_name]
        self.fish_db = self._client[self.fish_db_name]
        self.analytics_db = self._client[self.analytics_db_name]

        #  USER DB REPOSITORIES
        self.users: Any = None
        self.fish_mapping: Any = None

        # MEDIA DB REPOSITORIES
        self.message: Any = None
        self.notification: Any = None
        self.notification_queue: Any = None
        self.task: Any = None

        # FISH DB REPOSITORIES
        self.fish: Any = None
        self.pond: Any = None
        self.pond_event: Any = None
        self.fish_analytics: Any = None
        self.fish_activity = None
        self.feedback: Any = None
        self.feedback_queue: Any = None
        self.sampling: Any = None

        # EXPENSE/TRANSACTION DB REPOSITORIES
        self.expenses: Any = None
        self.transactions: Any = None
        self.feeding: Any = None


    def init_repositories(self):
        from fin_server.repository.expenses import TransactionsRepository
        from fin_server.repository.expenses_repository import ExpensesRepository
        from fin_server.repository.fish import FishRepository, FishActivityRepository, PondEventRepository, PondRepository, \
            FishAnalyticsRepository, SamplingRepository, FeedingRepository
        from fin_server.repository.media import MessageRepository, NotificationRepository, NotificationQueueRepository, \
            TaskRepository
        from fin_server.repository.user import UserRepository, FishMappingRepository
        # USER DB REPOSITORIES
        self.users = UserRepository(self.user_db)
        self.fish_mapping = FishMappingRepository(self.user_db)

        # MEDIA DB REPOSITORIES
        self.message = MessageRepository(self.media_db)
        self.notification = NotificationRepository(self.media_db)
        self.notification_queue = NotificationQueueRepository(self.media_db)
        self.task = TaskRepository(self.media_db)

        # FISH DB REPOSITORIES
        self.fish = FishRepository(self.fish_db)
        self.fish_activity = FishActivityRepository(self.fish_db)
        self.fish_analytics = FishAnalyticsRepository(self.fish_db)
        self.pond = PondRepository(self.fish_db)
        self.pond_event = PondEventRepository(self.fish_db)
        self.sampling = SamplingRepository(self.fish_db)

        # EXPENSE/TRANSACTION DB REPOSITORIES
        self.expenses = ExpensesRepository(self.expenses_db)
        self.transactions = TransactionsRepository(self.expenses_db)
        self.feeding = FeedingRepository(self.expenses_db)

    @classmethod
    def is_initialized(cls):
        return cls._is_initialized

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.init_repositories()
        return cls._instance


def get_collection(collection_name: str) -> Any:
    mongo_repo = MongoRepo.get_instance()
    # Don't need to init_repositories again; already handled in get_instance.
    coll = getattr(mongo_repo, collection_name, None)
    if coll is None:
        raise ValueError(f"Database '{collection_name}' not found in MongoRepo")
    return coll

