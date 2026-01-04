from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class AuditLogsRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(AuditLogsRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db):
        super().__init__(db)
        self.coll = db['audit_logs']

    def insert(self, doc):
        d = dict(doc)
        d.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(d)

