"""Dashboard routes for aggregated statistics and alerts.

This module provides endpoints for:
- Dashboard summary data (cards, metrics)
- Alerts listing and management
"""
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request

from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.decorators import handle_errors, require_auth
from fin_server.utils.helpers import respond_success, respond_error, normalize_doc

logger = logging.getLogger(__name__)

# Blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

# API Blueprint for /api prefix
dashboard_api_bp = Blueprint('dashboard_api', __name__, url_prefix='/api')

# Repositories
pond_repo = get_collection('pond')
task_repo = get_collection('task')
feeding_repo = get_collection('feeding')
sampling_repo = get_collection('sampling')
expenses_repo = get_collection('expenses')
fish_mapping_repo = get_collection('fish_mapping')


# =============================================================================
# Helper Functions
# =============================================================================

def _get_pond_count(account_key):
    """Get total number of ponds for account."""
    try:
        return pond_repo.count_documents({'account_key': account_key})
    except Exception:
        try:
            return len(list(pond_repo.find({'account_key': account_key})))
        except Exception:
            return 0


def _get_active_tasks_count(account_key):
    """Get count of active (non-completed) tasks."""
    try:
        return task_repo.count_documents({
            'account_key': account_key,
            'status': {'$nin': ['completed', 'done', 'cancelled']}
        })
    except Exception:
        try:
            tasks = list(task_repo.find({'account_key': account_key}))
            return sum(1 for t in tasks if t.get('status') not in ['completed', 'done', 'cancelled'])
        except Exception:
            return 0


def _get_critical_alerts_count(account_key):
    """Get count of unacknowledged critical alerts."""
    try:
        alerts_repo = get_collection('alerts')
        return alerts_repo.count_documents({
            'account_key': account_key,
            'severity': {'$in': ['critical', 'high', 'warning']},
            'acknowledged': {'$ne': True}
        })
    except Exception:
        return 0


def _get_total_stock(account_key):
    """Get total fish stock count from ponds."""
    try:
        ponds = list(pond_repo.find({'account_key': account_key}))
        total = 0
        for p in ponds:
            metadata = p.get('metadata', {})
            total += metadata.get('total_fish', 0)
        return total
    except Exception:
        return 0


def _get_average_growth_rate(account_key):
    """Calculate average growth rate from recent sampling records."""
    try:
        # Get samples from last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        samples = list(sampling_repo.find({
            'account_key': account_key,
            'created_at': {'$gte': thirty_days_ago}
        }).limit(100))

        if not samples:
            return 0.0

        growth_rates = []
        for s in samples:
            extra = s.get('extra', {})
            gr = extra.get('growth_rate') or extra.get('growthRate') or s.get('growth_rate')
            if gr is not None:
                try:
                    growth_rates.append(float(gr))
                except (TypeError, ValueError):
                    pass

        return round(sum(growth_rates) / len(growth_rates), 2) if growth_rates else 0.0
    except Exception:
        return 0.0


def _get_feed_efficiency(account_key):
    """Calculate feed conversion ratio from recent feeding records."""
    try:
        # Get feeding records from last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        feeds = list(feeding_repo.find({
            'account_key': account_key,
            'created_at': {'$gte': thirty_days_ago}
        }).limit(100))

        if not feeds:
            return 0.0

        total_feed = sum(f.get('quantity', 0) or f.get('feed_quantity', 0) for f in feeds)
        # Simple efficiency calculation (can be enhanced)
        return round(total_feed / len(feeds), 2) if feeds else 0.0
    except Exception:
        return 0.0


def _get_alerts(account_key, limit=10):
    """Get recent alerts for account."""
    try:
        alerts_repo = get_collection('alerts')
        cursor = alerts_repo.find({
            'account_key': account_key
        }).sort('timestamp', -1).limit(limit)

        return [normalize_doc(a) for a in cursor]
    except Exception:
        return []


def _build_dashboard_data(account_key):
    """Build complete dashboard data."""
    return {
        'cards': {
            'totalPonds': _get_pond_count(account_key),
            'activeTasks': _get_active_tasks_count(account_key),
            'criticalAlerts': _get_critical_alerts_count(account_key),
            'averageGrowthRate': _get_average_growth_rate(account_key),
            'totalStock': _get_total_stock(account_key),
            'feedEfficiency': _get_feed_efficiency(account_key),
        },
        'alerts': _get_alerts(account_key),
        'generated_at': datetime.now().isoformat(),
    }


# =============================================================================
# Dashboard Endpoints
# =============================================================================

@dashboard_bp.route('', methods=['GET'])
@dashboard_bp.route('/', methods=['GET'])
@handle_errors
@require_auth
def get_dashboard(auth_payload):
    """Get dashboard summary data including cards, metrics, and alerts."""
    logger.info('GET /dashboard called')

    account_key = auth_payload.get('account_key')
    if not account_key:
        return respond_error('Account key required', status=400)

    data = _build_dashboard_data(account_key)
    return respond_success(data)


# =============================================================================
# Alerts Endpoints (DEPRECATED - Use /api/notification/alert/* instead)
# =============================================================================

@dashboard_bp.route('/alerts', methods=['GET'])
@handle_errors
@require_auth
def get_alerts_list(auth_payload):
    """Get list of alerts for the account.

    DEPRECATED: Use GET /api/notification/alert/ instead.
    This endpoint will be removed in a future version.
    """
    logger.warning('DEPRECATED: GET /api/dashboard/alerts - Use GET /api/notification/alert/ instead')

    account_key = auth_payload.get('account_key')
    limit = int(request.args.get('limit', 50))

    alerts = _get_alerts(account_key, limit=limit)
    return respond_success({
        'alerts': alerts,
        '_deprecated': True,
        '_message': 'Use GET /api/notification/alert/ instead'
    })


@dashboard_bp.route('/alerts/<alert_id>/acknowledge', methods=['PUT'])
@handle_errors
@require_auth
def acknowledge_alert(alert_id, auth_payload):
    """Mark an alert as acknowledged.

    DEPRECATED: Use PUT /api/notification/alert/{alert_id}/acknowledge instead.
    This endpoint will be removed in a future version.
    """
    logger.warning(f'DEPRECATED: PUT /api/dashboard/alerts/{alert_id}/acknowledge - Use /api/notification/alert/{alert_id}/acknowledge instead')

    account_key = auth_payload.get('account_key')
    user_key = auth_payload.get('user_key')

    # Use the new AlertHandler
    from fin_server.websocket.handlers.alert_handler import AlertHandler
    success = AlertHandler.acknowledge_and_emit(alert_id, account_key, user_key)

    if success:
        return respond_success({
            'message': 'Alert acknowledged',
            'alert_id': alert_id,
            '_deprecated': True,
            '_message': 'Use PUT /api/notification/alert/{alert_id}/acknowledge instead'
        })
    else:
        return respond_error('Alert not found', status=404)


# =============================================================================
# NOTE: dashboard_api_bp routes removed - use main dashboard_bp with /api/dashboard prefix
# =============================================================================

