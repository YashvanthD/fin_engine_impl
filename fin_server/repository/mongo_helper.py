from typing import Any
from pymongo import MongoClient
import logging

from config import config

logger = logging.getLogger(__name__)


class MongoRepo:
    _instance = None
    _client = None
    _is_initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MongoRepo, cls).__new__(cls)
            cls._client = MongoClient(config.MONGO_URI)
            cls.init_repositories(cls._instance)
            cls._is_initialized = True
        return cls._instance

    def __init__(self):
        # Use database names from config
        self.user_db_name = config.USER_DB_NAME
        self.media_db_name = config.MEDIA_DB_NAME
        self.expenses_db_name = config.EXPENSES_DB_NAME
        self.fish_db_name = config.FISH_DB_NAME
        self.analytics_db_name = config.ANALYTICS_DB_NAME

        self.user_db = self._client[self.user_db_name]
        self.media_db = self._client[self.media_db_name]
        self.expenses_db = self._client[self.expenses_db_name]
        self.fish_db = self._client[self.fish_db_name]
        self.analytics_db = self._client[self.analytics_db_name]

        #  USER DB REPOSITORIES
        self.users: Any = None
        self.fish_mapping: Any = None
        self.companies = None
        self.ai_usage: Any = None

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

        self.init_repositories()
        self._is_initialized = True

    def init_client(self):
        if self._client is None:
            self._client = MongoClient(config.MONGO_URI)

    def init_dbs(self):
        self.init_client()

        # Use database names from config
        self.user_db_name = config.USER_DB_NAME
        self.media_db_name = config.MEDIA_DB_NAME
        self.expenses_db_name = config.EXPENSES_DB_NAME
        self.fish_db_name = config.FISH_DB_NAME
        self.analytics_db_name = config.ANALYTICS_DB_NAME

        self.user_db = self._client[self.user_db_name]
        self.media_db = self._client[self.media_db_name]
        self.expenses_db = self._client[self.expenses_db_name]
        self.fish_db = self._client[self.fish_db_name]
        self.analytics_db = self._client[self.analytics_db_name]

    def init_repositories(self):
        try:
            from fin_server.repository.expenses import TransactionsRepository
            from fin_server.repository.expenses_repository import ExpensesRepository
            from fin_server.repository.fish import FishRepository, FishActivityRepository, PondEventRepository, PondRepository, \
                FishAnalyticsRepository, SamplingRepository, FeedingRepository
            from fin_server.repository.media import MessageRepository, NotificationRepository, NotificationQueueRepository, \
                TaskRepository
            from fin_server.repository.user import UserRepository, FishMappingRepository, CompanyRepository
            from fin_server.repository.user.ai_usage_repository import AIUsageRepository

            # USER DB REPOSITORIES
            self.init_dbs()
            self.users = UserRepository(self.user_db)
            self.fish_mapping = FishMappingRepository(self.user_db)
            self.companies = CompanyRepository(self.user_db)
            self.ai_usage = AIUsageRepository(self.user_db)

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
        except Exception as e:
            logger.error(f"Error initializing repositories: {e}")
            raise e

    @classmethod
    def is_initialized(cls):
        return cls._is_initialized

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def get_collection(collection_name: str) -> Any:
    """Return the named repository collection from the singleton MongoRepo.

    Avoid importing `server` here to prevent circular import errors when
    modules (DTOs/routes) call this function at import time.
    """
    # Use the MongoRepo singleton directly instead of importing server.mongoDbRepo
    repo = MongoRepo.get_instance()
    # Ensure repositories are initialized
    if not MongoRepo.is_initialized():
        try:
            repo.init_repositories()
        except Exception:
            # If initialization fails, ensure the error is visible to the caller
            raise

    coll = getattr(repo, collection_name, None)
    if coll is None:
        raise ValueError(f"Repository '{collection_name}' is None. Existing: {dir(repo)}")
    return coll


class CollectionAdapter:
    def __init__(self, collection):
        self._coll = collection

    def find(self, query=None, *args, **kwargs):
        if query is None:
            query = {}
        # Return the raw pymongo Cursor so callers can chain sort/limit
        return self._coll.find(query, *args, **kwargs)

    def find_many(self, query=None, *args, **kwargs):
        if query is None:
            query = {}
        return list(self._coll.find(query, *args, **kwargs))
