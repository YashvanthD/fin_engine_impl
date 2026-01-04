from fin_server.repository.base_repository import BaseRepository
import logging
from fin_server.utils.time_utils import get_time_date_dt

class PondRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="pond"):
        if cls._instance is None:
            cls._instance = super(PondRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    def __init__(self, db, collection_name="pond"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self.coll = self.collection
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def create(self, data):
        logging.info(f"Inserting pond data: {data}")
        data['created_at'] = get_time_date_dt(include_time=True)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = get_time_date_dt(include_time=True)
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)

    def get_pond(self, pond_id):
        return self.find_one({'pond_id': pond_id})

    def _pond_query(self, pond_id):
        """Return a query that matches a pond by either pond_id or _id."""
        return {'$or': [{'pond_id': pond_id}, {'_id': pond_id}]}

    def atomic_update_metadata(self, pond_id, inc_fields=None, set_fields=None, unset_fields=None):
        update = {}
        if inc_fields:
            update['$inc'] = inc_fields
        if set_fields:
            update['$set'] = set_fields
        if unset_fields:
            update['$unset'] = unset_fields
        if not update:
            return None
        return self.collection.update_one(self._pond_query(pond_id), update, upsert=False)

    # --- Backwards-compatible thin collection proxies ---
    def update_one(self, query, update, **kwargs):
        return self.collection.update_one(query, update, **kwargs)

    def update_many(self, query, update, **kwargs):
        return self.collection.update_many(query, update, **kwargs)

    def insert_one(self, doc, **kwargs):
        return self.collection.insert_one(doc, **kwargs)

    def delete_one(self, query, **kwargs):
        return self.collection.delete_one(query, **kwargs)

    def update_stock(self, pond_id, species, delta, average_weight=None, sampling_id=None):
        """Update pond current_stock and related counters for a species.

        - Adjusts/increments top-level 'fish_count' and nested 'metadata.total_fish'
          and 'metadata.fish_types.<species>' by `delta`.
        - Updates the `current_stock` array by incrementing an existing species entry
          or appending a new one. If `average_weight` provided it will set/update it
          on the species entry.
        Returns the update result object or None if pond not found.
        """
        try:
            q = self._pond_query(pond_id)
            pond = self.find_one(q)
            if not pond:
                return None

            cs = pond.get('current_stock') or []
            updated = False
            for s in cs:
                if s.get('species') == species:
                    try:
                        s['quantity'] = int(s.get('quantity', 0) or 0) + int(delta)
                    except Exception:
                        # fallback to arithmetic that tolerates strings
                        s['quantity'] = (s.get('quantity') or 0) + int(delta)
                    if average_weight is not None:
                        s['average_weight'] = average_weight
                    updated = True
                    break

            if not updated:
                stock_doc = {
                    'stock_id': sampling_id or f'stock-{get_time_date_dt(include_time=True).strftime("%Y%m%d%H%M%S")}',
                    'species': species,
                    'quantity': int(delta),
                    'average_weight': average_weight,
                    'stocking_date': get_time_date_dt(include_time=True)
                }
                cs.append(stock_doc)

            # persist updated stock array and increment counts atomically where possible
            # Use a combined update: set current_stock array and increment counters
            inc_fields = {'fish_count': int(delta), 'metadata.total_fish': int(delta), f'metadata.fish_types.{species}': int(delta)}
            update_doc = {'$set': {'current_stock': cs, 'updated_at': get_time_date_dt(include_time=True)}, '$inc': inc_fields}
            res = self.collection.update_one(q, update_doc)
            return res
        except Exception:
            logging.exception('Failed to update_stock for pond=%s species=%s', pond_id, species)
            return None

    def update_status(self, pond_id, status):
        """Set the high-level pond status and update updated_at.

        Returns modified_count (or None on failure).
        """
        try:
            res = self.collection.update_one(self._pond_query(pond_id), {'$set': {'status': status, 'updated_at': get_time_date_dt(include_time=True)}}, upsert=False)
            return getattr(res, 'modified_count', None)
        except Exception:
            logging.exception('Failed to update_status for pond=%s', pond_id)
            return None

    def update_fields(self, pond_id, set_fields: dict = None, inc_fields: dict = None, unset_fields: dict = None, upsert: bool = False):
        """Generic helper to update arbitrary pond fields.

        - set_fields: dict of fields to $set
        - inc_fields: dict of fields to $inc
        - unset_fields: dict of fields to $unset (values ignored)
        Returns the update result or None on failure.
        """
        try:
            update = {}
            if set_fields:
                update.setdefault('$set', {})
                update['$set'].update(set_fields)
            if inc_fields:
                update.setdefault('$inc', {})
                update['$inc'].update(inc_fields)
            if unset_fields:
                update.setdefault('$unset', {})
                # ensure unset values are empty strings per Mongo convention used elsewhere
                update['$unset'].update({k: '' for k in unset_fields.keys()})
            if not update:
                return None
            # Always set updated_at
            update.setdefault('$set', {})
            update['$set']['updated_at'] = get_time_date_dt(include_time=True)
            res = self.collection.update_one(self._pond_query(pond_id), update, upsert=upsert)
            return res
        except Exception:
            logging.exception('Failed to update_fields for pond=%s', pond_id)
            return None
