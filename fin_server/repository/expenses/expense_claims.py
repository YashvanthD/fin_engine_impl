from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class ExpenseClaimsRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="expense_claims"):
        if cls._instance is None:
            cls._instance = super(ExpenseClaimsRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="expense_claims"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            try:
                self.collection.create_index([('claimant_id', 1), ('status', 1)], name='claims_claimant_status')
            except Exception:
                pass
            self._initialized = True

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('created_at', datetime.now(timezone.utc))
        return self.collection.insert_one(doc)
