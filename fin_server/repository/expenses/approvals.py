from datetime import datetime, timezone

from pymongo.synchronous.database import Database

from fin_server.repository.base_repository import BaseRepository


class ApprovalsRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="approvals"):
        if cls._instance is None:
            cls._instance = super(ApprovalsRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db, collection_name="approvals"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            try:
                self.collection.create_index([('ref_type', 1), ('ref_id', 1)], name='approvals_ref')
            except Exception:
                pass
            self._initialized = True

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('created_at', datetime.now(timezone.utc))
        return self.collection.insert_one(doc)
