from bson.decimal128 import Decimal128
from datetime import datetime, timezone

from fin_server.repository.base_repository import BaseRepository


class TransactionsRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db)
        self.coll = db['transactions']
        try:
            self.coll.create_index([('postingDate', 1)], name='tx_posting_date')
        except Exception:
            pass

    def create_transaction(self, tx_doc):
        """Create a journal transaction ensuring debits == credits.
        tx_doc expected shape: { occurredAt, postingDate, description, entries: [ { accountId, debit, credit, refType, refId } ], amountLocal, currency }
        Returns inserted_id.
        """
        entries = tx_doc.get('entries') or []
        # Sum debits and credits using Decimal128 arithmetic by converting to Python decimals
        from decimal import Decimal
        total_debit = Decimal('0')
        total_credit = Decimal('0')
        for e in entries:
            # allow Decimal128 or numeric strings
            d = e.get('debit')
            c = e.get('credit')
            try:
                if isinstance(d, Decimal128):
                    total_debit += Decimal(str(d.to_decimal()))
                elif d is not None:
                    total_debit += Decimal(str(d))
            except Exception:
                pass
            try:
                if isinstance(c, Decimal128):
                    total_credit += Decimal(str(c.to_decimal()))
                elif c is not None:
                    total_credit += Decimal(str(c))
            except Exception:
                pass
        if total_debit != total_credit:
            raise ValueError('Transaction not balanced: debits != credits')
        tx_doc = dict(tx_doc)
        tx_doc.setdefault('createdAt', datetime.now(timezone.utc))
        res = self.coll.insert_one(tx_doc)
        return res.inserted_id

    def find(self, q=None, limit=100):
        return list(self.coll.find(q or {}).limit(limit))

    def find_one(self, q):
        return self.coll.find_one(q)

