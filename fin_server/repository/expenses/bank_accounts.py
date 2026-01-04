from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class BankAccountsRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="bank_accounts"):
        if cls._instance is None:
            cls._instance = super(BankAccountsRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="bank_accounts"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            try:
                self.collection.create_index([('external_id', 1)], unique=False, name='bank_ext')
            except Exception:
                pass
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.collection.insert_one(doc)

    def find_one(self, q):
        return self.collection.find_one(q)
