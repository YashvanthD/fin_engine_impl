from pymongo import MongoClient
import os
import logging


class MongoRepositorySingleton:
    _instance = None
    _db_instance = None

    @classmethod
    def get_db(cls):
        """Singleton utility to get the MongoDB database object.

        Uses the MONGO_URI and MONGO_DB environment variables. For local
        development, defaults to mongodb://localhost:27017 and database
        'user_db' if not explicitly set. In production you should always
        set MONGO_URI and MONGO_DB securely via environment.
        """
        if cls._db_instance is not None:
            return cls._db_instance
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
        db_name = os.getenv('MONGO_DB', 'user_db')
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
        from fin_server.repository.notification_queue_repository import NotificationQueueRepository
        from .fish_mapping_repository import FishMappingRepository
        # New optional repositories for frontend compatibility (import defensively)
        try:
            from fin_server.repository.feeding_repository import FeedingRepository
        except Exception:
            FeedingRepository = None
        try:
            from fin_server.repository.sampling_repository import SamplingRepository
        except Exception:
            SamplingRepository = None

        db = self.get_db()
        self.fish = FishRepository(db)
        self.pond = PondRepository(db)
        self.pond_event = PondEventRepository(db)
        self.user = UserRepository(db)
        self.task = TaskRepository(db)
        self.message = MessageRepository(db)
        self.notification = NotificationRepository(db)
        # optional repositories (only initialize if available)
        self.feeding = FeedingRepository(db) if FeedingRepository else None
        self.sampling = SamplingRepository(db) if SamplingRepository else None
        # fish_mapping repository expects an already-created collection
        self.fish_mapping = FishMappingRepository(self.get_collection('fish_mapping', db))
        # NotificationQueueRepository expects a db instance (it will fetch/create its collection)
        self.notification_queue = NotificationQueueRepository(db)
        current_app_logger = logging.getLogger('fin_server.mongo_helper')
        current_app_logger.debug('Initialized notification_queue repository with DB instance')
        # Ensure recommended indexes for performance
        try:
            self._ensure_indexes(db)
        except Exception as e:
            logging.exception(f'Failed to ensure DB indexes: {e}')

    def _ensure_indexes(self, db):
        """Create recommended indexes used by query paths (idempotent)."""
        try:
            # pond_events: quick lookup by pond_id and created_at
            db['pond_events'].create_index([('pond_id', 1), ('created_at', -1)], name='pond_events_pond_created_at')
            # fish_activity: pond + fish + created_at
            db['fish_activity'].create_index([('pond_id', 1), ('fish_id', 1), ('created_at', -1)], name='fish_activity_pond_fish_created_at')
            # fish_analytics: species and account + date
            db['fish_analytics'].create_index([('species_id', 1), ('account_key', 1), ('date_added', -1)], name='fish_analytics_species_account_date')
            # fish_mapping: account_key
            db['fish_mapping'].create_index([('account_key', 1)], unique=True, name='fish_mapping_account_key')
            # ponds: pond_id
            db['ponds'].create_index([('pond_id', 1)], unique=True, name='ponds_pond_id')
            logging.info('Ensured recommended DB indexes')
        except Exception as e:
            logging.exception(f'Error creating indexes: {e}')
