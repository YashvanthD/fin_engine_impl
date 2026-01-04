from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class ExpenseClaimsRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(ExpenseClaimsRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db):
        super().__init__(db)
        self.coll = db['expense_claims']
        try:
            self.coll.create_index([('claimantId', 1), ('status', 1)], name='claims_claimant_status')
        except Exception:
            pass

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

