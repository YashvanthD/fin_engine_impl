from fin_server.repository.mongo_helper import MongoRepositorySingleton
from fin_server.utils.time_utils import get_time_date_dt
import logging

class StockRepository:
    """Reusable helpers for adding/removing fish stock on ponds and related side-effects.

    Methods are best-effort and will log exceptions instead of raising, to match
    existing route behavior. They return True on a successful (best-effort) operation
    and False on failure.
    """

    def __init__(self, db=None):
        self.db = db or MongoRepositorySingleton.get_db()
        self.ponds = MongoRepositorySingleton.get_collection('ponds', self.db)
        self.pond_events = MongoRepositorySingleton.get_collection('pond_events', self.db)
        self.fish = MongoRepositorySingleton.get_collection('fish', self.db)
        self.fish_activity = MongoRepositorySingleton.get_collection('fish_activity', self.db)
        self.fish_analytics = MongoRepositorySingleton.get_collection('fish_analytics', self.db)
        self.fish_mapping = MongoRepositorySingleton.get_collection('fish_mapping', self.db)
        # expenses collection may or may not be present
        try:
            self.expenses = MongoRepositorySingleton.get_collection('expenses', self.db)
        except Exception:
            self.expenses = None

    def add_stock_to_pond(self, account_key, pond_id, species, count, average_weight=None, sampling_id=None, recorded_by=None, create_event=True, create_activity=True, create_analytics=True, create_expense=False, expense_amount=None):
        """Add `count` fish of `species` to the pond's current_stock.

        - account_key: account/farm identifier (optional)
        - pond_id: pond business id
        - species: species code/id
        - count: integer to add
        - average_weight: optional per-fish weight
        - sampling_id: optional id to use as stock_id
        - recorded_by: user_key who recorded
        - create_event/activity/analytics flags control side-effects
        """
        try:
            # 1) atomic update into pond current_stock if entry exists
            try:
                res = self.ponds.update_one(
                    {'pond_id': pond_id, 'current_stock.species': species},
                    {'$inc': {'current_stock.$.quantity': int(count)}, '$set': {'current_stock.$.average_weight': average_weight}}
                )
            except Exception:
                res = None
            if not res or not getattr(res, 'matched_count', 0):
                # push a new stock entry
                stock_doc = {
                    'stock_id': sampling_id or f'stock-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S")}',
                    'species': species,
                    'quantity': int(count),
                    'average_weight': average_weight,
                    'stocking_date': get_time_date_dt(include_time=True)
                }
                try:
                    self.ponds.update_one({'pond_id': pond_id}, {'$push': {'current_stock': stock_doc}})
                except Exception:
                    logging.exception('Failed to push new stock_doc into pond.current_stock')

            # 2) update fish document current_stock (best-effort)
            try:
                # Try to update by species code or _id
                q = {'$or': [{'species_code': species}, {'_id': species}]}
                f = self.fish.find_one(q)
                if f:
                    try:
                        self.fish.update_one({'_id': f.get('_id')}, {'$inc': {'current_stock': int(count)}})
                    except Exception:
                        logging.exception('Failed to increment fish.current_stock')
                else:
                    # create minimal fish doc
                    fish_doc = {'_id': species, 'species_code': species, 'common_name': species, 'current_stock': int(count)}
                    try:
                        self.fish.insert_one(fish_doc)
                    except Exception:
                        logging.exception('Failed to create fish doc for stock add')
            except Exception:
                logging.exception('Error updating fish collection for add_stock')

            # 3) optionally create pond_event
            if create_event:
                try:
                    ev = {'pond_id': pond_id, 'event_type': 'buy', 'details': {'species': species, 'count': int(count)}, 'recorded_by': recorded_by}
                    try:
                        self.pond_events.insert_one(ev)
                    except Exception:
                        logging.exception('Failed to insert pond_event for add_stock')
                except Exception:
                    logging.exception('Error creating pond_event for add_stock')

            # 4) optionally create fish_activity
            if create_activity:
                try:
                    act = {'account_key': account_key, 'pond_id': pond_id, 'fish_id': species, 'event_type': 'buy', 'count': int(count), 'user_key': recorded_by, 'created_at': get_time_date_dt(include_time=True)}
                    try:
                        self.fish_activity.insert_one(act)
                    except Exception:
                        logging.exception('Failed to insert fish_activity for add_stock')
                except Exception:
                    logging.exception('Error creating fish_activity for add_stock')

            # 5) optionally analytics batch
            if create_analytics:
                try:
                    # Use same structure as FishAnalyticsRepository.add_batch: create batch doc
                    batch = {'_id': f'{account_key}-{species}-{pond_id}-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S%f")}', 'species_id': species, 'count': int(count), 'fish_age_in_month': 0, 'date_added': get_time_date_dt(include_time=True), 'account_key': account_key, 'pond_id': pond_id}
                    if average_weight is not None:
                        batch['fish_weight'] = average_weight
                    try:
                        self.fish_analytics.insert_one(batch)
                    except Exception:
                        logging.exception('Failed to insert fish_analytics batch for add_stock')
                except Exception:
                    logging.exception('Error creating analytics batch for add_stock')

            # 6) optional expense
            if create_expense and self.expenses is not None:
                try:
                    exp = {'pond_id': pond_id, 'species': species, 'category': 'buy', 'amount': float(expense_amount) if expense_amount is not None else None, 'recorded_by': recorded_by, 'account_key': account_key, 'created_at': get_time_date_dt(include_time=True)}
                    try:
                        self.expenses.insert_one(exp)
                    except Exception:
                        logging.exception('Failed to insert expense doc for add_stock')
                except Exception:
                    logging.exception('Error creating expense doc for add_stock')

            # 7) ensure fish mapping contains species
            try:
                try:
                    self.fish_mapping.update_one({'account_key': account_key}, {'$addToSet': {'fish_ids': species}}, upsert=True)
                except Exception:
                    logging.exception('Failed to upsert fish_mapping')
            except Exception:
                logging.exception('Error updating fish mapping for add_stock')

            return True
        except Exception:
            logging.exception('Unexpected error in add_stock_to_pond')
            return False

    def remove_stock_from_pond(self, account_key, pond_id, species, count, recorded_by=None, create_event=True, create_activity=True, create_analytics=True):
        """Remove `count` fish of `species` from pond.current_stock (sampling, sell, remove).

        Performs a decrement on the matching current_stock entry and removes depleted entries.
        """
        try:
            try:
                res = self.ponds.update_one({'pond_id': pond_id, 'current_stock.species': species}, {'$inc': {'current_stock.$.quantity': -int(count)}})
            except Exception:
                res = None
            # fallback manual read-modify-write if needed
            if not res or not getattr(res, 'matched_count', 0):
                try:
                    pond = self.ponds.find_one({'pond_id': pond_id})
                    if pond:
                        cs = pond.get('current_stock') or []
                        for s in cs:
                            if s.get('species') == species:
                                try:
                                    s['quantity'] = int(s.get('quantity', 0) or 0) - int(count)
                                except Exception:
                                    s['quantity'] = (s.get('quantity') or 0) - int(count)
                                break
                        # remove depleted
                        cs = [s for s in cs if (s.get('quantity') or 0) > 0]
                        self.ponds.update_one({'pond_id': pond_id}, {'$set': {'current_stock': cs}})
                except Exception:
                    logging.exception('Failed manual decrement of pond.current_stock')

            # ensure clean-up of non-positive quantities
            try:
                self.ponds.update_one({'pond_id': pond_id}, {'$pull': {'current_stock': {'quantity': {'$lte': 0}}}})
            except Exception:
                logging.exception('Failed to pull depleted stock entries')

            # pond_event & activity & analytics
            if create_event:
                try:
                    ev = {'pond_id': pond_id, 'event_type': 'sample', 'details': {'species': species, 'count': int(count)}, 'recorded_by': recorded_by}
                    try:
                        self.pond_events.insert_one(ev)
                    except Exception:
                        logging.exception('Failed to insert pond_event for remove_stock')
                except Exception:
                    logging.exception('Error creating pond_event for remove_stock')

            if create_activity:
                try:
                    act = {'account_key': account_key, 'pond_id': pond_id, 'fish_id': species, 'event_type': 'sample', 'count': int(count), 'user_key': recorded_by, 'created_at': get_time_date_dt(include_time=True)}
                    try:
                        self.fish_activity.insert_one(act)
                    except Exception:
                        logging.exception('Failed to insert fish_activity for remove_stock')
                except Exception:
                    logging.exception('Error creating fish_activity for remove_stock')

            if create_analytics:
                try:
                    batch = {'_id': f'{account_key}-{species}-sample-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S%f")}', 'species_id': species, 'count': -int(count), 'fish_age_in_month': 0, 'date_added': get_time_date_dt(include_time=True), 'account_key': account_key, 'pond_id': pond_id}
                    try:
                        self.fish_analytics.insert_one(batch)
                    except Exception:
                        logging.exception('Failed to insert fish_analytics batch for remove_stock')
                except Exception:
                    logging.exception('Error creating analytics batch for remove_stock')

            return True
        except Exception:
            logging.exception('Unexpected error in remove_stock_from_pond')
            return False

