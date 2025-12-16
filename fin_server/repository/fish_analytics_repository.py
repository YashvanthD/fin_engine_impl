from fin_server.repository.mongo_helper import MongoRepositorySingleton
from datetime import datetime, timezone

class FishAnalyticsRepository:
    def __init__(self, db=None, collection_name="fish_analytics"):
        self.collection_name = collection_name
        print("Initializing FishAnalyticsRepository, collection:", self.collection_name)
        self.collection = MongoRepositorySingleton.get_collection(self.collection_name, db)

    def add_batch(self, species_id, count, fish_age_in_month, date_added=None, account_key=None, event_id=None):
        if not date_added:
            date_added = datetime.now(timezone.utc)
        batch = {
            '_id': event_id,
            'species_id': species_id,
            'count': count,
            'fish_age_in_month': fish_age_in_month,
            'date_added': date_added,
            'account_key': account_key
        }
        self.collection.insert_one(batch)

    def get_batches(self, species_id, account_key=None):
        query = {'species_id': species_id}
        if account_key:
            query['account_key'] = account_key
        return list(self.collection.find(query))

    def get_analytics(self, species_id, account_key=None):
        batches = self.get_batches(species_id, account_key=account_key)
        now = datetime.now(timezone.utc)
        age_analytics = {}
        total_fish = 0
        for batch in batches:
            count = batch.get('count', 0)
            age_at_add = batch.get('fish_age_in_month', 0)
            date_added = batch.get('date_added', now)
            if isinstance(date_added, str):
                try:
                    date_added = datetime.fromisoformat(date_added)
                except Exception:
                    date_added = now
            elif isinstance(date_added, (int, float)):
                date_added = datetime.fromtimestamp(date_added, tz=timezone.utc)
            months_since_add = (now.year - date_added.year) * 12 + (now.month - date_added.month)
            current_age = age_at_add + months_since_add
            age_analytics[current_age] = age_analytics.get(current_age, 0) + count
            total_fish += count
        return {
            'total_fish': total_fish,
            'age_analytics': age_analytics,
            'last_updated': now.isoformat(),
            'batches': batches
        }
