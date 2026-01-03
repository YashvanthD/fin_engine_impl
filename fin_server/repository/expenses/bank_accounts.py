from datetime import datetime, timezone


class BankAccountsRepository:
    def __init__(self, db):
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

