from datetime import datetime, timezone

class PondEventRepository:
    def __init__(self, db):
        self.collection = db['pond_events']

    def add_event(self, event_data):
        event_data['created_at'] = datetime.now(timezone.utc)
        return self.collection.insert_one(event_data)

    def get_events_by_pond(self, pond_id):
        return list(self.collection.find({'pond_id': pond_id}))

    def list_events(self, query=None):
        return list(self.collection.find(query or {}))

    def delete_event(self, event_id):
        return self.collection.delete_one({'_id': event_id})

