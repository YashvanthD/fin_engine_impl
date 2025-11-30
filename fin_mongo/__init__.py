from pymongo import MongoClient
from typing import Any, Dict, Optional, List

class MongoRepository:
    def __init__(self, uri: str, db_name: str, collection_name: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def create(self, document: Dict[str, Any]) -> str:
        """Insert a document into the collection."""
        result = self.collection.insert_one(document)
        return str(result.inserted_id)

    def read(self, query: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Find documents matching the query. If no query, return all."""
        if query is None:
            query = {}
        return list(self.collection.find(query))

    def update(self, query: Dict[str, Any], update_fields: Dict[str, Any]) -> int:
        """Update documents matching the query with update_fields."""
        result = self.collection.update_many(query, {'$set': update_fields})
        return result.modified_count

    def delete(self, query: Dict[str, Any]) -> int:
        """Delete documents matching the query."""
        result = self.collection.delete_many(query)
        return result.deleted_count

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single document matching the query."""
        return self.collection.find_one(query)

# Example usage (to be removed in production):
# repo = MongoRepository('mongodb://localhost:27017/', 'test_db', 'test_collection')
# repo.create({'name': 'Alice', 'age': 30, 'address': {'city': 'NY', 'zip': '10001'}})
# repo.read({'name': 'Alice'})
# repo.update({'name': 'Alice'}, {'age': 31})
# repo.delete({'name': 'Alice'})

