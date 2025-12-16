class FishMappingRepository:
    def __init__(self, collection):
        self.collection = collection

    def update_one(self, *args, **kwargs):
        return self.collection.update_one(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        return self.collection.find_one(*args, **kwargs)
    # Add more methods as needed

    def create_or_update_mapping(self, fish_doc):
        """Create or update a mapping document that links fish_id to account_key.

        account_key will be set to fish_doc['species_code'] if present, otherwise fallback to fish_doc['_id'].
        Upsert is performed using fish_id as the unique key.
        """
        fish_id = fish_doc.get('_id')
        species_code = fish_doc.get('species_code') if fish_doc else None
        account_key = species_code or fish_id
        mapping = {
            'fish_id': fish_id,
            'account_key': account_key,
            'species_code': species_code,
            'common_name': fish_doc.get('common_name') if fish_doc else None,
        }
        # add timestamps if available
        from datetime import datetime, timezone
        mapping['updated_at'] = datetime.now(timezone.utc)
        # perform upsert by fish_id
        return self.collection.update_one({'fish_id': fish_id}, {'$set': mapping}, upsert=True)

    def add_fish_to_account(self, account_key, fish_id):
        """Add a fish_id to the account mapping document (idempotent). Creates document if missing."""
        try:
            return self.collection.update_one({'account_key': account_key}, {'$addToSet': {'fish_ids': fish_id}}, upsert=True)
        except Exception as e:
            # Let caller handle logging; return None for failure
            return None

    def get_fish_ids_for_account(self, account_key):
        doc = self.collection.find_one({'account_key': account_key})
        return doc.get('fish_ids', []) if doc else []
