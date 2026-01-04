from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class BankStatementsRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="bank_statements"):
        if cls._instance is None:
            cls._instance = super(BankStatementsRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="bank_statements"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            self._initialized = True

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('imported_at', datetime.now(timezone.utc))
        return self.collection.insert_one(doc)

    def find_one(self, q):
        return self.collection.find_one(q)


class StatementLinesRepository:
    def __init__(self, db):
        # Keep a reference to the DB and coll so we can update bank_accounts too
        self.db = db
        self.coll = db['statement_lines']
        try:
            self.coll.create_index([('bank_account_id', 1), ('created_at', 1)], name='stmt_bank_date')
        except Exception:
            pass

    def insert_many(self, lines):
        if not lines:
            return None
        now = datetime.now(timezone.utc)
        for l in lines:
            l.setdefault('created_at', now)
        return self.coll.insert_many(lines)

    def find(self, q=None, limit=100):
        return list(self.coll.find(q or {}).limit(limit))

    def append_line(self, bank_account_id, amount: float, currency: str = 'INR', direction: str = 'out', reference: dict = None, transaction_id: any = None, created_at=None):
        """Append a statement line (passbook entry) for the given bank account.

        - Computes the running balance using the last statement line (if any).
        - Updates the bank_accounts.balance to reflect the new balance.
        - Inserts a new statement_lines document with the resulting balance.

        Returns the inserted_id and the new balance.
        """
        now = created_at or datetime.now(timezone.utc)
        # normalize direction
        dir_norm = (direction or 'out').lower()
        delta = float(amount or 0)
        if dir_norm not in ('in', 'credit'):
            delta = -delta

        # Find latest statement for this bank account to derive previous balance
        prev_stmt = self.coll.find({'bank_account_id': bank_account_id}).sort('created_at', -1).limit(1)
        prev_list = list(prev_stmt)
        prev_balance = 0.0
        if prev_list:
            try:
                prev_balance = float(prev_list[0].get('balance', 0) or 0)
            except Exception:
                prev_balance = 0.0
        new_balance = prev_balance + delta

        stmt = {
            'bank_account_id': bank_account_id,
            'amount': float(amount or 0),
            'currency': currency,
            'direction': dir_norm,
            'balance': float(new_balance),
            'reference': reference or {},
            'transaction_id': transaction_id,
            'created_at': now
        }

        res = self.coll.insert_one(stmt)

        # Update bank_accounts balance (best-effort)
        try:
            bank_coll = self.db['bank_accounts']
            # Try update by _id first, fallback to account_key matching
            upd = bank_coll.update_one({'_id': bank_account_id}, {'$set': {'balance': float(new_balance)}})
            if upd.matched_count == 0:
                # fallback: try account_key or account_number
                bank_coll.update_one({'account_key': bank_account_id, 'type': 'organization'}, {'$set': {'balance': float(new_balance)}})
        except Exception:
            try:
                # last resort: try a generic update that won't crash
                self.db['bank_accounts'].update_one({'account_key': bank_account_id}, {'$set': {'balance': float(new_balance)}})
            except Exception:
                pass

        return getattr(res, 'inserted_id', None), new_balance
