from datetime import datetime, timezone


class ExpenseClaimsRepository:
    def __init__(self, db):
        self.coll = db['expense_claims']
        try:
            self.coll.create_index([('claimantId', 1), ('status', 1)], name='claims_claimant_status')
        except Exception:
            pass

    def create(self, doc):
        doc = dict(doc)
        doc.setdefault('createdAt', datetime.now(timezone.utc))
        return self.coll.insert_one(doc)

