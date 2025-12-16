from abc import ABC, abstractmethod

class BaseRepository(ABC):
    @abstractmethod
    def create(self, data):
        """Insert a new document into the collection."""
        pass

    @abstractmethod
    def find(self, query=None):
        """Find multiple documents matching the query."""
        pass

    @abstractmethod
    def find_one(self, query):
        """Find a single document matching the query."""
        pass

    @abstractmethod
    def update(self, query, update_fields):
        """Update documents matching the query with the given fields."""
        pass

    @abstractmethod
    def delete(self, query):
        """Delete documents matching the query."""
        pass

