from datetime import datetime, timezone

from pymongo.synchronous.database import Database

from fin_server.repository.base_repository import BaseRepository


class ApprovalsRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(ApprovalsRepository, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, db):
        super().__init__(db)
        self.coll = db['approvals']
        try:
            self.coll.create_index([('refType', 1), ('refId', 1)], name='approvals_ref')
        except Exception:
            pass

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

