from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class AuditLogsRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="audit_logs"):
        if cls._instance is None:
            cls._instance = super(AuditLogsRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="audit_logs"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            # Backwards-compatible attribute
            self.coll = self.collection
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def insert(self, doc):
        d = dict(doc)
        d.setdefault('createdAt', datetime.now(timezone.utc))
        return self.collection.insert_one(d)
