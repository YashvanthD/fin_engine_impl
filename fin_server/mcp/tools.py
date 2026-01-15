"""MCP Tools for interacting with Fin Engine data.

This module provides tools that can be called by AI assistants to:
- Query and analyze fish data
- Access pond information
- Retrieve financial/expense data
- Get user and company information
- Generate reports and analytics
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from config import config

logger = logging.getLogger(__name__)


class MCPTools:
    """MCP Tools for data access and manipulation."""

    def __init__(self):
        self._repos = None  # Lazy initialization

    def _get_repos(self):
        """Lazy initialize repositories when first needed."""
        if self._repos is None:
            self._repos = {}
            try:
                from fin_server.repository.mongo_helper import get_collection
                self._repos = {
                    'users': get_collection('users'),
                    'companies': get_collection('companies'),
                    'fish': get_collection('fish'),
                    'fish_analytics': get_collection('fish_analytics'),
                    'fish_mapping': get_collection('fish_mapping'),
                    'pond': get_collection('pond'),
                    'pond_event': get_collection('pond_event'),
                    'expenses': get_collection('expenses'),
                    'transactions': get_collection('transactions'),
                    'feeding': get_collection('feeding'),
                    'sampling': get_collection('sampling'),
                }
                logger.info("MCP Tools repositories initialized")
            except Exception as e:
                logger.error(f"Failed to initialize MCP repositories: {e}")
        return self._repos

    def _get_repo(self, name: str):
        """Get a specific repository by name."""
        repos = self._get_repos()
        return repos.get(name) if repos else None

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get list of available MCP tool definitions."""
        return [
            {
                "name": "get_user_info",
                "description": "Get information about a user by user_key or account_key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_key": {"type": "string", "description": "User's unique key"},
                        "account_key": {"type": "string", "description": "Account key to get all users"},
                    },
                },
            },
            {
                "name": "get_company_info",
                "description": "Get company information and employee list",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Company's account key"},
                    },
                    "required": ["account_key"],
                },
            },
            {
                "name": "list_fish_species",
                "description": "List all fish species for an account with analytics",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                        "include_analytics": {"type": "boolean", "description": "Include analytics data", "default": True},
                    },
                    "required": ["account_key"],
                },
            },
            {
                "name": "get_fish_analytics",
                "description": "Get detailed analytics for a specific fish species",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "species_code": {"type": "string", "description": "Fish species code"},
                        "account_key": {"type": "string", "description": "Account key"},
                    },
                    "required": ["species_code", "account_key"],
                },
            },
            {
                "name": "list_ponds",
                "description": "List all ponds for an account",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                        "include_fish": {"type": "boolean", "description": "Include fish in each pond", "default": True},
                    },
                    "required": ["account_key"],
                },
            },
            {
                "name": "get_pond_details",
                "description": "Get detailed information about a specific pond",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pond_id": {"type": "string", "description": "Pond ID"},
                        "account_key": {"type": "string", "description": "Account key"},
                    },
                    "required": ["pond_id", "account_key"],
                },
            },
            {
                "name": "get_expenses",
                "description": "Get expenses/transactions for an account",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                        "start_date": {"type": "string", "description": "Start date (ISO format)"},
                        "end_date": {"type": "string", "description": "End date (ISO format)"},
                        "category": {"type": "string", "description": "Expense category filter"},
                        "limit": {"type": "integer", "description": "Max records to return", "default": 50},
                    },
                    "required": ["account_key"],
                },
            },
            {
                "name": "get_financial_summary",
                "description": "Get financial summary with totals by category",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                        "start_date": {"type": "string", "description": "Start date (ISO format)"},
                        "end_date": {"type": "string", "description": "End date (ISO format)"},
                    },
                    "required": ["account_key"],
                },
            },
            {
                "name": "get_feeding_records",
                "description": "Get feeding records for ponds",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                        "pond_id": {"type": "string", "description": "Filter by pond ID"},
                        "limit": {"type": "integer", "description": "Max records", "default": 50},
                    },
                    "required": ["account_key"],
                },
            },
            {
                "name": "get_sampling_data",
                "description": "Get water quality sampling data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                        "pond_id": {"type": "string", "description": "Filter by pond ID"},
                        "limit": {"type": "integer", "description": "Max records", "default": 50},
                    },
                    "required": ["account_key"],
                },
            },
            {
                "name": "search_data",
                "description": "Search across multiple collections",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                        "query": {"type": "string", "description": "Search query"},
                        "collections": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Collections to search: fish, ponds, expenses, feeding",
                        },
                    },
                    "required": ["account_key", "query"],
                },
            },
            {
                "name": "get_dashboard_summary",
                "description": "Get a complete dashboard summary for an account",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_key": {"type": "string", "description": "Account key"},
                    },
                    "required": ["account_key"],
                },
            },
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments."""
        tool_map = {
            "get_user_info": self._get_user_info,
            "get_company_info": self._get_company_info,
            "list_fish_species": self._list_fish_species,
            "get_fish_analytics": self._get_fish_analytics,
            "list_ponds": self._list_ponds,
            "get_pond_details": self._get_pond_details,
            "get_expenses": self._get_expenses,
            "get_financial_summary": self._get_financial_summary,
            "get_feeding_records": self._get_feeding_records,
            "get_sampling_data": self._get_sampling_data,
            "search_data": self._search_data,
            "get_dashboard_summary": self._get_dashboard_summary,
        }

        handler = tool_map.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return handler(**arguments)
        except Exception as e:
            logger.exception(f"Tool execution error: {tool_name}")
            return {"error": str(e)}

    # =========================================================================
    # Tool Implementations
    # =========================================================================

    def _get_user_info(self, user_key: str = None, account_key: str = None) -> Dict[str, Any]:
        """Get user information."""
        repo = self._repos.get('users')
        if not repo:
            return {"error": "Users repository not available"}

        if user_key:
            user = repo.find_one({'user_key': user_key})
            if user:
                user.pop('password', None)
                user.pop('refresh_tokens', None)
                user['_id'] = str(user.get('_id', ''))
                return {"user": user}
            return {"error": "User not found"}

        if account_key:
            users = list(repo.find({'account_key': account_key}))
            for u in users:
                u.pop('password', None)
                u.pop('refresh_tokens', None)
                u['_id'] = str(u.get('_id', ''))
            return {"users": users, "count": len(users)}

        return {"error": "Provide user_key or account_key"}

    def _get_company_info(self, account_key: str) -> Dict[str, Any]:
        """Get company information."""
        repo = self._repos.get('companies')
        if not repo:
            return {"error": "Companies repository not available"}

        company = repo.find_one({'account_key': account_key})
        if not company:
            return {"error": "Company not found"}

        company['_id'] = str(company.get('_id', ''))
        return {"company": company}

    def _list_fish_species(self, account_key: str, include_analytics: bool = True) -> Dict[str, Any]:
        """List all fish species for an account."""
        mapping_repo = self._repos.get('fish_mapping')
        fish_repo = self._repos.get('fish')
        analytics_repo = self._repos.get('fish_analytics')

        if not mapping_repo or not fish_repo:
            return {"error": "Fish repositories not available"}

        # Get mapped fish IDs
        mapping = mapping_repo.find_one({'account_key': account_key})
        fish_ids = mapping.get('fish_ids', []) if mapping else []

        if not fish_ids:
            return {"fish": [], "count": 0}

        # Get fish details
        fish_list = list(fish_repo.find({'_id': {'$in': fish_ids}}))

        result = []
        for fish in fish_list:
            fish_data = {
                'species_code': fish.get('_id'),
                'common_name': fish.get('common_name'),
                'scientific_name': fish.get('scientific_name'),
                'created_at': str(fish.get('created_at', '')),
            }

            if include_analytics and analytics_repo:
                try:
                    analytics = analytics_repo.get_analytics(fish.get('_id'), account_key=account_key)
                    fish_data['analytics'] = analytics
                except Exception:
                    pass

            result.append(fish_data)

        return {"fish": result, "count": len(result)}

    def _get_fish_analytics(self, species_code: str, account_key: str) -> Dict[str, Any]:
        """Get detailed fish analytics."""
        analytics_repo = self._repos.get('fish_analytics')
        fish_repo = self._repos.get('fish')

        if not analytics_repo:
            return {"error": "Analytics repository not available"}

        # Get fish details
        fish = fish_repo.find_one({'_id': species_code}) if fish_repo else None

        # Get analytics
        try:
            analytics = analytics_repo.get_analytics(species_code, account_key=account_key)
        except Exception as e:
            return {"error": f"Failed to get analytics: {e}"}

        return {
            "species_code": species_code,
            "fish": {
                'common_name': fish.get('common_name') if fish else None,
                'scientific_name': fish.get('scientific_name') if fish else None,
            } if fish else None,
            "analytics": analytics,
        }

    def _list_ponds(self, account_key: str, include_fish: bool = True) -> Dict[str, Any]:
        """List all ponds for an account."""
        pond_repo = self._repos.get('pond')
        pond_event_repo = self._repos.get('pond_event')

        if not pond_repo:
            return {"error": "Pond repository not available"}

        ponds = list(pond_repo.find({'account_key': account_key}))

        result = []
        for pond in ponds:
            pond_data = {
                'pond_id': pond.get('pond_id') or str(pond.get('_id', '')),
                'name': pond.get('name'),
                'size': pond.get('size'),
                'location': pond.get('location'),
                'status': pond.get('status'),
                'created_at': str(pond.get('created_at', '')),
            }

            if include_fish and pond_event_repo:
                try:
                    events = list(pond_event_repo.find({
                        'account_key': account_key,
                        'pond_id': pond_data['pond_id']
                    }))
                    species = list(set(e.get('species_code') for e in events if e.get('species_code')))
                    pond_data['fish_species'] = species
                except Exception:
                    pass

            result.append(pond_data)

        return {"ponds": result, "count": len(result)}

    def _get_pond_details(self, pond_id: str, account_key: str) -> Dict[str, Any]:
        """Get detailed pond information."""
        pond_repo = self._repos.get('pond')
        pond_event_repo = self._repos.get('pond_event')
        feeding_repo = self._repos.get('feeding')
        sampling_repo = self._repos.get('sampling')

        if not pond_repo:
            return {"error": "Pond repository not available"}

        pond = pond_repo.find_one({'pond_id': pond_id, 'account_key': account_key})
        if not pond:
            pond = pond_repo.find_one({'_id': pond_id})

        if not pond:
            return {"error": "Pond not found"}

        result = {
            'pond_id': pond.get('pond_id') or str(pond.get('_id', '')),
            'name': pond.get('name'),
            'size': pond.get('size'),
            'location': pond.get('location'),
            'status': pond.get('status'),
            'created_at': str(pond.get('created_at', '')),
        }

        # Get events
        if pond_event_repo:
            try:
                events = list(pond_event_repo.find({'pond_id': pond_id}).sort('created_at', -1).limit(10))
                result['recent_events'] = [
                    {
                        'type': e.get('event_type'),
                        'species_code': e.get('species_code'),
                        'count': e.get('count'),
                        'date': str(e.get('created_at', '')),
                    }
                    for e in events
                ]
            except Exception:
                pass

        # Get recent feeding
        if feeding_repo:
            try:
                feeding = list(feeding_repo.find({'pondId': pond_id}).sort('created_at', -1).limit(5))
                result['recent_feeding'] = [
                    {
                        'feed_type': f.get('feedType'),
                        'quantity': f.get('quantity'),
                        'date': str(f.get('created_at', '')),
                    }
                    for f in feeding
                ]
            except Exception:
                pass

        return result

    def _get_expenses(
        self,
        account_key: str,
        start_date: str = None,
        end_date: str = None,
        category: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get expenses for an account."""
        repo = self._repos.get('expenses')
        if not repo:
            return {"error": "Expenses repository not available"}

        query = {'account_key': account_key}

        if category:
            query['category'] = category

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                date_query['$lte'] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query['date'] = date_query

        try:
            expenses = list(repo.find(query).sort('date', -1).limit(limit))
        except Exception:
            expenses = list(repo.find(query))[:limit]

        result = []
        for e in expenses:
            result.append({
                'id': str(e.get('_id', '')),
                'category': e.get('category'),
                'amount': e.get('amount'),
                'description': e.get('description'),
                'date': str(e.get('date', '')),
                'pond_id': e.get('pond_id'),
            })

        return {"expenses": result, "count": len(result)}

    def _get_financial_summary(
        self,
        account_key: str,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """Get financial summary."""
        repo = self._repos.get('expenses')
        tx_repo = self._repos.get('transactions')

        if not repo:
            return {"error": "Expenses repository not available"}

        query = {'account_key': account_key}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query['$gte'] = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if end_date:
                date_query['$lte'] = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query['date'] = date_query

        try:
            expenses = list(repo.find(query))
        except Exception:
            expenses = []

        # Calculate totals by category
        by_category = {}
        total_amount = 0

        for e in expenses:
            cat = e.get('category', 'Other')
            amount = float(e.get('amount', 0))
            by_category[cat] = by_category.get(cat, 0) + amount
            total_amount += amount

        return {
            "total_expenses": total_amount,
            "by_category": by_category,
            "expense_count": len(expenses),
            "period": {
                "start": start_date,
                "end": end_date,
            }
        }

    def _get_feeding_records(
        self,
        account_key: str,
        pond_id: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get feeding records."""
        repo = self._repos.get('feeding')
        if not repo:
            return {"error": "Feeding repository not available"}

        query = {}
        if pond_id:
            query['pondId'] = pond_id

        try:
            records = list(repo.find(query).sort('created_at', -1).limit(limit))
        except Exception:
            records = list(repo.find(query))[:limit]

        result = []
        for r in records:
            result.append({
                'id': str(r.get('_id', '')),
                'pond_id': r.get('pondId'),
                'feed_type': r.get('feedType'),
                'quantity': r.get('quantity'),
                'unit': r.get('unit'),
                'date': str(r.get('created_at', '')),
            })

        return {"feeding_records": result, "count": len(result)}

    def _get_sampling_data(
        self,
        account_key: str,
        pond_id: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get water quality sampling data."""
        repo = self._repos.get('sampling')
        if not repo:
            return {"error": "Sampling repository not available"}

        query = {'account_key': account_key}
        if pond_id:
            query['pond_id'] = pond_id

        try:
            records = list(repo.find(query).sort('created_at', -1).limit(limit))
        except Exception:
            records = list(repo.find(query))[:limit]

        result = []
        for r in records:
            result.append({
                'id': str(r.get('_id', '')),
                'pond_id': r.get('pond_id'),
                'temperature': r.get('temperature'),
                'ph': r.get('ph'),
                'dissolved_oxygen': r.get('dissolved_oxygen'),
                'ammonia': r.get('ammonia'),
                'date': str(r.get('created_at', '')),
            })

        return {"sampling_records": result, "count": len(result)}

    def _search_data(
        self,
        account_key: str,
        query: str,
        collections: List[str] = None
    ) -> Dict[str, Any]:
        """Search across collections."""
        if not collections:
            collections = ['fish', 'pond', 'expenses']

        results = {}

        for coll_name in collections:
            repo = self._repos.get(coll_name)
            if not repo:
                continue

            try:
                # Simple text search
                search_query = {
                    'account_key': account_key,
                    '$or': [
                        {'name': {'$regex': query, '$options': 'i'}},
                        {'common_name': {'$regex': query, '$options': 'i'}},
                        {'description': {'$regex': query, '$options': 'i'}},
                        {'category': {'$regex': query, '$options': 'i'}},
                    ]
                }

                items = list(repo.find(search_query).limit(10))
                for item in items:
                    item['_id'] = str(item.get('_id', ''))

                results[coll_name] = items
            except Exception as e:
                results[coll_name] = {"error": str(e)}

        return {"search_results": results, "query": query}

    def _get_dashboard_summary(self, account_key: str) -> Dict[str, Any]:
        """Get complete dashboard summary."""
        summary = {
            "account_key": account_key,
            "generated_at": datetime.now().isoformat(),
        }

        # Company info
        company_result = self._get_company_info(account_key)
        if 'company' in company_result:
            summary['company_name'] = company_result['company'].get('company_name')
            summary['employee_count'] = company_result['company'].get('employee_count', 0)

        # Fish count
        fish_result = self._list_fish_species(account_key, include_analytics=False)
        summary['fish_species_count'] = fish_result.get('count', 0)

        # Pond count
        pond_result = self._list_ponds(account_key, include_fish=False)
        summary['pond_count'] = pond_result.get('count', 0)

        # Recent expenses
        expense_result = self._get_financial_summary(account_key)
        summary['total_expenses'] = expense_result.get('total_expenses', 0)
        summary['expense_categories'] = expense_result.get('by_category', {})

        # Recent feeding count
        feeding_result = self._get_feeding_records(account_key, limit=100)
        summary['recent_feeding_count'] = feeding_result.get('count', 0)

        return summary

