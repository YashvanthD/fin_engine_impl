from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class PaymentsRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="payments"):
        if cls._instance is None:
            cls._instance = super(PaymentsRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="payments"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            try:
                self.collection.create_index([('paymentRef', 1)], unique=False, name='payments_ref')
            except Exception:
                pass
            self._initialized = True

    def create_payment(self, payment_doc):
        payment = dict(payment_doc)
        payment.setdefault('status', 'initiated')
        payment.setdefault('createdAt', datetime.now(timezone.utc))
        return self.collection.insert_one(payment)

    def update(self, q, updates):
        return self.collection.update_one(q, {'$set': updates})

    def find_one(self, q):
        return self.collection.find_one(q)
