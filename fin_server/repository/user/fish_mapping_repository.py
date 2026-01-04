from fin_server.repository.base_repository import BaseRepository
from fin_server.utils.time_utils import get_time_date_dt

class FishMappingRepository(BaseRepository):
    _instance = None

    def __new__(cls, db, collection_name="fish_mapping"):
        if cls._instance is None:
            cls._instance = super(FishMappingRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="fish_mapping"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)
    # Add more methods as needed

    def create_or_update_mapping(self, fish_doc):
        fish_id = fish_doc.get('_id')
        species_code = fish_doc.get('species_code') if fish_doc else None
        account_key = species_code or fish_id
        mapping = {
            'fish_id': fish_id,
            'account_key': account_key,
            'species_code': species_code,
            'common_name': fish_doc.get('common_name') if fish_doc else None,
        }
        mapping['updated_at'] = get_time_date_dt(include_time=True)
        return self.collection.update_one({'fish_id': fish_id}, {'$set': mapping}, upsert=True)

    def add_fish_to_account(self, account_key, fish_id):
        try:
            return self.collection.update_one({'account_key': account_key}, {'$addToSet': {'fish_ids': fish_id}}, upsert=True)
        except Exception:
            return None

    def get_fish_ids_for_account(self, account_key):
        doc = self.collection.find_one({'account_key': account_key})
        return doc.get('fish_ids', []) if doc else []
