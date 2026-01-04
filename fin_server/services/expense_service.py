import logging
from typing import Any, Dict, Optional
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.utils.normalizers import normalize_document_fields

logger = logging.getLogger(__name__)


def build_expense_from_sampling(pond_id: str, account_key: str, total_amount: float, dto: Any, extra: Dict[str, Any] = None) -> Dict[str, Any]:
    """Build an expense document from sampling/buy context.

    normalizes keys and sets sensible defaults; returns a plain dict ready for
    insertion via ExpensesRepository.create_expense or direct insert.
    """
    extra = extra or {}
    doc = {
        'pond_id': pond_id,
        'amount': float(total_amount) if total_amount is not None else None,
        'currency': extra.get('currency') or 'INR',
        'payment_method': extra.get('payment_method') or extra.get('paymentMethod') or 'cash',
        'notes': extra.get('notes') or getattr(dto, 'notes', None),
        'recorded_by': getattr(dto, 'recordedBy', None),
        'account_key': account_key,
        'category': extra.get('category') or 'asset',
        'action': extra.get('action') or 'buy',
        'type': extra.get('type') or 'fish',
        'metadata': {}
    }
    # Promote a few nice metadata fields
    for k in ('species', 'sampling_id', 'batch_id', 'fish_age_in_month'):
        v = extra.get(k) or getattr(dto, k, None)
        if v is not None:
            doc['metadata'][k] = v
    # strip empty metadata and None values
    if not doc['metadata']:
        doc.pop('metadata')
    doc = {k: v for k, v in doc.items() if v is not None}
    # normalize keys (camelCase -> snake_case) to be safe
    return normalize_document_fields(doc)


def create_expense_with_repo(expense_doc: Dict[str, Any], expenses_repo: Any) -> Optional[Any]:
    """Create an expense using the provided expenses_repo. Returns inserted id or None.

    Prefers high-level API `create_expense`, falls back to `create` or collection insert.
    """
    try:
        if expenses_repo is None:
            raise RuntimeError('No expenses_repo provided')
        if hasattr(expenses_repo, 'create_expense'):
            return expenses_repo.create_expense(expense_doc)
        if hasattr(expenses_repo, 'create'):
            return expenses_repo.create(expense_doc)
        if hasattr(expenses_repo, 'insert_one'):
            res = expenses_repo.insert_one(expense_doc)
            return getattr(res, 'inserted_id', None)
        # last resort: try attribute 'db' collection
        if hasattr(expenses_repo, 'db') and hasattr(expenses_repo.db, 'expenses'):
            coll = expenses_repo.db['expenses']
            res = coll.insert_one(expense_doc)
            return getattr(res, 'inserted_id', None)
    except Exception:
        logger.exception('Failed to create expense via repo')
        raise
    return None

