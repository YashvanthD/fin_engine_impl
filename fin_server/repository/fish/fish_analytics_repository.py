from fin_server.repository.base_repository import BaseRepository
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.time_utils import get_time_date_dt
import logging

class FishAnalyticsRepository(BaseRepository):
    def __init__(self, db=None, collection_name="fish_analytics"):
        self.collection_name = collection_name
        print("Initializing FishAnalyticsRepository, collection:", self.collection_name)
        self.collection = get_collection(self.collection_name) if db is None else db[collection_name]

    def add_batch(self, species_id, count, fish_age_in_month, date_added=None, account_key=None, event_id=None, fish_weight=None, pond_id=None):
        if not date_added:
            date_added = get_time_date_dt(include_time=True)
        batch = {
            '_id': event_id,
            'species_id': species_id,
            'count': count,
            'fish_age_in_month': fish_age_in_month,
            'date_added': date_added,
            'account_key': account_key
        }
        if fish_weight is not None:
            batch['fish_weight'] = fish_weight
        # Optionally store the originating pond_id to allow pond-scoped analytics
        if pond_id is not None:
            batch['pond_id'] = pond_id
        self.collection.insert_one(batch)

    def get_batches(self, species_id, account_key=None):
        query = {'species_id': species_id}
        if account_key:
            query['account_key'] = account_key
        return list(self.collection.find(query))

    def get_analytics(self, species_id, account_key=None, min_age=None, max_age=None, avg_n=None, min_weight=None, max_weight=None):
        """
        Compute analytics for given species_id.
        Optional filters:
          - min_age, max_age: filter age groups included in analytics (inclusive)
          - avg_n: integer; compute additional averages over the last N age groups (based on age ordering descending)
          - min_weight, max_weight: filter weight groups included in weight analytics
        Returns a dict with:
          - total_fish
          - age_analytics: { age_in_months: count }
          - age_summary: { min: {age, count, avg_age}, max: {...}, avg_age_all }
          - weight_analytics (if weight data present): { weight: count }
          - weight_summary (if weight data present): { min: {...}, max: {...}, avg_all }
          - last_updated, batches
        """
        batches = self.get_batches(species_id, account_key=account_key)
        now = get_time_date_dt(include_time=True)
        age_counts = {}
        weight_counts = {}
        total_fish = 0

        # Build raw analytics from batches
        for batch in batches:
            count = int(batch.get('count', 0) or 0)
            age_at_add = batch.get('fish_age_in_month', 0) or 0
            date_added = batch.get('date_added', now)
            if isinstance(date_added, str):
                try:
                    # parse ISO string into a datetime (naive, local)
                    from datetime import datetime as _dt
                    date_added = _dt.fromisoformat(date_added)
                except Exception:
                    date_added = now
            elif isinstance(date_added, (int, float)):
                from datetime import datetime as _dt
                date_added = _dt.fromtimestamp(date_added)

            months_since_add = (now.year - date_added.year) * 12 + (now.month - date_added.month)
            current_age = int(age_at_add) + int(months_since_add)

            # Age analytics
            age_counts[current_age] = age_counts.get(current_age, 0) + count

            # Weight analytics if weight field exists on batch (per-fish weight)
            fish_weight = batch.get('fish_weight') or batch.get('weight')
            if fish_weight is not None:
                try:
                    w = float(fish_weight)
                    # round to 2 decimal places for grouping
                    w_rounded = round(w, 2)
                    weight_counts[w_rounded] = weight_counts.get(w_rounded, 0) + count
                except Exception:
                    # ignore invalid weight values
                    pass

            total_fish += count

        # Apply age filters if provided
        filtered_age_counts = {}
        for age, cnt in age_counts.items():
            if (min_age is not None and age < int(min_age)):
                continue
            if (max_age is not None and age > int(max_age)):
                continue
            filtered_age_counts[age] = cnt

        # Prepare age summary
        age_summary = {}
        if filtered_age_counts:
            ages_sorted = sorted(filtered_age_counts.keys())
            min_age_val = ages_sorted[0]
            max_age_val = ages_sorted[-1]
            min_age_count = filtered_age_counts.get(min_age_val, 0)
            max_age_count = filtered_age_counts.get(max_age_val, 0)
            # avg of all fishes by age (weighted average)
            total_count_in_age = sum(filtered_age_counts.values())
            if total_count_in_age > 0:
                avg_all_age = sum([age * cnt for age, cnt in filtered_age_counts.items()]) / total_count_in_age
            else:
                avg_all_age = None
            age_summary = {
                'min': {'age': min_age_val, 'count': min_age_count, 'avg_age_of_min_group': float(min_age_val) if min_age_count > 0 else None},
                'max': {'age': max_age_val, 'count': max_age_count, 'avg_age_of_max_group': float(max_age_val) if max_age_count > 0 else None},
                'avg_all': avg_all_age
            }

            # avg_n: if requested, compute average age and average count across last N age groups (largest ages)
            if avg_n:
                try:
                    n = int(avg_n)
                    if n > 0:
                        last_n_ages = ages_sorted[-n:]
                        total_cnt_last_n = sum([filtered_age_counts.get(a, 0) for a in last_n_ages])
                        if total_cnt_last_n > 0:
                            avg_age_last_n = sum([a * filtered_age_counts.get(a, 0) for a in last_n_ages]) / total_cnt_last_n
                        else:
                            avg_age_last_n = None
                        age_summary['avg_last_n_groups'] = {'n': n, 'ages': last_n_ages, 'avg_age': avg_age_last_n, 'avg_count': (total_cnt_last_n / len(last_n_ages)) if len(last_n_ages) > 0 else None}
                except Exception:
                    # ignore invalid avg_n
                    pass

        # Apply weight filters if provided
        filtered_weight_counts = {}
        if weight_counts:
            for w, cnt in weight_counts.items():
                if (min_weight is not None and float(w) < float(min_weight)):
                    continue
                if (max_weight is not None and float(w) > float(max_weight)):
                    continue
                filtered_weight_counts[w] = cnt

        weight_summary = {}
        if filtered_weight_counts:
            weights_sorted = sorted(filtered_weight_counts.keys())
            min_w = weights_sorted[0]
            max_w = weights_sorted[-1]
            min_w_count = filtered_weight_counts.get(min_w, 0)
            max_w_count = filtered_weight_counts.get(max_w, 0)
            total_count_in_weight = sum(filtered_weight_counts.values())
            if total_count_in_weight > 0:
                # weighted average weight across all fishes
                avg_all_weight = sum([w * cnt for w, cnt in filtered_weight_counts.items()]) / total_count_in_weight
            else:
                avg_all_weight = None
            weight_summary = {
                'min': {'weight': float(min_w), 'count': min_w_count, 'avg_weight_of_min_group': float(min_w) if min_w_count > 0 else None},
                'max': {'weight': float(max_w), 'count': max_w_count, 'avg_weight_of_max_group': float(max_w) if max_w_count > 0 else None},
                'avg_all': avg_all_weight
            }

        # Calculate total_fish_after_filters
        total_fish_after_filters = sum(filtered_age_counts.values()) if filtered_age_counts else 0
        # if age filters were not provided, fall back to total_fish computed earlier
        if min_age is None and max_age is None:
            total_fish_after_filters = total_fish

        analytics = {
            'total_fish': total_fish_after_filters,
            'age_analytics': filtered_age_counts,
            'age_summary': age_summary,
            'last_updated': now.isoformat(),
            'batches': batches
        }

        if filtered_weight_counts:
            analytics['weight_analytics'] = filtered_weight_counts
            analytics['weight_summary'] = weight_summary

        return analytics

    # New helper: convert values that use Mongo extended JSON wrappers ($numberInt/$numberDouble)
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

    def map_fish_to_analytics(self, fish_doc, account_key=None):
        """Map a fish entity into an analytics metadata document."""
        fish = self._normalize_doc(fish_doc)
        mapped = {
            '_id': fish.get('_id'),
            'fish_id': fish.get('_id'),
            'species_code': fish.get('species_code'),
            'common_name': fish.get('common_name'),
            'scientific_name': fish.get('scientific_name'),
            'taxonomic_classification': fish.get('taxonomic_classification'),
            'habitat': fish.get('habitat'),
            'distribution': fish.get('distribution'),
            'average_size_cm': fish.get('average_size_cm'),
            'weight_kg': fish.get('weight_kg'),
            'diet': fish.get('diet'),
            'conservation_status': fish.get('conservation_status'),
            'lifespan_years': fish.get('lifespan_years'),
            'water_type': fish.get('water_type'),
            'temperature_range_celsius': fish.get('temperature_range_celsius'),
            'ph_level_range': fish.get('ph_level_range'),
            'commercial_importance': fish.get('commercial_importance'),
            'economic_value_inr': fish.get('economic_value_inr'),
            'account_key': account_key,
            'last_updated': get_time_date_dt(include_time=True)
        }
        return mapped

    def create_or_update_from_fish(self, fish_doc, account_key=None):
        """Upsert a fish analytics document created from a fish entity."""
        mapped = self.map_fish_to_analytics(fish_doc, account_key=account_key)
        query = {'fish_id': mapped['fish_id']}
        update = {'$set': mapped}
        logging.info(f"Upserting analytics for fish_id={mapped['fish_id']} account_key={account_key}")
        return self.collection.update_one(query, update, upsert=True)
