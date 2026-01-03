from datetime import datetime, timezone


class AuditLogsRepository:
    def __init__(self, db):
        self.coll = db['audit_logs']

    def insert(self, doc):
        d = dict(doc)
        d.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(d)

