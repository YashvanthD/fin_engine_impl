from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class FinancialAccountsRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(FinancialAccountsRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db):
        super().__init__(db)
        self.coll = db['financial_accounts']
        # ensure indexes
        try:
            self.coll.create_index([('code', 1)], unique=True, name='fa_code')
        except Exception:
            pass

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

    def find(self, q=None, limit=100):
        return list(self.coll.find(q or {}).limit(limit))

    def find_one(self, q):
        return self.coll.find_one(q)

