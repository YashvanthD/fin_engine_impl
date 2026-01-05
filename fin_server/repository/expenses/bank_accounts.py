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
        doc.setdefault('created_at', datetime.now(timezone.utc))
        return self.collection.insert_one(doc)

    def find_one(self, q):
        return self.collection.find_one(q)

    def get_by_account_key(self, account_key: str):
        try:
            return self.collection.find_one({'account_key': account_key})
        except Exception:
            return None

    def adjust_balance(self, account_selector, delta: float):
        """Adjust balance by delta. account_selector can be _id or account_key dict/value."""
        try:
            # If caller passes a dict, use it as query
            if isinstance(account_selector, dict):
                q = account_selector
            else:
                # try _id first
                q = {'_id': account_selector}
            res = self.collection.update_one(q, {'$inc': {'balance': float(delta)}})
            if getattr(res, 'matched_count', 0) == 0:
                # fallback to account_key
                self.collection.update_one({'account_key': account_selector}, {'$inc': {'balance': float(delta)}})
        except Exception:
            # best-effort
            pass
