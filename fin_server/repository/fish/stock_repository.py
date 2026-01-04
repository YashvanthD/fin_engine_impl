import logging

from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger('fin_server.repository.stock_repository')

class StockRepository:
    """Reusable helpers for adding/removing fish stock on ponds and related side-effects.

    Methods are best-effort and will log exceptions instead of raising, to match
    existing route behavior. They return True on a successful (best-effort) operation
    and False on failure.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(StockRepository, cls).__new__(cls)
        return cls._instance

    def __init__(self, db=None):
        # store provided db reference (may be None); avoid importing route modules here to prevent circular imports
        self.db = db
        self.ponds = get_collection('pond')
        self.pond_events = get_collection('pond_event')
        self.fish = get_collection('fish')
        self.fish_activity = get_collection('fish_activity')
        self.fish_analytics = get_collection('fish_analytics')
        self.fish_mapping = get_collection('fish_mapping')
        # expenses collection may or may not be present
        try:
            self.expenses = get_collection('expenses')
        except Exception:
            self.expenses = None

    def _attempt_update(self, queries, update):
        """Try a list of queries sequentially until one matches. Return the update result or None."""
        for q in queries:
            try:
                res = self.ponds.update_one(q, update)
                if getattr(res, 'matched_count', 0):
                    return res
            except Exception:
                logger.exception('Attempted update_one failed for query: %s', q)
        return None

    def _attempt_update_session(self, queries, update, session):
        """Same as _attempt_update but within a session for transactions."""
        for q in queries:
            try:
                res = self.ponds.update_one(q, update, session=session)
                if getattr(res, 'matched_count', 0):
                    return res
            except Exception:
                logger.exception('Attempted session update_one failed for query: %s', q)
        return None

    def add_stock_to_pond(self, account_key, pond_id, species, count, average_weight=None, sampling_id=None, recorded_by=None, create_event=True, create_activity=True, create_analytics=True, create_expense=False, expense_amount=None):
        """Add `count` fish of `species` to the pond's current_stock.

        Simpler implementation: read the pond doc, modify the in-memory current_stock list (add or increment),
        then write the whole list back and increment fish_count. This avoids positional-operator edge cases
        and ensures a new species entry is created when needed.
        """
        logger.info('add_stock_to_pond called pond=%s species=%s count=%s account=%s recorded_by=%s sampling_id=%s', pond_id, species, count, account_key, recorded_by, sampling_id)
        try:
            # find pond document (prefer pond_id field, fallback to _id)
            try:
                pond = self.ponds.find_one({'pond_id': pond_id})
            except Exception:
                pond = None
            if not pond:
                try:
                    pond = self.ponds.find_one({'_id': pond_id})
                except Exception:
                    pond = None

            if not pond:
                logger.warning('No pond found for pond_id=%s; cannot add stock (species=%s count=%s)', pond_id, species, count)
                return False

            logger.debug('Found pond for pond_id=%s (db _id=%s)', pond_id, pond.get('_id'))
            cs = pond.get('current_stock') or []
            updated = False
            for s in cs:
                if s.get('species') == species:
                    # increment existing record
                    try:
                        s['quantity'] = int(s.get('quantity', 0) or 0) + int(count)
                    except Exception:
                        s['quantity'] = (s.get('quantity') or 0) + int(count)
                    # update average weight if provided
                    if average_weight is not None:
                        s['average_weight'] = average_weight
                    updated = True
                    logger.info('Incremented existing stock for pond=%s species=%s new_quantity=%s', pond_id, species, s['quantity'])
                    break

            if not updated:
                stock_doc = {
                    'stock_id': sampling_id or f'stock-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S")}',
                    'species': species,
                    'quantity': int(count),
                    'average_weight': average_weight,
                    'stocking_date': get_time_date_dt(include_time=True)
                }
                cs.append(stock_doc)
                logger.info('Appended new stock record for pond=%s species=%s quantity=%s stock_id=%s', pond_id, species, count, stock_doc.get('stock_id'))

            # persist updated stock array and increment fish_count
            try:
                res = self.ponds.update_one({'_id': pond.get('_id')}, {'$set': {'current_stock': cs}, '$inc': {'fish_count': int(count)}})
                logger.debug('Persisted current_stock for pond _id=%s matched=%s modified=%s', pond.get('_id'), getattr(res, 'matched_count', 0), getattr(res, 'modified_count', 0))
            except Exception:
                logger.exception('Failed to persist updated current_stock for pond_id=%s', pond_id)

            # 2) update fish document current_stock (best-effort)
            try:
                # Try to update by species code or _id
                qf = {'$or': [{'species_code': species}, {'_id': species}]}
                f = None
                # Prefer repository API if available
                f = self.fish.find_one(qf)
                if f:
                    try:
                        # Compute new current_stock value if repository exposes `update`
                        old_val = (f.get('current_stock', 0) or 0)
                        new_val = int(old_val) + int(count)
                        self.fish.update({'_id': f.get('_id')}, {'current_stock': new_val})

                        logger.debug('Updated fish %s current_stock inc=%s', f.get('_id'), count)
                    except Exception:
                        logger.exception('Failed to increment fish.current_stock for species=%s', species)
                else:
                    # create minimal fish doc using repo API if present
                    fish_doc = {'_id': species, 'species_code': species, 'common_name': species, 'current_stock': int(count)}
                    try:
                        self.fish.create(fish_doc)
                        self.fish.insert_one(fish_doc)
                        logger.info('Created fish doc for species=%s current_stock=%s', species, count)
                    except Exception:
                        logger.exception('Failed to create fish doc for stock add for species=%s', species)
            except Exception:
                logger.exception('Error updating fish collection for add_stock')

            # 3) optionally create pond_event
            if create_event:
                try:
                    ev = {'pond_id': pond_id, 'event_type': 'buy', 'details': {'species': species, 'count': int(count)}, 'recorded_by': recorded_by}
                    try:
                        r = self.pond_events.insert_one(ev)
                        logger.debug('Inserted pond_event for buy pond=%s event_id=%s', pond_id, getattr(r, 'inserted_id', None))
                    except Exception:
                        logger.exception('Failed to insert pond_event for add_stock')
                except Exception:
                    logger.exception('Error creating pond_event for add_stock')

            # 4) optionally create fish_activity
            if create_activity:
                try:
                    act = {'account_key': account_key, 'pond_id': pond_id, 'fish_id': species, 'event_type': 'buy', 'count': int(count), 'user_key': recorded_by, 'created_at': get_time_date_dt(include_time=True)}
                    try:
                        r = self.fish_activity.insert_one(act)
                        logger.debug('Inserted fish_activity for pond=%s activity_id=%s', pond_id, getattr(r, 'inserted_id', None))
                    except Exception:
                        logger.exception('Failed to insert fish_activity for add_stock')
                except Exception:
                    logger.exception('Failed to create fish_activity for add_stock')

            # 5) optionally analytics batch
            if create_analytics:
                try:
                    # Use same structure as FishAnalyticsRepository.add_batch: create batch doc
                    batch = {'_id': f'{account_key}-{species}-{pond_id}-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S%f")}', 'species_id': species, 'count': int(count), 'fish_age_in_month': 0, 'date_added': get_time_date_dt(include_time=True), 'account_key': account_key, 'pond_id': pond_id}
                    if average_weight is not None:
                        batch['fish_weight'] = average_weight
                    try:
                        r = self.fish_analytics.insert_one(batch)
                        logger.debug('Inserted fish_analytics batch id=%s', getattr(r, 'inserted_id', None))
                    except Exception:
                        logger.exception('Failed to insert fish_analytics batch for add_stock')
                except Exception:
                    logger.exception('Error creating analytics batch for add_stock')

            # 6) optional expense
            if create_expense and self.expenses is not None:
                try:
                    exp = {
                        'pond_id': pond_id,
                        'species': species,
                        'category': 'buy',
                        'type': 'buy',
                        'amount': float(expense_amount) if expense_amount is not None else None,
                        'currency': 'INR',
                        'recorded_by': recorded_by,
                        'account_key': account_key,
                        'creditor': None,
                        'debited': None,
                        'transaction_id': None,
                        'gst': None,
                        'tax': None,
                        'payment_method': None,
                        'invoice_no': None,
                        'vendor': None,
                        'created_at': get_time_date_dt(include_time=True)
                    }
                    try:
                        # r = self.expenses.insert_one(exp)
                        logger.debug('Inserted expense for pond=%s expense_id=%s amount=%s', pond_id, getattr(r, 'inserted_id', None), exp.get('amount'))
                    except Exception:
                        logger.exception('Failed to insert expense doc for add_stock')
                except Exception:
                    logger.exception('Error creating expense doc for add_stock')

            # 7) ensure fish mapping contains species
            try:
                try:
                    r = self.fish_mapping.update_one({'account_key': account_key}, {'$addToSet': {'fish_ids': species}}, upsert=True)
                    logger.debug('Upserted fish_mapping for account=%s result_matched=%s result_modified=%s', account_key, getattr(r, 'matched_count', None), getattr(r, 'modified_count', None))
                except Exception:
                    logger.exception('Failed to upsert fish_mapping')
            except Exception:
                logger.exception('Error updating fish mapping for add_stock')

            logger.info('add_stock_to_pond completed pond=%s species=%s count=%s', pond_id, species, count)
            return True
        except Exception:
            logger.exception('Unexpected error in add_stock_to_pond for pond=%s species=%s', pond_id, species)
            return False

    def add_stock_transactional(self, account_key, pond_id, species, count, average_weight=None, sampling_id=None, recorded_by=None, expense_amount=None, timeout_seconds: int = 3,
                                transactions_repo=get_collection('transactions')):
        logger.info('add_stock_transactional start pond=%s species=%s count=%s account=%s', pond_id, species, count, account_key)
        # ...existing code ...
        try:
            expense_doc = {
                'pond_id': pond_id,
                'species': species,
                'category': 'buy',
                'type': 'buy',
                'amount': float(expense_amount) if expense_amount is not None else None,
                'currency': 'INR',
                'notes': None,
                'recorded_by': recorded_by,
                'account_key': account_key,
                'creditor': None,
                'debited': None,
                'transaction_id': None,
                'gst': None,
                'tax': None,
                'payment_method': None,
                'invoice_no': None,
                'vendor': None,
                'created_at': None
            }

            session = None
            timer = None
            try:
                # Use the underlying DB client for transactions when available
                client = None
                try:
                    client = self.db.client if self.db is not None else None
                except Exception:
                    client = None
                if client is None:
                    logger.warning('Mongo client not available for transactions; falling back to non-transactional add_stock_to_pond')
                    return self.add_stock_to_pond(account_key, pond_id, species, count, average_weight=average_weight, sampling_id=sampling_id, recorded_by=recorded_by, create_event=True, create_activity=True, create_analytics=True, create_expense=True, expense_amount=expense_amount)

                with client.start_session() as session:
                    session.start_transaction()
                    logger.debug('Started mongo session for add_stock_transactional pond=%s', pond_id)

                    # create transaction ledger entry using TransactionsRepository inside the session
                    try:
                        from fin_server.repository.expenses import TransactionsRepository
                        tr = TransactionsRepository(self.db)
                        tx_payload = {
                            'transaction_id': None,
                            'type': 'expense',
                            'subtype': 'buy',
                            'amount': expense_doc.get('amount'),
                            'currency': expense_doc.get('currency'),
                            'account_key': account_key,
                            'pond_id': pond_id,
                            'species': species,
                            'creditor': None,
                            'debited': None,
                            'payment_method': None,
                            'invoice_no': None,
                            'gst': None,
                            'tax': None,
                            'recorded_by': recorded_by
                        }
                        tx_res = tr.collection.insert_one(tx_payload, session=session)
                        tx_id = getattr(tx_res, 'inserted_id', None)
                        logger.debug('Created transaction ledger inside session tx_id=%s', tx_id)
                    except Exception:
                        logger.exception('Failed to create transaction inside session')
                        session.abort_transaction()
                        return False

                    # 2) create expense referencing transaction
                    try:
                        expense_doc['transaction_ref'] = str(tx_id)
                        expense_doc['created_at'] = get_time_date_dt(include_time=True)
                        self.expenses.insert_one(expense_doc, session=session)
                        logger.debug('Inserted expense inside session for pond=%s transaction_ref=%s', pond_id, expense_doc.get('transaction_ref'))
                    except Exception:
                        logger.exception('Failed to insert expense inside session')
                        session.abort_transaction()
                        return False

                    # read-modify-write pond.current_stock inside session
                    try:
                        pond = self.ponds.find_one({'pond_id': pond_id}, session=session) or self.ponds.find_one({'_id': pond_id}, session=session)
                        if not pond:
                            logger.warning('No pond found for pond_id=%s (transactional)', pond_id)
                            session.abort_transaction()
                            return False

                        cs = pond.get('current_stock') or []
                        updated = False
                        for s in cs:
                            if s.get('species') == species:
                                try:
                                    s['quantity'] = int(s.get('quantity', 0) or 0) + int(count)
                                except Exception:
                                    s['quantity'] = (s.get('quantity') or 0) + int(count)
                                if average_weight is not None:
                                    s['average_weight'] = average_weight
                                updated = True
                                # logger.info('Decremented stock for pond=%s species=%s old_quantity=%s new_quantity=%s', pond_id, species, old_q, s['quantity'])
                                break
                        if not updated:
                            stock_doc = {
                                'stock_id': sampling_id or f'stock-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S")}',
                                'species': species,
                                'quantity': int(count),
                                'average_weight': average_weight,
                                'stocking_date': get_time_date_dt(include_time=True)
                            }
                            cs.append(stock_doc)

                        # persist
                        self.ponds.update_one({'_id': pond.get('_id')}, {'$set': {'current_stock': cs}, '$inc': {'fish_count': int(count)}}, session=session)
                    except Exception:
                        logger.exception('Failed to update pond.current_stock inside session')
                        session.abort_transaction()
                        return False

                    # update fish.current_stock inside session
                    try:
                        q = {'$or': [{'species_code': species}, {'_id': species}]}
                        # Use raw collection for session-aware ops
                        fish_coll = self.db['fish'] if self.db is not None else None
                        if fish_coll is not None:
                            f = fish_coll.find_one(q, session=session)
                            if f:
                                fish_coll.update_one({'_id': f.get('_id')}, {'$inc': {'current_stock': int(count)}}, session=session)
                            else:
                                fish_doc = {'_id': species, 'species_code': species, 'common_name': species, 'current_stock': int(count)}
                                fish_coll.insert_one(fish_doc, session=session)
                        else:
                            # fallback to repository methods without session
                            f = self.fish.find_one(q)
                            if f:
                                # compute new value and use repo.update
                                if hasattr(self.fish, 'update'):
                                    new_val = int((f.get('current_stock', 0) or 0)) + int(count)
                                    self.fish.update({'_id': f.get('_id')}, {'current_stock': new_val})
                                else:
                                    self.fish.update_one({'_id': f.get('_id')}, {'$inc': {'current_stock': int(count)}})
                            else:
                                fish_doc = {'_id': species, 'species_code': species, 'common_name': species, 'current_stock': int(count)}
                                if hasattr(self.fish, 'create'):
                                    self.fish.create(fish_doc)
                                else:
                                    self.fish.insert_one(fish_doc)
                    except Exception:
                        logger.exception('Failed to update fish.current_stock inside session')
                        session.abort_transaction()
                        return False

                    # activity/analytics best-effort inside session
                    try:
                        act = {'account_key': account_key, 'pond_id': pond_id, 'fish_id': species, 'event_type': 'buy', 'count': int(count), 'user_key': recorded_by, 'created_at': get_time_date_dt(include_time=True)}
                        self.fish_activity.insert_one(act, session=session)
                    except Exception:
                        logger.exception('Failed to insert fish_activity inside session')

                    try:
                        batch = {'_id': f'{account_key}-{species}-{pond_id}-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S%f")}', 'species_id': species, 'count': int(count), 'fish_age_in_month': 0, 'date_added': get_time_date_dt(include_time=True), 'account_key': account_key, 'pond_id': pond_id}
                        if average_weight is not None:
                            batch['fish_weight'] = average_weight
                        self.fish_analytics.insert_one(batch, session=session)
                    except Exception:
                        logger.exception('Failed to insert fish_analytics inside session')

                    try:
                        session.commit_transaction()
                        logger.info('Committed transaction for add_stock_transactional pond=%s tx_id=%s', pond_id, tx_id)
                    except Exception:
                        logger.exception('Failed to commit transaction')
                        try:
                            session.abort_transaction()
                            logger.warning('Aborted transaction for pond=%s', pond_id)
                        except Exception:
                            pass
                        return False

                    return True
            finally:
                if timer:
                    try:
                        timer.cancel()
                    except Exception:
                        pass
        except Exception:
            logger.exception('Unexpected error in add_stock_transactional for pond=%s species=%s', pond_id, species)
            return False

    def remove_stock_from_pond(self, account_key, pond_id, species, count, recorded_by=None, create_event=True, create_activity=True, create_analytics=True):
        logger.info('remove_stock_from_pond called pond=%s species=%s count=%s account=%s recorded_by=%s', pond_id, species, count, account_key, recorded_by)
        try:
            # find pond by pond_id then _id
            try:
                pond = self.ponds.find_one({'pond_id': pond_id})
            except Exception:
                pond = None
            if not pond:
                try:
                    pond = self.ponds.find_one({'_id': pond_id})
                except Exception:
                    pond = None

            if not pond:
                logger.warning('No pond found for pond_id=%s; cannot remove stock', pond_id)
                return False

            logger.debug('Found pond for removal pond_id=%s _id=%s', pond_id, pond.get('_id'))
            cs = pond.get('current_stock') or []
            for s in cs:
                if s.get('species') == species:
                    try:
                        old_q = int(s.get('quantity', 0) or 0)
                        s['quantity'] = old_q - int(count)
                        logger.info('Decremented stock for pond=%s species=%s old_quantity=%s new_quantity=%s', pond_id, species, old_q, s['quantity'])
                    except Exception:
                        s['quantity'] = (s.get('quantity') or 0) - int(count)
                        logger.info('Decremented stock for pond=%s species=%s (fallback arithmetic)', pond_id, species)
                    break

            # remove depleted entries
            cs = [s for s in cs if (s.get('quantity') or 0) > 0]
            try:
                res = self.ponds.update_one({'_id': pond.get('_id')}, {'$set': {'current_stock': cs}, '$inc': {'fish_count': -int(count)}})
                logger.debug('Persisted decremented current_stock for pond _id=%s matched=%s modified=%s', pond.get('_id'), getattr(res, 'matched_count', 0), getattr(res, 'modified_count', 0))
            except Exception:
                logger.exception('Failed to persist decremented current_stock for pond_id=%s', pond_id)

            # ensure cleanup
            try:
                self.ponds.update_one({'_id': pond.get('_id')}, {'$pull': {'current_stock': {'quantity': {'$lte': 0}}}})
            except Exception:
                logger.exception('Failed to pull depleted stock entries')

            # pond_event & activity & analytics
            if create_event:
                try:
                    ev = {'pond_id': pond_id, 'event_type': 'sample', 'details': {'species': species, 'count': int(count)}, 'recorded_by': recorded_by}
                    try:
                        r = self.pond_events.insert_one(ev)
                        logger.debug('Inserted pond_event for sample pond=%s event_id=%s', pond_id, getattr(r, 'inserted_id', None))
                    except Exception:
                        logger.exception('Failed to insert pond_event for remove_stock')
                except Exception:
                    logger.exception('Error creating pond_event for remove_stock')

            if create_activity:
                try:
                    act = {'account_key': account_key, 'pond_id': pond_id, 'fish_id': species, 'event_type': 'sample', 'count': int(count), 'user_key': recorded_by, 'created_at': get_time_date_dt(include_time=True)}
                    try:
                        r = self.fish_activity.insert_one(act)
                        logger.debug('Inserted fish_activity for sample pond=%s activity_id=%s', pond_id, getattr(r, 'inserted_id', None))
                    except Exception:
                        logger.exception('Failed to insert fish_activity for remove_stock')
                except Exception:
                    logger.exception('Error creating fish_activity for remove_stock')

            if create_analytics:
                try:
                    batch = {'_id': f'{account_key}-{species}-sample-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S%f")}', 'species_id': species, 'count': -int(count), 'fish_age_in_month': 0, 'date_added': get_time_date_dt(include_time=True), 'account_key': account_key, 'pond_id': pond_id}
                    try:
                        r = self.fish_analytics.insert_one(batch)
                        logger.debug('Inserted fish_analytics sample batch id=%s', getattr(r, 'inserted_id', None))
                    except Exception:
                        logger.exception('Failed to insert fish_analytics batch for remove_stock')
                except Exception:
                    logger.exception('Error creating analytics batch for remove_stock')

            logger.info('remove_stock_from_pond completed pond=%s species=%s count=%s', pond_id, species, count)
            return True
        except Exception:
            logger.exception('Unexpected error in remove_stock_from_pond for pond=%s species=%s', pond_id, species)
            return False

