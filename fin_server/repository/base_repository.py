from typing import Any, Dict, Optional

class BaseRepository:
    """Lightweight repository base that proxies common operations to an underlying
    pymongo collection if the subclass sets `self.collection` or passes a `db`
    and `collection_name` to the constructor.

    Subclasses may override any method where custom behaviour is required.
    """

    def __init__(self, db: Optional[Any] = None, collection_name: Optional[str] = None):
        self.db = db
        self.collection = None
        if db is not None and collection_name is not None:
            self.collection = db[collection_name]

    # --- Create / Read / Update / Delete helpers ---
    def create(self, data: Dict[str, Any]):
        """Insert a document and return inserted_id (or None)."""
        if self.collection is None:
            raise NotImplementedError('create() requires collection to be set')
        res = self.collection.insert_one(data)
        return getattr(res, 'inserted_id', None)

    def find(self, query: Optional[Dict[str, Any]] = None, *args, **kwargs):
        """Return a pymongo Cursor for the given query so callers can chain sort/limit."""
        if self.collection is None:
            raise NotImplementedError('find() requires collection to be set')
        if query is None:
            query = {}
        return self.collection.find(query, *args, **kwargs)

    def find_many(self, query: Optional[Dict[str, Any]] = None, limit: int = 0, skip: int = 0, sort: Optional[Any] = None):
        """Return a list of documents for the query (convenience wrapper)."""
        cursor = self.find(query)
        if sort:
            cursor = cursor.sort(sort)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def find_one(self, query: Dict[str, Any]):
        if self.collection is None:
            raise NotImplementedError('find_one() requires collection to be set')
        return self.collection.find_one(query)

    def update(self, query: Dict[str, Any], update_fields: Dict[str, Any], multi: bool = False):
        """Update documents and return modified_count."""
        if self.collection is None:
            raise NotImplementedError('update() requires collection to be set')
        if multi:
            res = self.collection.update_many(query, {'$set': update_fields})
        else:
            res = self.collection.update_one(query, {'$set': update_fields})
        return getattr(res, 'modified_count', None)

    def delete(self, query: Dict[str, Any], multi: bool = False):
        if self.collection is None:
            raise NotImplementedError('delete() requires collection to be set')
        if multi:
            res = self.collection.delete_many(query)
        else:
            res = self.collection.delete_one(query)
        return getattr(res, 'deleted_count', None)
