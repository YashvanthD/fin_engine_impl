from typing import Any
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
import logging

from config import config

logger = logging.getLogger(__name__)


def create_mongo_client(uri: str, max_retries: int = 3):
    """Create MongoDB client with connection options and retry logic.

    Args:
        uri: MongoDB connection string
        max_retries: Number of connection attempts

    Returns:
        MongoClient instance or None if connection fails
    """
    # Connection options for better reliability
    client_options = {
        'serverSelectionTimeoutMS': 10000,  # 10 seconds
        'connectTimeoutMS': 10000,
        'socketTimeoutMS': 30000,
        'retryWrites': True,
        'retryReads': True,
    }

    # For SRV records (mongodb+srv://), add DNS timeout
    if uri and '+srv' in uri:
        # dnspython timeout is controlled differently
        pass

    for attempt in range(max_retries):
        try:
            client = MongoClient(uri, **client_options)
            # Test connection
            client.admin.command('ping')
            logger.info("MongoDB connection established successfully")
            return client
        except (ConnectionFailure, ConfigurationError) as e:
            logger.warning(f"MongoDB connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                logger.error(f"Failed to connect to MongoDB after {max_retries} attempts")
                raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}")
            raise

    return None


class MongoRepo:
    _instance = None
    _client = None
    _is_initialized = False
    _mongo_uri = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MongoRepo, cls).__new__(cls)
            cls._mongo_uri = config.MONGO_URI
            try:
                cls._client = create_mongo_client(cls._mongo_uri)
            except Exception as e:
                logger.error(f"Failed to initialize MongoDB client: {e}")
                # Don't raise here - allow app to start, repos will be None
                cls._client = None
            if cls._client:
                cls.init_repositories(cls._instance)
            cls._is_initialized = True
        return cls._instance

    @classmethod
    def get_instance(cls):
        """Get the singleton instance, creating if necessary."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if MongoDB is properly initialized."""
        return cls._is_initialized and cls._client is not None

    def __init__(self):
        # Use database names from config
        self.user_db_name = config.USER_DB_NAME
        self.media_db_name = config.MEDIA_DB_NAME
        self.expenses_db_name = config.EXPENSES_DB_NAME
        self.fish_db_name = config.FISH_DB_NAME
        self.analytics_db_name = config.ANALYTICS_DB_NAME

        # Initialize database references (may be None if client not connected)
        if self._client:
            self.user_db = self._client[self.user_db_name]
            self.media_db = self._client[self.media_db_name]
            self.expenses_db = self._client[self.expenses_db_name]
            self.fish_db = self._client[self.fish_db_name]
            self.analytics_db = self._client[self.analytics_db_name]
        else:
            self.user_db = None
            self.media_db = None
            self.expenses_db = None
            self.fish_db = None
            self.analytics_db = None

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

        if self._client:
            self.init_repositories()
        self._is_initialized = True

    def init_client(self):
        if self._client is None:
            try:
                self._client = create_mongo_client(config.MONGO_URI)
            except Exception as e:
                logger.error(f"Failed to initialize MongoDB client: {e}")
                self._client = None

    def init_dbs(self):
        self.init_client()

        if not self._client:
            logger.warning("Cannot initialize databases - MongoDB client not connected")
            return

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
        if not self._client:
            logger.warning("Cannot initialize repositories - MongoDB client not connected")
            return

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



def get_collection(collection_name: str) -> Any:
    """Return the named repository collection from the singleton MongoRepo.

    Avoid importing `server` here to prevent circular import errors when
    modules (DTOs/routes) call this function at import time.

    Returns:
        Repository collection or None if MongoDB is not connected
    """
    # Use the MongoRepo singleton directly instead of importing server.mongoDbRepo
    repo = MongoRepo.get_instance()

    # Check if MongoDB is connected
    if not MongoRepo.is_initialized() or not MongoRepo._client:
        logger.warning(f"MongoDB not connected, cannot get collection '{collection_name}'")
        return None

    # Ensure repositories are initialized
    if not MongoRepo.is_initialized():
        try:
            repo.init_repositories()
        except Exception as e:
            logger.error(f"Failed to initialize repositories: {e}")
            return None

    coll = getattr(repo, collection_name, None)
    if coll is None:
        logger.warning(f"Repository '{collection_name}' is None")
        return None
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
