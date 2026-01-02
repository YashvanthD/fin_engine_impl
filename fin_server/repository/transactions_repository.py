from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.utils.time_utils import get_time_date_dt

class TransactionsRepository(BaseRepository):
    def __init__(self, db=None, collection_name='transactions'):
        self.collection_name = collection_name
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        doc = (data or {}).copy()
        # normalize transaction id
        if 'transaction_id' not in doc:
            doc['transaction_id'] = doc.get('transactionId') or doc.get('tx_id') or None
        if 'created_at' not in doc:
            doc['created_at'] = get_time_date_dt(include_time=True)
        # support optional session via key 'session' in caller-provided data (or pass session param)
        return self.collection.insert_one(doc)

    def create_transaction(self, payload: dict):
        """Normalize a generic transaction payload and insert into transactions collection.

        Accepts flexible keys (camelCase/snake_case) and returns the insert result.
        """
        doc = (payload or {}).copy()
        # canonicalize keys
        if 'transaction_id' not in doc:
            doc['transaction_id'] = doc.get('transactionId') or doc.get('tx_id') or None
        if 'type' not in doc:
            doc['type'] = doc.get('tx_type') or doc.get('transaction_type') or doc.get('type') or 'expense'
        if 'subtype' not in doc:
            doc['subtype'] = doc.get('category') or doc.get('subtype')
        # amount
        if 'amount' not in doc and 'totalAmount' in doc:
            try:
                doc['amount'] = float(doc.get('totalAmount'))
            except Exception:
                doc['amount'] = doc.get('totalAmount')
        # currency
        if 'currency' not in doc:
            doc['currency'] = doc.get('currency') or 'INR'
        # timestamps
        if 'created_at' not in doc:
            doc['created_at'] = get_time_date_dt(include_time=True)
        if 'created_at' not in doc:
            doc['created_at'] = get_time_date_dt(include_time=True)
        # allow caller to pass session via payload['_session'] or session param in future
        return self.create(doc)

    def create_from_expense(self, expense_doc: dict, related_id: str = None):
        """Build and insert a transaction record from an expense document.

        Returns insert result or raises on failure.
        """
        if not expense_doc:
            raise ValueError('expense_doc is required')
        tx = {
            'transaction_id': expense_doc.get('transaction_id') or expense_doc.get('transactionId') or expense_doc.get('tx_id'),
            'type': 'expense',
            'subtype': expense_doc.get('category') or expense_doc.get('type'),
            'amount': expense_doc.get('amount'),
            'currency': expense_doc.get('currency') or 'INR',
            'account_key': expense_doc.get('account_key'),
            'pond_id': expense_doc.get('pond_id'),
            'species': expense_doc.get('species'),
            'related_id': related_id,
            'creditor': expense_doc.get('creditor'),
            'debited': expense_doc.get('debited'),
            'payment_method': expense_doc.get('payment_method'),
            'invoice_no': expense_doc.get('invoice_no'),
            'gst': expense_doc.get('gst'),
            'tax': expense_doc.get('tax'),
            'recorded_by': expense_doc.get('recorded_by')
        }
        return self.create_transaction(tx)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = get_time_date_dt(include_time=True)
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)
