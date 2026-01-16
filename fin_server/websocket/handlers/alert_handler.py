"""Alert handler for WebSocket events.

This module handles alert-related WebSocket events and provides
helper functions to emit alerts via WebSocket.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fin_server.websocket.event_emitter import EventEmitter
from fin_server.repository.mongo_helper import get_collection
from fin_server.utils.generator import generate_uuid_hex
from fin_server.utils.time_utils import get_time_date_dt

logger = logging.getLogger(__name__)


class AlertHandler:
    """Handler for alert WebSocket events."""

    @staticmethod
    def create_and_emit(
        account_key: str,
        title: str,
        message: str,
        alert_type: str = 'warning',
        severity: str = 'medium',
        source: str = 'system',
        source_id: str = None,
        auto_dismiss: bool = False,
        dismiss_after_minutes: int = None,
        created_by: str = None
    ) -> Optional[str]:
        """Create an alert in DB and emit via WebSocket to all account users.

        Args:
            account_key: Account key
            title: Alert title
            message: Alert message
            alert_type: Type (info, warning, critical, success)
            severity: Severity (low, medium, high, critical)
            source: Source (system, pond, task, expense)
            source_id: Related entity ID
            auto_dismiss: Whether to auto-dismiss
            dismiss_after_minutes: Minutes until auto-dismiss
            created_by: User who created the alert

        Returns:
            Alert ID if successful, None otherwise
        """
        alerts_repo = get_collection('alerts')
        if not alerts_repo:
            logger.error("Alerts repository not available")
            return None

        # Create alert document
        alert_id = generate_uuid_hex(24)
        now = get_time_date_dt(include_time=True)

        alert_doc = {
            '_id': alert_id,
            'alert_id': alert_id,
            'account_key': account_key,
            'title': title,
            'message': message,
            'type': alert_type,
            'severity': severity,
            'source': source,
            'source_id': source_id,
            'acknowledged': False,
            'acknowledged_by': None,
            'acknowledged_at': None,
            'auto_dismiss': auto_dismiss,
            'dismiss_after_minutes': dismiss_after_minutes,
            'created_by': created_by,
            'created_at': now,
            'updated_at': now
        }

        try:
            # Save to database
            alerts_repo.create(alert_doc)

            # Emit via WebSocket to all account users
            EventEmitter.notify_account_alert(account_key, {
                'alert_id': alert_id,
                'title': title,
                'message': message,
                'type': alert_type,
                'severity': severity,
                'source': source,
                'source_id': source_id,
                'created_at': now.isoformat() if hasattr(now, 'isoformat') else str(now)
            })

            # Update unacknowledged count
            try:
                unack_count = alerts_repo.collection.count_documents({
                    'account_key': account_key,
                    'acknowledged': False
                })
                EventEmitter.update_alert_count(account_key, unack_count)
            except Exception:
                pass

            logger.info(f"Alert {alert_id} created and emitted to account {account_key}")
            return alert_id

        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None

    @staticmethod
    def acknowledge_and_emit(alert_id: str, account_key: str, user_key: str) -> bool:
        """Acknowledge an alert and emit update via WebSocket.

        Args:
            alert_id: Alert ID
            account_key: Account key
            user_key: User acknowledging the alert

        Returns:
            True if successful
        """
        alerts_repo = get_collection('alerts')
        if not alerts_repo:
            return False

        try:
            result = alerts_repo.update(
                {'alert_id': alert_id, 'account_key': account_key},
                {
                    'acknowledged': True,
                    'acknowledged_by': user_key,
                    'acknowledged_at': get_time_date_dt(include_time=True),
                    'updated_at': get_time_date_dt(include_time=True)
                }
            )

            if result.modified_count > 0:
                # Emit via WebSocket to all account users
                EventEmitter.emit_to_account(account_key, EventEmitter.ALERT_ACKNOWLEDGED, {
                    'alert_id': alert_id,
                    'acknowledged_by': user_key
                })

                # Update unacknowledged count
                try:
                    unack_count = alerts_repo.collection.count_documents({
                        'account_key': account_key,
                        'acknowledged': False
                    })
                    EventEmitter.update_alert_count(account_key, unack_count)
                except Exception:
                    pass

                return True
            return False

        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False

    @staticmethod
    def delete_and_emit(alert_id: str, account_key: str) -> bool:
        """Delete an alert and emit update via WebSocket.

        Args:
            alert_id: Alert ID
            account_key: Account key

        Returns:
            True if successful
        """
        alerts_repo = get_collection('alerts')
        if not alerts_repo:
            return False

        try:
            result = alerts_repo.delete({
                'alert_id': alert_id,
                'account_key': account_key
            })

            if result.deleted_count > 0:
                # Emit via WebSocket to all account users
                EventEmitter.emit_to_account(account_key, EventEmitter.ALERT_DELETED, {
                    'alert_id': alert_id
                })

                # Update unacknowledged count
                try:
                    unack_count = alerts_repo.collection.count_documents({
                        'account_key': account_key,
                        'acknowledged': False
                    })
                    EventEmitter.update_alert_count(account_key, unack_count)
                except Exception:
                    pass

                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting alert: {e}")
            return False

    # =========================================================================
    # Convenience methods for common alert types
    # =========================================================================

    @classmethod
    def create_pond_alert(
        cls,
        account_key: str,
        pond_id: str,
        title: str,
        message: str,
        severity: str = 'high',
        created_by: str = None
    ) -> Optional[str]:
        """Create a pond-related alert."""
        return cls.create_and_emit(
            account_key=account_key,
            title=title,
            message=message,
            alert_type='warning',
            severity=severity,
            source='pond',
            source_id=pond_id,
            created_by=created_by
        )

    @classmethod
    def create_task_alert(
        cls,
        account_key: str,
        task_id: str,
        title: str,
        message: str,
        severity: str = 'medium',
        created_by: str = None
    ) -> Optional[str]:
        """Create a task-related alert."""
        return cls.create_and_emit(
            account_key=account_key,
            title=title,
            message=message,
            alert_type='info',
            severity=severity,
            source='task',
            source_id=task_id,
            created_by=created_by
        )

    @classmethod
    def create_system_alert(
        cls,
        account_key: str,
        title: str,
        message: str,
        severity: str = 'low',
        created_by: str = None
    ) -> Optional[str]:
        """Create a system alert."""
        return cls.create_and_emit(
            account_key=account_key,
            title=title,
            message=message,
            alert_type='info',
            severity=severity,
            source='system',
            created_by=created_by
        )

    @classmethod
    def create_critical_alert(
        cls,
        account_key: str,
        title: str,
        message: str,
        source: str = 'system',
        source_id: str = None,
        created_by: str = None
    ) -> Optional[str]:
        """Create a critical alert."""
        return cls.create_and_emit(
            account_key=account_key,
            title=title,
            message=message,
            alert_type='critical',
            severity='critical',
            source=source,
            source_id=source_id,
            created_by=created_by
        )

