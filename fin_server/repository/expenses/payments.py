from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class PaymentsRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(PaymentsRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db):
        super().__init__(db)
        self.coll = db['payments']
        try:
            self.coll.create_index([('paymentRef', 1)], unique=False, name='payments_ref')
        except Exception:
            pass

    def create_payment(self, payment_doc):
        payment = dict(payment_doc)
        payment.setdefault('status', 'initiated')
        payment.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(payment)

    def update(self, q, updates):
        return self.coll.update_one(q, {'$set': updates})

    def find_one(self, q):
        return self.coll.find_one(q)

