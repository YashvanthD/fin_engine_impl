"""AI Usage Repository for tracking token consumption.

This module provides storage for AI API usage metrics including:
- Token counts per request
- Usage by account and user
- Historical usage tracking
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fin_server.repository.base_repository import BaseRepository


class AIUsageRepository(BaseRepository):
    """Repository for AI usage tracking."""

    _instance = None

    def __new__(cls, db, collection_name="ai_usage"):
        if cls._instance is None:
            cls._instance = super(AIUsageRepository, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db, collection_name="ai_usage"):
        if not getattr(self, "_initialized", False):
            super().__init__(db=db, collection_name=collection_name)
            self.collection_name = collection_name
            self._create_indexes()
            print(f"Initializing {self.collection_name} collection")
            self._initialized = True

    def _create_indexes(self):
        """Create indexes for efficient querying."""
        try:
            self.collection.create_index([('account_key', 1)], name='ai_usage_account')
            self.collection.create_index([('user_key', 1)], name='ai_usage_user')
            self.collection.create_index([('request_id', 1)], unique=True, name='ai_usage_request')
            self.collection.create_index([('created_at', -1)], name='ai_usage_date')
            self.collection.create_index([('account_key', 1), ('created_at', -1)], name='ai_usage_account_date')
        except Exception:
            pass

    # =========================================================================
    # Core CRUD Operations
    # =========================================================================

    def create(self, data: Dict[str, Any]) -> str:
        """Create a new AI usage record."""
        data = dict(data)
        data.setdefault('created_at', datetime.now(timezone.utc))
        result = self.collection.insert_one(data)
        return str(result.inserted_id)

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find a single usage record."""
        return self.collection.find_one(query)

    def find_many(self, query: Dict[str, Any] = None, limit: int = 100, skip: int = 0, sort: List = None) -> List[Dict[str, Any]]:
        """Find multiple usage records."""
        if query is None:
            query = {}
        cursor = self.collection.find(query)
        if sort:
            cursor = cursor.sort(sort)
        else:
            cursor = cursor.sort('created_at', -1)
        if skip:
            cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def update(self, query: Dict[str, Any], update_fields: Dict[str, Any]) -> int:
        """Update usage record(s)."""
        return self.collection.update_one(query, {'$set': update_fields}).modified_count

    def delete(self, query: Dict[str, Any]) -> int:
        """Delete usage record(s)."""
        return self.collection.delete_one(query).deleted_count

    # =========================================================================
    # AI Usage Specific Methods
    # =========================================================================

    def log_usage(
        self,
        account_key: str,
        user_key: str,
        request_id: str,
        tokens: Dict[str, int],
        model: str = None,
        endpoint: str = None,
        tool_name: str = None,
        success: bool = True,
        error: str = None,
        metadata: Dict[str, Any] = None,
        image_attached: bool = False,
        image_url: str = None,
    ) -> str:
        """Log an AI API usage record.

        Args:
            account_key: Account identifier
            user_key: User identifier
            request_id: Unique request identifier
            tokens: Token counts dict with prompt_tokens, completion_tokens, total_tokens
            model: AI model used (e.g., gpt-4o-mini)
            endpoint: API endpoint called (e.g., /ai/openai/query)
            tool_name: MCP tool name if applicable
            success: Whether the request was successful
            error: Error message if failed
            metadata: Additional metadata
            image_attached: Whether an image was included in the request
            image_url: URL of the image if provided via URL (not stored for base64)

        Returns:
            Created record ID
        """
        usage_doc = {
            'account_key': account_key,
            'user_key': user_key,
            'request_id': request_id,
            'tokens': {
                'prompt_tokens': tokens.get('prompt_tokens', 0),
                'completion_tokens': tokens.get('completion_tokens', 0),
                'total_tokens': tokens.get('total_tokens', 0),
            },
            'model': model,
            'endpoint': endpoint,
            'tool_name': tool_name,
            'success': success,
            'error': error,
            'metadata': metadata or {},
            'image_attached': image_attached,
            'image_url': image_url,
            'created_at': datetime.now(timezone.utc),
        }

        return self.create(usage_doc)

    def get_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get usage record by request ID."""
        return self.find_one({'request_id': request_id})

    def get_by_account(
        self,
        account_key: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get usage records for an account."""
        query = {'account_key': account_key}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['created_at'] = date_query

        return self.find_many(query, limit=limit)

    def get_by_user(
        self,
        user_key: str,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get usage records for a user."""
        query = {'user_key': user_key}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['created_at'] = date_query

        return self.find_many(query, limit=limit)

    def get_usage_summary(
        self,
        account_key: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """Get aggregated usage summary for an account.

        Returns:
            Summary dict with total tokens, request counts, etc.
        """
        query = {'account_key': account_key, 'success': True}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['created_at'] = date_query

        pipeline = [
            {'$match': query},
            {'$group': {
                '_id': '$account_key',
                'total_requests': {'$sum': 1},
                'total_prompt_tokens': {'$sum': '$tokens.prompt_tokens'},
                'total_completion_tokens': {'$sum': '$tokens.completion_tokens'},
                'total_tokens': {'$sum': '$tokens.total_tokens'},
                'models_used': {'$addToSet': '$model'},
                'first_request': {'$min': '$created_at'},
                'last_request': {'$max': '$created_at'},
            }}
        ]

        try:
            results = list(self.collection.aggregate(pipeline))
            if results:
                result = results[0]
                result.pop('_id', None)
                return result
        except Exception:
            pass

        return {
            'total_requests': 0,
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_tokens': 0,
            'models_used': [],
        }

    def get_usage_by_model(
        self,
        account_key: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get usage breakdown by model."""
        query = {'account_key': account_key, 'success': True}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['created_at'] = date_query

        pipeline = [
            {'$match': query},
            {'$group': {
                '_id': '$model',
                'request_count': {'$sum': 1},
                'total_tokens': {'$sum': '$tokens.total_tokens'},
                'prompt_tokens': {'$sum': '$tokens.prompt_tokens'},
                'completion_tokens': {'$sum': '$tokens.completion_tokens'},
            }},
            {'$sort': {'total_tokens': -1}}
        ]

        try:
            results = list(self.collection.aggregate(pipeline))
            return [{'model': r['_id'], **{k: v for k, v in r.items() if k != '_id'}} for r in results]
        except Exception:
            return []

    def get_usage_by_user(
        self,
        account_key: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Dict[str, Any]]:
        """Get usage breakdown by user within an account."""
        query = {'account_key': account_key, 'success': True}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['created_at'] = date_query

        pipeline = [
            {'$match': query},
            {'$group': {
                '_id': '$user_key',
                'request_count': {'$sum': 1},
                'total_tokens': {'$sum': '$tokens.total_tokens'},
            }},
            {'$sort': {'total_tokens': -1}}
        ]

        try:
            results = list(self.collection.aggregate(pipeline))
            return [{'user_key': r['_id'], **{k: v for k, v in r.items() if k != '_id'}} for r in results]
        except Exception:
            return []

    def get_daily_usage(
        self,
        account_key: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get daily usage for the last N days."""
        from datetime import timedelta

        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        pipeline = [
            {'$match': {
                'account_key': account_key,
                'success': True,
                'created_at': {'$gte': start_date}
            }},
            {'$group': {
                '_id': {
                    '$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}
                },
                'request_count': {'$sum': 1},
                'total_tokens': {'$sum': '$tokens.total_tokens'},
            }},
            {'$sort': {'_id': 1}}
        ]

        try:
            results = list(self.collection.aggregate(pipeline))
            return [{'date': r['_id'], **{k: v for k, v in r.items() if k != '_id'}} for r in results]
        except Exception:
            return []

    def get_image_usage_summary(
        self,
        account_key: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """Get summary of image-related usage for an account.

        Returns:
            Summary dict with image request counts and token usage.
        """
        query = {'account_key': account_key, 'success': True, 'image_attached': True}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = start_date
            if end_date:
                date_query['$lte'] = end_date
            query['created_at'] = date_query

        pipeline = [
            {'$match': query},
            {'$group': {
                '_id': '$account_key',
                'total_image_requests': {'$sum': 1},
                'total_tokens': {'$sum': '$tokens.total_tokens'},
                'requests_with_url': {
                    '$sum': {'$cond': [{'$ne': ['$image_url', None]}, 1, 0]}
                },
                'requests_with_base64': {
                    '$sum': {'$cond': [{'$eq': ['$image_url', None]}, 1, 0]}
                },
            }}
        ]

        try:
            results = list(self.collection.aggregate(pipeline))
            if results:
                result = results[0]
                result.pop('_id', None)
                return result
        except Exception:
            pass

        return {
            'total_image_requests': 0,
            'total_tokens': 0,
            'requests_with_url': 0,
            'requests_with_base64': 0,
        }

    def get_requests_with_images(
        self,
        account_key: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get usage records that include images.

        Args:
            account_key: Account identifier
            limit: Max records to return

        Returns:
            List of usage records with images
        """
        query = {'account_key': account_key, 'image_attached': True}
        return self.find_many(query, limit=limit)
