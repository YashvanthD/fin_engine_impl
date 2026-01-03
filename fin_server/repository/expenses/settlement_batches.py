from datetime import datetime, timezone


class SettlementBatchesRepository:
    def __init__(self, db):
        self.coll = db['settlement_batches']

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

