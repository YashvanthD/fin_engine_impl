from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import MongoRepositorySingleton
import logging
from datetime import datetime, timezone

class FishRepository(BaseRepository):
    def __init__(self, db=None, collection_name="fish"):
        self.collection_name = collection_name
        print("Initializing FishRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def create(self, data):
        logging.info(f"Inserting fish data: {data}")
        data['created_at'] = datetime.now(timezone.utc)
        return self.collection.insert_one(data)

    def find(self, query=None):
        return list(self.collection.find(query or {}))

    def find_one(self, query):
        return self.collection.find_one(query)

    def update(self, query, update_fields):
        update_fields['updated_at'] = datetime.now(timezone.utc)
        return self.collection.update_one(query, {'$set': update_fields})

    def delete(self, query):
        return self.collection.delete_one(query)

    def list_fish_by_account(self, account_key):
        return list(self.collection.find({'account_key': account_key}))

    def get_fields(self):
        """Return a set of all field names in the fish collection."""
        sample = self.collection.find_one()
        if not sample:
            return set()
        return set(sample.keys())

    def get_distinct_values(self, field):
        """Return all distinct values for a given field in the fish collection."""
        return self.collection.distinct(field)

    def get_field_stats(self, field):
        """Return min, max, avg for a numeric field in the fish collection."""
        pipeline = [
            {"$group": {
                "_id": None,
                "min": {"$min": f"${field}"},
                "max": {"$max": f"${field}"},
                "avg": {"$avg": f"${field}"}
            }}
        ]
        result = list(self.collection.aggregate(pipeline))
        if result:
            return result[0]
        return {"min": None, "max": None, "avg": None}

    def create_or_update(self, fish_entity):
        species_id = fish_entity['_id']
        self.collection.update_one({'_id': species_id}, {'$set': fish_entity}, upsert=True)

    # New helper to normalize numeric wrappers from the JSON fixture
    def _convert_number_wrapper(self, v):
        if isinstance(v, dict):
            if '$numberInt' in v:
                try:
                    return int(v['$numberInt'])
                except Exception:
                    return v['$numberInt']
            if '$numberDouble' in v:
                try:
                    return float(v['$numberDouble'])
                except Exception:
                    return v['$numberDouble']
        return v

    def _normalize_doc(self, doc):
        """Recursively normalize a fish document converting numeric wrappers to native types."""
        if isinstance(doc, dict):
            out = {}
            for k, val in doc.items():
                if isinstance(val, dict) and ('$numberInt' in val or '$numberDouble' in val):
                    out[k] = self._convert_number_wrapper(val)
                else:
                    out[k] = self._normalize_doc(val)
            return out
        elif isinstance(doc, list):
            return [self._normalize_doc(v) for v in doc]
        else:
            return doc

    # removed `import_fish_file` - reading from local files is not required; fish should be in DB.


    # New: iterate over fish already in DB and map them to analytics/mapping
    def map_existing_fish(self, account_key=None, dry_run=True, limit=None):
        """Map fish documents already present in the DB into `fish_analytics` and `fish_mapping`.

        - If dry_run=True: do not perform any writes, return processed counts and sample mapped docs.
        - If dry_run=False: upsert analytics and mapping documents for each fish.
        - `account_key` if provided overrides per-fish account selection; otherwise `species_code` or `_id` is used.
        - `limit` optionally restricts the number of records processed.

        This function will try to read fish docs from the collection; if DB access fails it falls back to the local JSON fixture.
        """
        # Prepare repos
        try:
            mr = MongoRepositorySingleton.get_instance()
            analytics_repo = mr.fish_analytics
            mapping_repo = mr.fish_mapping
        except Exception:
            from fin_server.repository.fish_analytics_repository import FishAnalyticsRepository
            from fin_server.repository.fish_mapping_repository import FishMappingRepository
            analytics_repo = FishAnalyticsRepository()
            mapping_col = MongoRepositorySingleton.get_collection('fish_mapping')
            mapping_repo = FishMappingRepository(mapping_col)

        # Load fish documents strictly from DB. If DB access fails, return an error -
        # the source of truth should be the DB and users can add missing fish via the API.
        fish_docs = []
        try:
            query_cursor = self.collection.find({})
            if limit is not None:
                query_cursor = query_cursor.limit(int(limit))
            fish_docs = list(query_cursor)
        except Exception as e:
            return {'error': f'Failed to load fish documents from DB: {e}'}

        processed = 0
        samples = []
        for rec in fish_docs:
            norm = self._normalize_doc(rec)
            acct = account_key or norm.get('species_code') or norm.get('_id')
            # analytics
            try:
                if not dry_run:
                    analytics_repo.create_or_update_from_fish(norm, account_key=acct)
                mapped = analytics_repo.map_fish_to_analytics(norm, account_key=acct)
            except Exception as e:
                mapped = {'error': str(e), 'fish_id': norm.get('_id')}
            # mapping
            try:
                if not dry_run:
                    mapping_repo.create_or_update_mapping(norm)
            except Exception:
                # ignore mapping failures
                pass

            samples.append(mapped)
            processed += 1
            if limit and processed >= int(limit):
                break

        return {'total_found': len(fish_docs), 'processed': processed, 'samples': samples[:3]}
