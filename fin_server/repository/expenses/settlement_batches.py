from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class SettlementBatchesRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="settlement_batches"):
        if cls._instance is None:
            cls._instance = super(SettlementBatchesRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="settlement_batches"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('created_at', datetime.now(timezone.utc))
        return self.collection.insert_one(doc)
