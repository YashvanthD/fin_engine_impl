import logging
from typing import Any, Dict, Optional
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.utils.normalizers import normalize_document_fields
from fin_server.repository.mongo_helper import get_collection
import json
import os
from functools import lru_cache

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

STATUS_CHOICES = {'DRAFT', 'INITIATED', 'FAILED', 'SUCCESS', 'PENDING', 'INPROGRESS', 'FINALIZED', 'CANCELLED'}


@lru_cache(maxsize=1)
def _load_expense_catalog() -> Dict[str, Any]:
    path = os.path.join(PROJECT_ROOT, 'data', 'expesnses.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _flatten_categories(catalog: Dict[str, Any]) -> set:
    out = set()
    for k, v in catalog.items():
        out.add(k.lower())
        if isinstance(v, dict):
            for k2 in v.keys():
                out.add(k2.lower())
                # one more level deep
                sub = v.get(k2) or {}
                if isinstance(sub, dict):
                    for k3 in sub.keys():
                        out.add(k3.lower())
    return out


def normalize_category(cat: Optional[str], default: str = 'Operational') -> str:
    if not cat:
        return default
    cat_norm = str(cat).strip()
    catalog = _load_expense_catalog()
    flat = _flatten_categories(catalog)
    # direct match case-insensitive
    if cat_norm.lower() in flat:
        # return title-cased version for readability
        return cat_norm
    # try to match top-level keys heuristically
    for top in catalog.keys():
        if cat_norm.lower() in top.lower() or top.lower() in cat_norm.lower():
            return top
    return default


def normalize_status(status: Optional[str], default: str = 'DRAFT') -> str:
    if not status:
        return default
    s = str(status).strip().upper()
    return s if s in STATUS_CHOICES else default


def normalize_type(t: Optional[str], default: str = 'other') -> str:
    if not t:
        return default
    tt = str(t).strip().lower()
    # common domain types
    known = {'pond', 'fish', 'maintenance', 'asset', 'service', 'labor', 'feed', 'expense', 'payment'}
    return tt if tt in known else default


logger = logging.getLogger(__name__)


def build_expense_from_sampling(pond_id: str, account_key: str, total_amount: float, dto: Any, extra: Dict[str, Any] = None) -> Dict[str, Any]:
    """Build an expense document from sampling/buy context.

    Normalizes keys and sets sensible defaults; returns a plain dict ready for
    insertion via ExpensesRepository.create_expense or direct insert. Important: do
    not place domain links like `pond_id` at the top level of the expense - keep
    them under `metadata` to keep expenses generalized for any accounting activity.
    """
    extra = extra or {}
    # Build metadata that links this expense to domain objects (pond, sampling, stock)
    metadata = {}
    if pond_id:
        metadata['pond_id'] = pond_id
    # sampling_id and stock_id are promoted below
    for k in ('species', 'sampling_id', 'batch_id', 'fish_age_in_month', 'stock_id'):
        v = extra.get(k) or getattr(dto, k, None)
        if v is not None:
            metadata[k] = v

    doc = {
        'amount': float(total_amount) if total_amount is not None else None,
        'currency': extra.get('currency') or 'INR',
        'payment_method': extra.get('payment_method') or extra.get('paymentMethod') or 'cash',
        'notes': extra.get('notes') or getattr(dto, 'notes', None),
        'recorded_by': getattr(dto, 'recordedBy', None),
        'account_key': account_key,
        'category': extra.get('category') or 'asset',
        'action': extra.get('action') or 'buy',
        'type': extra.get('type') or 'fish',
    }

    if metadata:
        doc['metadata'] = metadata

    # strip None values
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

        # Normalize key fields before persisting
        exp = dict(expense_doc)

        # --- Move domain links into metadata (keep expenses generic) ---
        meta = dict(exp.get('metadata') or {})
        # support several common top-level link names and canonicalize them into metadata
        link_fields = [
            ('pond_id', 'pond_id'), ('pondId', 'pond_id'), ('pond', 'pond_id'),
            ('sampling_id', 'sampling_id'), ('samplingId', 'sampling_id'), ('sampling', 'sampling_id'),
            ('stock_id', 'stock_id'), ('stockId', 'stock_id'), ('stock', 'stock_id'),
            ('species', 'species'), ('fish_id', 'species'), ('fishId', 'species')
        ]
        for src, dst in link_fields:
            if src in exp and exp.get(src) is not None:
                meta[dst] = exp.pop(src)
        if meta:
            exp['metadata'] = meta

        # category: map to a real-world category from catalog
        exp['category'] = normalize_category(exp.get('category'))
        exp['type'] = normalize_type(exp.get('type'))
        # status: normalize to uppercase standard statuses
        exp['status'] = normalize_status(exp.get('status'))

        # Business rule: payments made by cash should not remain in DRAFT.
        # If payment method indicates cash and status was left as DRAFT, default to SUCCESS.
        pm = exp.get('payment_method') or exp.get('paymentMethod') or exp.get('payment')
        if isinstance(pm, str) and 'cash' in pm.lower():
            if exp.get('status') == 'DRAFT':
                exp['status'] = 'SUCCESS'

        if hasattr(expenses_repo, 'create_expense'):
            return expenses_repo.create_expense(exp)
        if hasattr(expenses_repo, 'create'):
            return expenses_repo.create(exp)
        if hasattr(expenses_repo, 'insert_one'):
            res = expenses_repo.insert_one(exp)
            return getattr(res, 'inserted_id', None)
        # last resort: try attribute 'db' collection
        if hasattr(expenses_repo, 'db') and hasattr(expenses_repo.db, 'expenses'):
            coll = expenses_repo.db['expenses']
            res = coll.insert_one(exp)
            return getattr(res, 'inserted_id', None)
    except Exception:
        logger.exception('Failed to create expense via repo')
        raise
    return None


# ------------------------- Expense/Transaction helper API -------------------------
# These functions use the repository singletons (via get_collection) directly and
# are intentionally straightforward (no excessive error wrapping) so they are easy
# to call from route handlers like the DELETE pond flow.

# Transactions

def init_transaction(tx_doc: Dict[str, Any]) -> Any:
    """Create/initiate a transaction (journal entry) in the transactions collection.

    Expects tx_doc to contain balanced entries; this will call TransactionsRepository.create_transaction
    which validates debits==credits.
    Returns the inserted transaction id.
    """
    tx_repo = get_collection('transactions')
    # ensure createdAt
    tx = dict(tx_doc)
    tx.setdefault('createdAt', get_time_date_dt(include_time=True))
    return tx_repo.create_transaction(tx)


def update_transaction(tx_id: Any, sets: Dict[str, Any]) -> Any:
    """Update a transaction document by _id (or other selector if tx_id is a dict).

    If tx_id is a mapping, it is used directly as a query; otherwise it's treated as _id.
    Returns the raw update result from the collection.
    """
    tx_repo = get_collection('transactions')
    query = tx_id if isinstance(tx_id, dict) else {'_id': tx_id}
    return tx_repo.collection.update_one(query, {'$set': sets})


def delete_transaction(tx_id: Any) -> Any:
    """Delete a transaction by _id (or by query if a dict provided). Returns delete result."""
    tx_repo = get_collection('transactions')
    query = tx_id if isinstance(tx_id, dict) else {'_id': tx_id}
    return tx_repo.collection.delete_one(query)


# Expenses: create/init/update/delete helpers

def initiate_expense_for_pond(pond_id: str, account_key: str, amount: float, action: str = 'sell', expense_type: str = 'pond', notes: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None, payment_method: Optional[str] = None) -> Any:
    """Create an expense document for a pond-related action and mark it 'initiated'.

    Action and type are domain descriptors; the link to the pond is placed inside
    `metadata` to keep expense documents generalized for accounting.
    """
    expenses_repo = get_collection('expenses')
    meta = metadata.copy() if metadata else {}
    if pond_id:
        meta['pond_id'] = pond_id

    doc: Dict[str, Any] = {
        'account_key': account_key,
        'amount': float(amount) if amount is not None else None,
        'currency': 'INR',
        'payment_method': payment_method,
        'action': action,
        'type': normalize_type(expense_type),
        'status': normalize_status('initiated'),
        'notes': notes,
        'createdAt': get_time_date_dt(include_time=True),
    }
    if meta:
        doc['metadata'] = meta
    # normalize keys and persist via repository
    doc = normalize_document_fields(doc)
    return create_expense_with_repo(doc, expenses_repo)


def update_expense(expense_id: Any, sets: Dict[str, Any]) -> Any:
    """Generic expense update (by _id or by query dict). Returns update result."""
    expenses_repo = get_collection('expenses')
    query = expense_id if isinstance(expense_id, dict) else {'_id': expense_id}
    return expenses_repo.update_expense(query, sets)


def delete_expense(expense_id: Any) -> Any:
    """Delete an expense document by _id or query. Returns delete result."""
    expenses_repo = get_collection('expenses')
    coll = expenses_repo.db['expenses'] if hasattr(expenses_repo, 'db') else expenses_repo.collection
    query = expense_id if isinstance(expense_id, dict) else {'_id': expense_id}
    return coll.delete_one(query)


# Domain-specific updaters (convenience wrappers)

def update_expense_pond(expense_id: Any, sets: Dict[str, Any]) -> Any:
    """Update pond-related fields on an expense document."""
    return update_expense(expense_id, sets)


def update_expense_fish(expense_id: Any, sets: Dict[str, Any]) -> Any:
    """Update fish-related fields on an expense document."""
    return update_expense(expense_id, sets)


def update_expense_maintenance(expense_id: Any, sets: Dict[str, Any]) -> Any:
    """Update maintenance-related fields on an expense document."""
    return update_expense(expense_id, sets)


def update_cost_amounts_accounts(expense_id: Any, amount: Optional[float] = None, currency: Optional[str] = None, account_key: Optional[str] = None) -> Any:
    """Update cost/amount/account fields on an expense document."""
    sets: Dict[str, Any] = {}
    if amount is not None:
        sets['amount'] = float(amount)
    if currency is not None:
        sets['currency'] = currency
    if account_key is not None:
        sets['account_key'] = account_key
    if not sets:
        return None
    return update_expense(expense_id, sets)


# Convenience helpers to create/delete/update transactions+expenses together

def create_transaction_and_link_expense(tx_doc: Dict[str, Any], expense_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Create a transaction and an expense and link them (best-effort, no transaction wrapper).

    Returns dict with keys: transaction_id, expense_id
    """
    tx_id = init_transaction(tx_doc)
    expense_repo = get_collection('expenses')
    expense_id = create_expense_with_repo(expense_doc, expense_repo)
    # link expense -> transaction if possible
    if expense_id is not None and tx_id is not None:
        try:
            update_expense(expense_id, {'transaction_id': str(tx_id)})
        except Exception:
            logger.exception('Failed to link expense -> transaction')
    return {'transaction_id': tx_id, 'expense_id': expense_id}


def create_draft_transaction_for_pond(pond_id: str, account_key: str, amount: Optional[float] = None, description: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Any:
    """Create a draft transaction document for a pond deletion flow.

    This inserts a transaction document directly (bypassing create_transaction validation)
    and marks it as a draft so the UI/ops can review and add balanced entries later.
    Returns the inserted transaction id.
    """
    tx_repo = get_collection('transactions')
    tx_coll = tx_repo.collection if hasattr(tx_repo, 'collection') else tx_repo
    tx_doc: Dict[str, Any] = {
        'pond_id': pond_id,
        'account_key': account_key,
        'status': 'draft',
        'description': description,
        'amount': float(amount) if amount is not None else None,
        'createdAt': get_time_date_dt(include_time=True),
    }
    if metadata:
        tx_doc['metadata'] = metadata
    res = tx_coll.insert_one(tx_doc)
    return getattr(res, 'inserted_id', None)


def prepare_pond_deletion_financials(
    pond_id: str,
    account_key: str,
    pond_sale_amount: Optional[float] = None,
    fish_sale_amount: Optional[float] = None,
    maintenance_estimates: Optional[list] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepare draft financial artifacts when deleting a pond.

    - Creates a draft transaction (returns tx_id)
    - Creates an initiated expense for pond sale (asking user to confirm)
    - Creates expense for fish sale (if provided) — created as 'finalized' by default
    - Creates initiated maintenance expenses for each estimate provided

    Returns a summary with keys: transaction_id, pond_expense_id, fish_expense_id, maintenance_expense_ids
    """
    maintenance_estimates = maintenance_estimates or []

    # create draft transaction to group these operations
    total_estimated = 0.0
    if pond_sale_amount:
        total_estimated += float(pond_sale_amount)
    if fish_sale_amount:
        total_estimated += float(fish_sale_amount)
    for m in maintenance_estimates:
        try:
            total_estimated += float(m.get('amount', 0) or 0)
        except Exception:
            pass

    tx_id = create_draft_transaction_for_pond(pond_id=pond_id, account_key=account_key, amount=total_estimated, description=description or f'Pond deletion for {pond_id}')

    summary: Dict[str, Any] = {'transaction_id': tx_id, 'pond_expense_id': None, 'fish_expense_id': None, 'maintenance_expense_ids': []}

    # 1) Pond sale expense (initiated — user must mark)
    if pond_sale_amount is not None:
        pond_expense_doc = {
            'account_key': account_key,
            'amount': float(pond_sale_amount),
            'currency': 'INR',
            'action': 'sell',
            'type': 'pond',
            'status': 'initiated',
            'notes': f'Pond sale for {pond_id}',
            'createdAt': get_time_date_dt(include_time=True),
            'metadata': {'auto_created_by': 'prepare_pond_deletion', 'pond_id': pond_id}
        }
        pond_expense_id = create_expense_with_repo(normalize_document_fields(pond_expense_doc), get_collection('expenses'))
        summary['pond_expense_id'] = pond_expense_id
        # link to draft transaction if possible
        if pond_expense_id and tx_id:
            try:
                update_expense(pond_expense_id, {'transaction_id': str(tx_id)})
            except Exception:
                logger.exception('Failed to link pond expense to draft transaction')

    # 2) Fish sale expense (created as finalized record if amount provided)
    if fish_sale_amount is not None:
        fish_expense_doc = {
            'account_key': account_key,
            'amount': float(fish_sale_amount),
            'currency': 'INR',
            'action': 'sell',
            'type': 'fish',
            'status': 'finalized',
            'notes': f'Fish sale on pond {pond_id}',
            'createdAt': get_time_date_dt(include_time=True),
            'metadata': {'auto_created_by': 'prepare_pond_deletion', 'pond_id': pond_id}
        }
        fish_expense_id = create_expense_with_repo(normalize_document_fields(fish_expense_doc), get_collection('expenses'))
        summary['fish_expense_id'] = fish_expense_id
        if fish_expense_id and tx_id:
            try:
                update_expense(fish_expense_id, {'transaction_id': str(tx_id)})
            except Exception:
                logger.exception('Failed to link fish expense to draft transaction')

    # 3) Maintenance estimates -> create initiated expenses
    maintenance_ids = []
    for m in maintenance_estimates:
        amt = float(m.get('amount', 0) or 0)
        notes = m.get('notes') or m.get('note')
        meta = m.get('metadata') or {}
        # ensure pond link is in metadata
        meta = {**meta, 'auto_created_by': 'prepare_pond_deletion', 'pond_id': pond_id}
        maint_doc = {
            'account_key': account_key,
            'amount': amt,
            'currency': m.get('currency') or 'INR',
            'action': 'maintenance',
            'type': 'maintenance',
            'status': 'initiated',
            'notes': notes,
            'createdAt': get_time_date_dt(include_time=True),
            'metadata': meta
        }
        eid = create_expense_with_repo(normalize_document_fields(maint_doc), get_collection('expenses'))
        maintenance_ids.append(eid)
        if eid and tx_id:
            try:
                update_expense(eid, {'transaction_id': str(tx_id)})
            except Exception:
                logger.exception('Failed to link maintenance expense to draft transaction')

    summary['maintenance_expense_ids'] = maintenance_ids
    return summary


def find_expenses_for_sampling(sampling_id: Optional[str] = None, stock_id: Optional[str] = None, pond_id: Optional[str] = None):
    """Return list of expense docs related to a sampling/stock/pond."""
    expenses_repo = get_collection('expenses')
    coll = expenses_repo.db['expenses'] if hasattr(expenses_repo, 'db') else (getattr(expenses_repo, 'collection', expenses_repo))
    q = {}
    ors = []
    if sampling_id:
        ors.append({'sampling_id': sampling_id})
        ors.append({'metadata.sampling_id': sampling_id})
        ors.append({'metadata.stock_id': sampling_id})
    if stock_id:
        ors.append({'metadata.stock_id': stock_id})
    if pond_id:
        # Prefer metadata.pond_id, but keep fallback to top-level pond_id for compatibility
        ors.append({'metadata.pond_id': pond_id})
        ors.append({'pond_id': pond_id})
    if not ors:
        return []
    q['$or'] = ors
    return list(coll.find(q))


def mark_expense_cancelled(expense_id: Any, reason: Optional[str] = None):
    """Mark an expense as cancelled (status) and record reason."""
    updates = {'status': 'cancelled', 'updatedAt': get_time_date_dt(include_time=True)}
    if reason:
        updates['cancel_reason'] = reason
    return update_expense(expense_id, updates)


def handle_sampling_deletion(sampling_id: str):
    """When a sampling is deleted, cascade-update related finances and analytics:

    - find related expenses and mark cancelled (and delete/mark linked transactions)
    - decrement pond metadata counts
    - decrement fish current_stock
    - remove analytics batches and fish_activity entries referencing the sampling/stock

    Returns a summary dict describing actions taken.
    """
    summary = {
        'expenses_cancelled': [],
        'transactions_deleted': [],
        'ponds_updated': [],
        'fish_updated': [],
        'analytics_deleted': None,
        'activities_deleted': None
    }

    sampling_repo = get_collection('sampling')
    pond_repo = get_collection('pond')
    fish_repo = get_collection('fish')
    fish_analytics_repo = get_collection('fish_analytics')
    fish_activity_repo = get_collection('fish_activity')
    expenses_repo = get_collection('expenses')
    tx_repo = get_collection('transactions')

    # Load sampling doc
    samp = sampling_repo.find_one({'sampling_id': sampling_id}) or sampling_repo.find_one({'_id': sampling_id})
    if not samp:
        return {'error': 'sampling_not_found'}

    pond_id = samp.get('pond_id')
    stock_id = samp.get('stock_id') or (samp.get('extra') or {}).get('stock_id')
    species = samp.get('species')
    count = None
    try:
        # Determine count similar to perform_buy_sampling
        extra = samp.get('extra', {}) or {}
        if 'total_count' in extra:
            count = int(extra.get('total_count'))
        elif 'totalCount' in extra:
            count = int(extra.get('totalCount'))
        elif 'sampleSize' in samp:
            count = int(samp.get('sampleSize'))
    except Exception:
        count = None

    # 1) Find related expenses and cancel them
    related_expenses = find_expenses_for_sampling(sampling_id=sampling_id, stock_id=stock_id, pond_id=pond_id)
    for e in related_expenses:
        try:
            eid = e.get('_id')
            mark_expense_cancelled(eid, reason='Sampling deleted; automatic cancellation')
            summary['expenses_cancelled'].append(eid)
            # if linked transaction exists, delete it
            tx_ref = e.get('transaction_id') or e.get('transaction_ref') or e.get('transactionId')
            if tx_ref:
                try:
                    # try delete by id
                    delete_transaction(tx_ref)
                    summary['transactions_deleted'].append(tx_ref)
                except Exception:
                    logger.exception('Failed to delete linked transaction %s for expense %s', tx_ref, eid)
        except Exception:
            logger.exception('Failed while cancelling expense %s', e)

    # 2) Decrement pond counts
    if pond_id and count:
        try:
            dec_fields = {
                'fish_count': -int(count),
                'metadata.total_fish': -int(count),
                f'metadata.fish_types.{species}': -int(count)
            }
            pond_repo.atomic_update_metadata(pond_id, inc_fields=dec_fields)
            summary['ponds_updated'].append(pond_id)
        except Exception:
            logger.exception('Failed to decrement pond metadata for pond %s', pond_id)

    # 3) Decrement fish current_stock
    if species and count:
        try:
            # raw collection update
            fish_coll = fish_repo.collection if hasattr(fish_repo, 'collection') else fish_repo
            fish_coll.update_one({'_id': species}, {'$inc': {'current_stock': -int(count)}})
            summary['fish_updated'].append(species)
        except Exception:
            logger.exception('Failed to decrement fish current_stock for species %s', species)

    # 4) Remove analytics batches referencing sampling/stock
    try:
        analytics_coll = fish_analytics_repo.collection if hasattr(fish_analytics_repo, 'collection') else fish_analytics_repo
        # event_id convention used in sampling_service: f"{account_key}-{species}-{pond_id}-{sampling_id}"
        # We search by sampling id or stock_id in metadata or event id
        q = {'$or': [{'metadata.sampling_id': sampling_id}, {'metadata.stock_id': stock_id}, {'event_id': {'$regex': sampling_id}}]}
        res = analytics_coll.delete_many(q)
        summary['analytics_deleted'] = getattr(res, 'deleted_count', None)
    except Exception:
        logger.exception('Failed to delete analytics for sampling %s', sampling_id)

    # 5) Remove fish activity records referencing the sampling/stock
    try:
        activity_coll = fish_activity_repo.collection if hasattr(fish_activity_repo, 'collection') else fish_activity_repo
        q2 = {'$or': [{'stock_id': stock_id}, {'sampling_id': sampling_id}, {'pond_id': pond_id}], 'event_type': 'buy'}
        res2 = activity_coll.delete_many(q2)
        summary['activities_deleted'] = getattr(res2, 'deleted_count', None)
    except Exception:
        logger.exception('Failed to delete fish_activity for sampling %s', sampling_id)

    return summary

