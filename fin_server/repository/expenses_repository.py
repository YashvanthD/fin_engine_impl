"""High-level ExpensesRepository that aggregates the domain repositories and exposes convenience methods.

This file provides a class `ExpensesRepository` that wraps the lower-level collection
repositories implemented in `repository/expenses/__init__.py` and offers domain
operations such as create_expense, post_payment, create_transaction_for_payment, etc.
"""
from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.expenses import (
    FinancialAccountsRepository, BankAccountsRepository, PaymentMethodsRepository,
    TransactionsRepository, PaymentsRepository, BankStatementsRepository, StatementLinesRepository,
    ReconciliationsRepository, ExpenseClaimsRepository, ApprovalsRepository, SettlementBatchesRepository,
    AuditLogsRepository
)
from datetime import datetime, timezone


class ExpensesRepository(BaseRepository):
    def __init__(self, db):
        super().__init__(db)
        self.fin_accounts = FinancialAccountsRepository(db)
        self.bank_accounts = BankAccountsRepository(db)
        self.payment_methods = PaymentMethodsRepository(db)
        self.transactions = TransactionsRepository(db)
        self.payments = PaymentsRepository(db)
        self.bank_statements = BankStatementsRepository(db)
        self.statement_lines = StatementLinesRepository(db)
        self.reconciliations = ReconciliationsRepository(db)
        self.expense_claims = ExpenseClaimsRepository(db)
        self.approvals = ApprovalsRepository(db)
        self.settlement_batches = SettlementBatchesRepository(db)
        self.audit_logs = AuditLogsRepository(db)
        self.db = db

    # Expense CRUD: store flexible schema in `expenses` collection
    def create_expense(self, expense_doc):
        coll = self.db['expenses']
        doc = dict(expense_doc)
        doc.setdefault('status', 'draft')
        doc.setdefault('created_at', datetime.now(timezone.utc))
        res = coll.insert_one(doc)
        return res.inserted_id

    def find_expenses(self, query=None, limit=100):
        coll = self.db['expenses']
        return list(coll.find(query or {}).limit(limit))

    def find_expense(self, q):
        coll = self.db['expenses']
        return coll.find_one(q)

    def update_expense(self, q, sets):
        coll = self.db['expenses']
        return coll.update_one(q, {'$set': sets})

    # Payments: create payment record and optionally create transaction
    def create_payment_and_transaction(self, payment_doc, tx_doc=None):
        # This method should ideally be wrapped in a MongoDB multi-doc transaction
        payments_coll = self.db['payments']
        tx_coll = self.db['transactions']
        payment_doc = dict(payment_doc)
        payment_doc.setdefault('status', 'initiated')
        payment_doc.setdefault('created_at', datetime.now(timezone.utc))
        payment_res = payments_coll.insert_one(payment_doc)
        payment_id = payment_res.inserted_id
        tx_id = None
        if tx_doc:
            tx_doc = dict(tx_doc)
            tx_doc.setdefault('created_at', datetime.now(timezone.utc))
            tx_doc_res = tx_coll.insert_one(tx_doc)
            tx_id = tx_doc_res.inserted_id
            # Link payment -> transaction
            payments_coll.update_one({'_id': payment_id}, {'$set': {'transaction_id': tx_id}})

        # Post-create bookkeeping: update bank account balance and add statement line
        try:
            # Resolve bank account from payment_doc: try common field names
            bank_account_id = payment_doc.get('bankAccountId') or payment_doc.get('bank_account_id') or (payment_doc.get('metadata') or {}).get('bank_account_id')
            amount = float(payment_doc.get('amount') or 0)
            # Determine direction: default 'out' (org paid out), 'in' increases balance
            direction = (payment_doc.get('direction') or payment_doc.get('type') or 'out').lower()
            if bank_account_id and amount:
                # update bank account balance (collection may be via repo)
                try:
                    bank_acc_repo = BankAccountsRepository(self.db)
                    coll = getattr(bank_acc_repo, 'collection', bank_acc_repo)
                    if direction in ('in', 'credit'):
                        coll.update_one({'_id': bank_account_id}, {'$inc': {'balance': float(amount)}})
                    else:
                        coll.update_one({'_id': bank_account_id}, {'$inc': {'balance': -float(amount)}})
                except Exception:
                    try:
                        coll = self.db['bank_accounts']
                        if direction in ('in', 'credit'):
                            coll.update_one({'_id': bank_account_id}, {'$inc': {'balance': float(amount)}})
                        else:
                            coll.update_one({'_id': bank_account_id}, {'$inc': {'balance': -float(amount)}})
                    except Exception:
                        pass

                # insert a passbook-style statement line (use repository API when present)
                try:
                    sl_repo = getattr(self, 'statement_lines', None)
                    ref = {'type': 'payment', 'id': payment_id}
                    if sl_repo and hasattr(sl_repo, 'append_line'):
                        sl_repo.append_line(bank_account_id, amount=amount, currency=payment_doc.get('currency', 'INR'), direction=direction, reference=ref, transaction_id=tx_id, created_at=datetime.now(timezone.utc))
                    else:
                        sl_coll = self.db['statement_lines']
                        stmt = {
                            'bank_account_id': bank_account_id,
                            'amount': amount,
                            'currency': payment_doc.get('currency', 'INR'),
                            'direction': direction,
                            'reference': ref,
                            'transaction_id': tx_id,
                            'created_at': datetime.now(timezone.utc)
                        }
                        sl_coll.insert_one(stmt)
                except Exception:
                    pass
        except Exception:
            # ensure failure here does not break the main flow
            pass

    # Simple reconciliation helper: match statement_lines by externalRef
    def reconcile_by_external_ref(self, bank_account_id, external_ref):
        # find statement lines with external_ref and payments with matching gateway ref
        sl = list(self.db['statement_lines'].find({'bank_account_id': bank_account_id, 'external_ref': external_ref}))
        matches = []
        for line in sl:
            payment = self.db['payments'].find_one({'external_gateway_ref': external_ref})
            if payment:
                # mark matched
                self.db['statement_lines'].update_one({'_id': line['_id']}, {'$set': {'matched_to': {'type': 'payment', 'id': payment['_id']}}})
                matches.append((line, payment))
        return matches

    def insert_audit(self, doc):
        return self.audit_logs.insert(doc)


def create_expenses_repository(db):
    return ExpensesRepository(db)
