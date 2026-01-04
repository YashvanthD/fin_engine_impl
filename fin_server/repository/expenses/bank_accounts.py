from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class BankAccountsRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(BankAccountsRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db):
        super().__init__(db)
        self.coll = db['bank_accounts']
        try:
            self.coll.create_index([('external_id', 1)], unique=False, name='bank_ext')
        except Exception:
            pass

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

    def find_one(self, q):
        return self.coll.find_one(q)

