"""Sampling service: reusable business logic for buy/sample flows.

This service centralizes the operations performed when a sampling record is created
or updated that represents a fish buy (i.e., purchase of stock with some sampling
measurements). It keeps the route handlers thin and enables re-use from other
APIs or background jobs.

API:
- perform_buy_sampling(payload, repos, options) -> dict
    where repos is a dict-like object with keys:
      - sampling (SamplingRepository or collection-like)
      - pond (PondRepository)
      - fish (FishRepository)
      - stock (StockRepository)
      - fish_activity (FishActivityRepository)
      - fish_analytics (FishAnalyticsRepository)
      - expenses (ExpensesRepository)
      - fish_mapping (FishMappingRepository)

The function returns a result dict with keys like 'sampling_id', 'expense_id', 'transaction_id', etc.
"""
from typing import Any, Dict, Optional
from fin_server.utils.time_utils import get_time_date_dt
from fin_server.utils.generator import derive_stock_id_from_dto
import logging

logger = logging.getLogger(__name__)


def perform_buy_sampling(dto: Any, account_key: str, repos: Dict[str, Any], create_expense: bool = True, create_transaction: bool = True) -> Dict[str, Any]:
    """Perform the full buy sampling flow for a created sampling DTO.

    dto: an object with attributes: pondId, species, extra (dict), recordedBy, sampleSize, cost, id
    repos: dictionary with required repository objects (see module docstring)

    Returns: result dict with keys: sampling_id, expense_id (if any), transaction_id (if any)
    """
    result: Dict[str, Optional[Any]] = {'sampling_id': None, 'expense_id': None, 'transaction_id': None}

    # Required repos
    pond_repo = repos.get('pond')
    fish_repo = repos.get('fish')
    sampling_repo = repos.get('sampling')
    stock_repo = repos.get('stock')
    fish_activity_repo = repos.get('fish_activity')
    fish_analytics_repo = repos.get('fish_analytics')
    expenses_repo = repos.get('expenses')
    fish_mapping_repo = repos.get('fish_mapping')

    species = getattr(dto, 'species', None)
    pond_id = getattr(dto, 'pondId', None)
    count = None
    extra = getattr(dto, 'extra', {}) or {}

    # Determine buy_count
    if 'total_count' in extra:
        try:
            count = int(extra.get('total_count'))
        except Exception:
            count = None
    elif 'totalCount' in extra:
        try:
            count = int(extra.get('totalCount'))
        except Exception:
            count = None
    elif getattr(dto, 'sampleSize', None) is not None:
        try:
            count = int(dto.sampleSize)
        except Exception:
            count = None

    # 1) Persist sampling (dto.save should have been called by routes; if not, we persist here)
    try:
        if sampling_repo is not None and hasattr(sampling_repo, 'create') and getattr(dto, 'id', None) is None:
            sid = sampling_repo.create(dto.to_db_doc()) if hasattr(dto, 'to_db_doc') else sampling_repo.create(dto)
            result['sampling_id'] = str(sid)
        else:
            result['sampling_id'] = getattr(dto, 'id', None)
    except Exception:
        logger.exception('Failed to persist sampling record')
        raise

    # Determine/attach a stable stock_id to the sampling using shared helper
    try:
        stock_id = derive_stock_id_from_dto(dto)
        dto.extra = dto.extra or {}
        dto.extra['stock_id'] = stock_id
        result['stock_id'] = stock_id
        # Persist stock_id into the sampling document so future PUTs can reference it.
        try:
            if sampling_repo is not None:
                sid_field = result.get('sampling_id') or dto.extra.get('sampling_id')
                if sid_field:
                    try:
                        sampling_repo.update_one({'sampling_id': sid_field}, {'$set': {'stock_id': stock_id, 'extra.stock_id': stock_id}})
                    except Exception:
                        try:
                            sampling_repo.update_one({'_id': sid_field}, {'$set': {'stock_id': stock_id, 'extra.stock_id': stock_id}})
                        except Exception:
                            logger.exception('Failed to persist stock_id into sampling document')
        except Exception:
            logger.exception('Failed to persist stock_id into sampling repository')
    except Exception:
        logger.exception('Failed to determine stock_id for sampling')

    # 2) Ensure fish mapping
    try:
        if fish_mapping_repo is not None and hasattr(fish_mapping_repo, 'add_fish_to_account'):
            fish_mapping_repo.add_fish_to_account(account_key, species)
        elif fish_mapping_repo is not None and hasattr(fish_mapping_repo, 'update'):
            # best-effort: upsert mapping
            fish_mapping_repo.update({'account_key': account_key}, {'fish_ids': species}, multi=False)
    except Exception:
        logger.exception('Failed to ensure fish mapping')

    # 3) Update pond metadata (increment fish counts and per-species totals + last activity)
    try:
        if pond_repo is not None and count:
            # Build increment fields: top-level fish_count and nested metadata totals
            inc_fields = {
                'fish_count': int(count),
                'metadata.total_fish': int(count),
                f'metadata.fish_types.{species}': int(count)
            }
            # Last activity metadata (include stock_id for precise tracking)
            last_activity = {
                'event_type': 'buy',
                'fish_id': species,
                'count': int(count),
                'stock_id': result.get('stock_id'),
                'recorded_by': getattr(dto, 'recordedBy', None),
                'timestamp': get_time_date_dt(include_time=True).isoformat()
            }
            pond_repo.atomic_update_metadata(pond_id, inc_fields=inc_fields, set_fields={'metadata.last_activity': last_activity})
    except Exception:
        logger.exception('Failed to atomic_update_metadata for pond')

    # 4) Create pond_event
    try:
        ev = {
            'pond_id': pond_id,
            'event_type': 'buy',
            'details': {'species': species, 'count': count, 'total_amount': extra.get('totalAmount') or extra.get('total_amount'), 'stock_id': result.get('stock_id')},
            'recorded_by': getattr(dto, 'recordedBy', None)
        }
        if repos.get('pond_event') is not None and hasattr(repos.get('pond_event'), 'create'):
            repos.get('pond_event').create(ev)
        elif repos.get('pond_event') is not None and hasattr(repos.get('pond_event'), 'insert_one'):
            repos.get('pond_event').insert_one(ev)
    except Exception:
        logger.exception('Failed to create pond_event')

    # 5) Update fish repository current_stock
    try:
        if fish_repo is not None and species is not None and count:
            existing = None
            if hasattr(fish_repo, 'find_one'):
                existing = fish_repo.find_one({'species_code': species})
            if existing:
                try:
                    if hasattr(fish_repo, 'update'):
                        fish_repo.update({'_id': existing.get('_id')}, {'current_stock': (existing.get('current_stock', 0) or 0) + int(count)})
                    else:
                        fish_repo.update_one({'_id': existing.get('_id')}, {'$inc': {'current_stock': int(count)}})
                except Exception:
                    fish_repo.update_one({'_id': existing.get('_id')}, {'$inc': {'current_stock': int(count)}})
            else:
                fish_doc = {'_id': species, 'species_code': species, 'common_name': species, 'current_stock': int(count), 'account_key': account_key}
                if hasattr(fish_repo, 'create'):
                    fish_repo.create(fish_doc)
                else:
                    fish_repo.insert_one(fish_doc)
    except Exception:
        logger.exception('Failed to update/create fish record')

    # 6) Create expense and optional transaction using ExpensesRepository
    expense_id = None
    transaction_id = None
    total_amt = None
    try:
        if 'totalAmount' in extra:
            try:
                total_amt = float(extra.get('totalAmount'))
            except Exception:
                total_amt = None
        elif getattr(dto, 'cost', None) is not None and count:
            try:
                total_amt = float(dto.cost) * float(count)
            except Exception:
                total_amt = None

        if create_expense and expenses_repo is not None and total_amt is not None:
            expense_doc = {
                'pond_id': pond_id,
                'amount': total_amt,
                'currency': extra.get('currency') or 'INR',
                'payment_method': extra.get('payment_method') or 'cash',
                'notes': extra.get('notes') or getattr(dto, 'notes', None),
                'recorded_by': getattr(dto, 'recordedBy', None),
                'account_key': account_key,
                'category': extra.get('category') or 'asset',
                'action': extra.get('action') or 'buy',
                'type': extra.get('type') or 'fish',
                'metadata': {'stock_id': result.get('stock_id')}
            }
            # If ExpensesRepository exposes create_expense, prefer it; it may also create transactions
            if hasattr(expenses_repo, 'create_expense'):
                expense_id = expenses_repo.create_expense(expense_doc)
            elif hasattr(expenses_repo, 'create'):
                expense_id = expenses_repo.create(expense_doc)
            else:
                # fallback to collection insert
                try:
                    r = expenses_repo.insert_one(expense_doc)
                    expense_id = getattr(r, 'inserted_id', None)
                except Exception:
                    logger.exception('Failed to insert expense doc')
            result['expense_id'] = str(expense_id) if expense_id is not None else None
    except Exception:
        logger.exception('Failed to create expense for sampling')

    # 7) Add analytics batch
    try:
        if fish_analytics_repo is not None and count and species:
            fish_age = extra.get('fish_age_in_month') or extra.get('fish_age')
            fish_analytics_repo.add_batch(species, int(count), int(fish_age) if fish_age is not None else 0, account_key=account_key, event_id=f"{account_key}-{species}-{pond_id}-{result.get('sampling_id')}", pond_id=pond_id)
    except Exception:
        logger.exception('Failed to add analytics batch')

    # 8) Record fish activity
    try:
        if fish_activity_repo is not None and hasattr(fish_activity_repo, 'create'):
            activity = {'account_key': account_key, 'pond_id': pond_id, 'fish_id': species, 'event_type': 'buy', 'count': count, 'details': extra.get('details') or {}, 'user_key': getattr(dto, 'recordedBy', None)}
            fish_activity_repo.create(activity)
    except Exception:
        logger.exception('Failed to record fish_activity')

    # 9) Update pond current_stock via StockRepository (async via caller if desired)
    try:
        if stock_repo is not None and count:
            # stock_repo should handle transactions internally (add_stock_transactional)
            ok = stock_repo.add_stock_transactional(account_key, pond_id, species, count, average_weight=getattr(dto, 'averageWeight', None), sampling_id=result.get('stock_id'), recorded_by=getattr(dto, 'recordedBy', None), expense_amount=total_amt)
            if not ok:
                # fallback to non-transactional update
                stock_repo.add_stock_to_pond(account_key, pond_id, species, count, average_weight=getattr(dto, 'averageWeight', None), sampling_id=result.get('stock_id'), recorded_by=getattr(dto, 'recordedBy', None), create_event=False, create_activity=False, create_analytics=False, create_expense=False, expense_amount=total_amt)
    except Exception:
        logger.exception('Failed to update pond stock via StockRepository')

    return result

