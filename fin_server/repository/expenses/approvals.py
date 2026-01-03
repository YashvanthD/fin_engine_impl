from datetime import datetime, timezone


class ApprovalsRepository:
    def __init__(self, db):
        self.coll = db['approvals']
        try:
            self.coll.create_index([('refType', 1), ('refId', 1)], name='approvals_ref')
        except Exception:
            pass

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

