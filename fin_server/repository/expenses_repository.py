from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.utils.time_utils import get_time_date_dt

class ExpensesRepository(BaseRepository):
    def __init__(self, db=None, collection_name="expenses"):
        self.collection_name = collection_name
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        # Accept flexible keys and normalize into a canonical expense document
        doc = (data or {}).copy()
        # Normalize amount field
        amt_keys = ['amount', 'amt', 'value', 'total_amount', 'totalAmount']
        amount = None
        for k in amt_keys:
            if k in doc and doc.get(k) not in (None, ''):
                try:
                    amount = float(doc.get(k))
                except Exception:
                    try:
                        amount = float(str(doc.get(k)).replace(',', ''))
                    except Exception:
                        amount = None
                break
        if amount is not None:
            doc['amount'] = amount
        # Currency
        if 'currency' not in doc:
            doc['currency'] = doc.get('currency') or 'INR'
        # Expense type/category
        if 'type' not in doc:
            # accept expense_type or category
            doc['type'] = doc.get('expense_type') or doc.get('category') or 'expense'
        if 'category' not in doc:
            doc['category'] = doc.get('category') or doc.get('type')
        # Creditor / Debited
        if 'creditor' not in doc:
            doc['creditor'] = doc.get('credited_to') or doc.get('creditor') or None
        if 'debited' not in doc:
            doc['debited'] = doc.get('debited_to') or doc.get('debited') or None
        # Transaction id
        if 'transaction_id' not in doc:
            doc['transaction_id'] = doc.get('transactionId') or doc.get('tx_id') or doc.get('transaction_id') or None
        # GST / tax
        if 'gst' not in doc and doc.get('gst') is None:
            try:
                if 'gst' in doc:
                    doc['gst'] = float(doc['gst'])
            except Exception:
                pass
        if 'tax' not in doc and doc.get('tax') is None:
            try:
                if 'tax' in doc:
                    doc['tax'] = float(doc['tax'])
            except Exception:
                pass
        # Payment and invoice metadata
        if 'payment_method' not in doc:
            doc['payment_method'] = doc.get('paymentMethod') or doc.get('payment_method')
        if 'invoice_no' not in doc:
            doc['invoice_no'] = doc.get('invoiceNo') or doc.get('invoice_no')
        if 'vendor' not in doc:
            doc['vendor'] = doc.get('vendor')
        # Timestamps and bookkeeping
        doc['created_at'] = get_time_date_dt(include_time=True)
        # If possible, create a transaction ledger record and store only a reference
        try:
            from fin_server.repository.transactions_repository import TransactionsRepository
            tr = TransactionsRepository()
            tx_payload = {
                'transaction_id': doc.get('transaction_id') or doc.get('transactionId') or doc.get('tx_id'),
                'type': 'expense',
                'subtype': doc.get('category') or doc.get('type'),
                'amount': doc.get('amount'),
                'currency': doc.get('currency'),
                'account_key': doc.get('account_key'),
                'pond_id': doc.get('pond_id'),
                'species': doc.get('species'),
                'creditor': doc.get('creditor'),
                'debited': doc.get('debited'),
                'payment_method': doc.get('payment_method'),
                'invoice_no': doc.get('invoice_no'),
                'gst': doc.get('gst'),
                'tax': doc.get('tax'),
                'recorded_by': doc.get('recorded_by')
            }
            # create transaction ledger entry
            try:
                tx_res = tr.create_transaction(tx_payload)
                tx_id = getattr(tx_res, 'inserted_id', None)
            except Exception:
                tx_res = tr.create(tx_payload)
                tx_id = getattr(tx_res, 'inserted_id', None)
            # attach reference to expense and remove duplicated ledger fields
            if tx_id is not None:
                doc['transaction_ref'] = str(tx_id)
            # remove duplicated ledger fields from expense to keep it lightweight
            for k in ('account_key', 'pond_id', 'species', 'type', 'category', 'transaction_id', 'transactionId', 'tx_id', 'payment_method', 'paymentMethod', 'gst', 'tax', 'creditor', 'debited'):
                if k in doc:
                    doc.pop(k, None)
        except Exception:
            # TransactionsRepository not available or failed — fall back to inserting expense only
            pass
        # Allow caller to pass recorded_by/account_key/pond_id etc.
        try:
            return self.collection.insert_one(doc)
        except Exception:
            # In failure, raise so caller can fallback if needed
            raise

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = get_time_date_dt(include_time=True)
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)
