from typing import Optional, Dict, Any
from fin_server.utils.time_utils import get_time_date_dt

class TransactionDTO:
    def __init__(self, transaction_id: Optional[str], tx_type: str, subtype: Optional[str], amount: Optional[float], currency: Optional[str], account_key: Optional[str], pond_id: Optional[str], species: Optional[str], related_id: Optional[str], creditor: Optional[str], debited: Optional[str], payment_method: Optional[str], invoice_no: Optional[str], gst: Optional[float], tax: Optional[float], recorded_by: Optional[str], status: Optional[str], metadata: Dict[str, Any] = None, created_at: Optional[str] = None):
        self.transaction_id = transaction_id
        self.type = tx_type
        self.subtype = subtype
        self.amount = float(amount) if amount is not None else None
        self.currency = currency or 'INR'
        self.account_key = account_key
        self.pond_id = pond_id
        self.species = species
        self.related_id = related_id
        self.creditor = creditor
        self.debited = debited
        self.payment_method = payment_method
        self.invoice_no = invoice_no
        self.gst = float(gst) if gst is not None else None
        self.tax = float(tax) if tax is not None else None
        self.recorded_by = recorded_by
        self.status = status or 'posted'
        self.metadata = metadata or {}
        self.created_at = created_at or get_time_date_dt(include_time=True).isoformat()

    @classmethod
    def from_request(cls, payload: Dict[str, Any]):
        return cls(
            transaction_id=payload.get('transaction_id') or payload.get('transactionId') or payload.get('tx_id'),
            tx_type=payload.get('type') or payload.get('tx_type') or payload.get('transaction_type') or 'expense',
            subtype=payload.get('subtype') or payload.get('category'),
            amount=payload.get('amount') or payload.get('total_amount') or payload.get('totalAmount'),
            currency=payload.get('currency'),
            account_key=payload.get('account_key') or payload.get('accountKey'),
            pond_id=payload.get('pond_id') or payload.get('pondId') or payload.get('pond'),
            species=payload.get('species'),
            related_id=payload.get('related_id') or payload.get('sampling_id') or payload.get('stock_id'),
            creditor=payload.get('creditor') or payload.get('vendor'),
            debited=payload.get('debited'),
            payment_method=payload.get('payment_method') or payload.get('paymentMethod'),
            invoice_no=payload.get('invoice_no') or payload.get('invoiceNo'),
            gst=payload.get('gst'),
            tax=payload.get('tax'),
            recorded_by=payload.get('recorded_by') or payload.get('recordedBy') or payload.get('user_key'),
            status=payload.get('status'),
            metadata=payload.get('metadata') or payload.get('extra') or {}
        )

    def to_db_doc(self) -> Dict[str, Any]:
        doc = {
            'transaction_id': self.transaction_id,
            'type': self.type,
            'subtype': self.subtype,
            'amount': self.amount,
            'currency': self.currency,
            'account_key': self.account_key,
            'pond_id': self.pond_id,
            'species': self.species,
            'related_id': self.related_id,
            'creditor': self.creditor,
            'debited': self.debited,
            'payment_method': self.payment_method,
            'invoice_no': self.invoice_no,
            'gst': self.gst,
            'tax': self.tax,
            'recorded_by': self.recorded_by,
            'status': self.status,
            'metadata': self.metadata,
            'created_at': self.created_at
        }
        # remove None values
        return {k: v for k, v in doc.items() if v is not None}

    def save(self, collection=None, repo=None, collection_name: str = 'transactions'):
        doc = self.to_db_doc()
        if repo is not None:
            try:
                coll = repo.get_collection(collection_name)
                return coll.insert_one(doc)
            except Exception:
                pass
        if collection is not None:
            return collection.insert_one(doc)
        from fin_server.repository.mongo_helper import get_collection
        coll = get_collection(collection_name)
        return coll.insert_one(doc)
