from datetime import datetime, timezone


class PaymentMethodsRepository:
    def __init__(self, db):
        self.coll = db['payment_methods']
        try:
            self.coll.create_index([('ownerId', 1), ('ownerType', 1)], name='pm_owner')
        except Exception:
            pass

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

    def find_one(self, q):
        return self.coll.find_one(q)

