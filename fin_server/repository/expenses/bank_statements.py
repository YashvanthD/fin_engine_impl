from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class BankStatementsRepository(BaseRepository):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(BankStatementsRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db):
        super().__init__(db)
        self.coll = db['bank_statements']

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('importedAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

    def find_one(self, q):
        return self.coll.find_one(q)


class StatementLinesRepository:
    def __init__(self, db):
        self.coll = db['statement_lines']
        try:
            self.coll.create_index([('bankAccountId', 1), ('recordedAt', 1)], name='stmt_bank_date')
        except Exception:
            pass

    def insert_many(self, lines):
        if not lines:
            return None
        now = datetime.now(timezone.utc)
        for l in lines:
            l.setdefault('createdAt', now)
        return self.coll.insert_many(lines)

    def find(self, q=None, limit=100):
        return list(self.coll.find(q or {}).limit(limit))

