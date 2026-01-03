from datetime import datetime, timezone


class ReconciliationsRepository:
    def __init__(self, db):
        self.coll = db['reconciliations']

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

