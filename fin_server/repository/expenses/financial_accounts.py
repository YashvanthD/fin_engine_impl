from datetime import datetime, timezone


class FinancialAccountsRepository:
    def __init__(self, db):
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

