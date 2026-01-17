"""Alert Rules Service.

This module provides a rules engine for automatically triggering alerts
based on predefined thresholds and conditions for fish farm monitoring.

Usage:
    from fin_server.services.alert_rules_service import AlertRulesService

    # Check water quality thresholds
    AlertRulesService.check_water_quality(account_key, pond_id, pond_name, {
        'temperature': 34,
        'oxygen_level': 3.5,
        'ph_level': 8.8
    })

    # Check task deadlines
    AlertRulesService.check_task_deadline(account_key, task_id, task_name, due_date)
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from fin_server.websocket.handlers.alert_handler import AlertHandler

logger = logging.getLogger(__name__)


# =============================================================================
# Default Alert Rules Configuration
# =============================================================================

DEFAULT_ALERT_RULES = {
    # Water Quality Rules
    'water_temperature_high': {
        'name': 'High Water Temperature',
        'source': 'pond',
        'metric': 'temperature',
        'condition': 'gt',  # greater than
        'threshold': 32,
        'unit': '°C',
        'severity': 'high',
        'type': 'warning',
        'message_template': 'Water temperature in {pond_name} is {value}{unit} (threshold: {threshold}{unit})'
    },
    'water_temperature_critical': {
        'name': 'Critical Water Temperature',
        'source': 'pond',
        'metric': 'temperature',
        'condition': 'gt',
        'threshold': 35,
        'unit': '°C',
        'severity': 'critical',
        'type': 'critical',
        'message_template': 'CRITICAL: Water temperature in {pond_name} is {value}{unit}! Immediate action required.'
    },
    'water_temperature_low': {
        'name': 'Low Water Temperature',
        'source': 'pond',
        'metric': 'temperature',
        'condition': 'lt',  # less than
        'threshold': 20,
        'unit': '°C',
        'severity': 'medium',
        'type': 'warning',
        'message_template': 'Water temperature in {pond_name} is low: {value}{unit} (threshold: {threshold}{unit})'
    },
    'oxygen_level_low': {
        'name': 'Low Oxygen Level',
        'source': 'pond',
        'metric': 'oxygen_level',
        'condition': 'lt',
        'threshold': 5,
        'unit': 'mg/L',
        'severity': 'high',
        'type': 'warning',
        'message_template': 'Oxygen level in {pond_name} is low: {value}{unit} (threshold: {threshold}{unit})'
    },
    'oxygen_level_critical': {
        'name': 'Critical Oxygen Level',
        'source': 'pond',
        'metric': 'oxygen_level',
        'condition': 'lt',
        'threshold': 3,
        'unit': 'mg/L',
        'severity': 'critical',
        'type': 'critical',
        'message_template': 'CRITICAL: Oxygen level in {pond_name} is dangerously low: {value}{unit}! Fish at risk.'
    },
    'ph_level_high': {
        'name': 'High pH Level',
        'source': 'pond',
        'metric': 'ph_level',
        'condition': 'gt',
        'threshold': 8.5,
        'unit': '',
        'severity': 'medium',
        'type': 'warning',
        'message_template': 'pH level in {pond_name} is high: {value} (threshold: {threshold})'
    },
    'ph_level_low': {
        'name': 'Low pH Level',
        'source': 'pond',
        'metric': 'ph_level',
        'condition': 'lt',
        'threshold': 6.5,
        'unit': '',
        'severity': 'medium',
        'type': 'warning',
        'message_template': 'pH level in {pond_name} is low: {value} (threshold: {threshold})'
    },
    'ammonia_high': {
        'name': 'High Ammonia Level',
        'source': 'pond',
        'metric': 'ammonia',
        'condition': 'gt',
        'threshold': 0.5,
        'unit': 'mg/L',
        'severity': 'high',
        'type': 'warning',
        'message_template': 'Ammonia level in {pond_name} is high: {value}{unit} (threshold: {threshold}{unit})'
    },
    'nitrite_high': {
        'name': 'High Nitrite Level',
        'source': 'pond',
        'metric': 'nitrite',
        'condition': 'gt',
        'threshold': 0.5,
        'unit': 'mg/L',
        'severity': 'high',
        'type': 'warning',
        'message_template': 'Nitrite level in {pond_name} is high: {value}{unit} (threshold: {threshold}{unit})'
    },

    # Fish Health Rules
    'mortality_rate_high': {
        'name': 'High Mortality Rate',
        'source': 'fish',
        'metric': 'mortality_rate',
        'condition': 'gt',
        'threshold': 2,
        'unit': '%',
        'severity': 'high',
        'type': 'warning',
        'message_template': 'High mortality rate detected in {pond_name}: {value}%'
    },
    'mortality_rate_critical': {
        'name': 'Critical Mortality Rate',
        'source': 'fish',
        'metric': 'mortality_rate',
        'condition': 'gt',
        'threshold': 5,
        'unit': '%',
        'severity': 'critical',
        'type': 'critical',
        'message_template': 'CRITICAL: Mortality rate in {pond_name} is {value}%! Investigation required.'
    },

    # Task Rules
    'task_overdue': {
        'name': 'Task Overdue',
        'source': 'task',
        'condition': 'overdue',
        'severity': 'medium',
        'type': 'warning',
        'message_template': 'Task "{task_name}" is overdue by {days} day(s)'
    },
    'task_due_soon': {
        'name': 'Task Due Soon',
        'source': 'task',
        'condition': 'due_within_hours',
        'threshold': 24,
        'severity': 'low',
        'type': 'info',
        'message_template': 'Task "{task_name}" is due in {hours} hour(s)'
    },

    # Feeding Rules
    'feeding_missed': {
        'name': 'Feeding Missed',
        'source': 'feeding',
        'condition': 'missed',
        'severity': 'high',
        'type': 'warning',
        'message_template': 'Feeding missed for {pond_name}'
    },
    'feed_stock_low': {
        'name': 'Feed Stock Low',
        'source': 'feeding',
        'metric': 'feed_stock',
        'condition': 'lt',
        'threshold': 100,
        'unit': 'kg',
        'severity': 'medium',
        'type': 'warning',
        'message_template': 'Feed stock is running low: {value}{unit} remaining'
    }
}


class AlertRulesService:
    """Service for evaluating alert rules and triggering alerts."""

    _rules = DEFAULT_ALERT_RULES
    _cooldown_cache: Dict[str, datetime] = {}  # Prevent alert spam
    COOLDOWN_MINUTES = 30  # Minimum time between same alerts

    @classmethod
    def get_rules(cls) -> Dict[str, Any]:
        """Get all configured alert rules."""
        return cls._rules.copy()

    @classmethod
    def get_rule(cls, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific rule by ID."""
        return cls._rules.get(rule_id)

    @classmethod
    def _check_cooldown(cls, cache_key: str) -> bool:
        """Check if alert is in cooldown period.

        Returns True if alert should be suppressed (in cooldown).
        """
        if cache_key in cls._cooldown_cache:
            last_alert = cls._cooldown_cache[cache_key]
            if datetime.utcnow() - last_alert < timedelta(minutes=cls.COOLDOWN_MINUTES):
                return True
        return False

    @classmethod
    def _set_cooldown(cls, cache_key: str):
        """Set cooldown for an alert."""
        cls._cooldown_cache[cache_key] = datetime.utcnow()

    @classmethod
    def _evaluate_condition(cls, condition: str, value: float, threshold: float) -> bool:
        """Evaluate a condition against a value and threshold."""
        if condition == 'gt':  # greater than
            return value > threshold
        elif condition == 'gte':  # greater than or equal
            return value >= threshold
        elif condition == 'lt':  # less than
            return value < threshold
        elif condition == 'lte':  # less than or equal
            return value <= threshold
        elif condition == 'eq':  # equal
            return value == threshold
        elif condition == 'ne':  # not equal
            return value != threshold
        return False

    @classmethod
    def check_water_quality(
        cls,
        account_key: str,
        pond_id: str,
        pond_name: str,
        data: Dict[str, Any],
        created_by: str = 'system'
    ) -> List[str]:
        """Check water quality data against alert rules.

        Args:
            account_key: Account key
            pond_id: Pond ID
            pond_name: Pond name for alert messages
            data: Water quality data dict with keys like:
                  temperature, oxygen_level, ph_level, ammonia, nitrite
            created_by: User or 'system'

        Returns:
            List of alert IDs created
        """
        print(f"ALERT_RULES: Checking water quality for pond {pond_name}")

        alerts_created = []

        # Metric to rule mapping
        metric_rules = {
            'temperature': ['water_temperature_critical', 'water_temperature_high', 'water_temperature_low'],
            'oxygen_level': ['oxygen_level_critical', 'oxygen_level_low'],
            'ph_level': ['ph_level_high', 'ph_level_low'],
            'ammonia': ['ammonia_high'],
            'nitrite': ['nitrite_high'],
            'dissolved_oxygen': ['oxygen_level_critical', 'oxygen_level_low'],  # Alias
            'do': ['oxygen_level_critical', 'oxygen_level_low'],  # Alias
            'ph': ['ph_level_high', 'ph_level_low'],  # Alias
        }

        for metric, value in data.items():
            if value is None:
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                continue

            rule_ids = metric_rules.get(metric.lower(), [])

            for rule_id in rule_ids:
                rule = cls._rules.get(rule_id)
                if not rule:
                    continue

                # Check if rule metric matches
                rule_metric = rule.get('metric', '').lower()
                if metric.lower() not in [rule_metric, 'dissolved_oxygen', 'do', 'ph']:
                    if rule_metric != metric.lower().replace('_', ''):
                        continue

                threshold = rule.get('threshold')
                condition = rule.get('condition')

                if threshold is None or condition is None:
                    continue

                # Evaluate condition
                if cls._evaluate_condition(condition, value, threshold):
                    # Check cooldown
                    cache_key = f"{account_key}:{pond_id}:{rule_id}"
                    if cls._check_cooldown(cache_key):
                        print(f"ALERT_RULES: Suppressing {rule_id} (cooldown)")
                        continue

                    # Create alert
                    message = rule.get('message_template', '').format(
                        pond_name=pond_name,
                        value=round(value, 2),
                        threshold=threshold,
                        unit=rule.get('unit', '')
                    )

                    print(f"ALERT_RULES: Triggering alert - {rule.get('name')}: {message}")

                    alert_id = AlertHandler.create_and_emit(
                        account_key=account_key,
                        title=rule.get('name'),
                        message=message,
                        alert_type=rule.get('type', 'warning'),
                        severity=rule.get('severity', 'medium'),
                        source='pond',
                        source_id=pond_id,
                        created_by=created_by
                    )

                    if alert_id:
                        alerts_created.append(alert_id)
                        cls._set_cooldown(cache_key)

        return alerts_created

    @classmethod
    def check_mortality_rate(
        cls,
        account_key: str,
        pond_id: str,
        pond_name: str,
        mortality_rate: float,
        created_by: str = 'system'
    ) -> Optional[str]:
        """Check mortality rate against thresholds.

        Args:
            account_key: Account key
            pond_id: Pond ID
            pond_name: Pond name
            mortality_rate: Current mortality rate percentage
            created_by: User or 'system'

        Returns:
            Alert ID if created, None otherwise
        """
        print(f"ALERT_RULES: Checking mortality rate for {pond_name}: {mortality_rate}%")

        # Check critical first, then high
        for rule_id in ['mortality_rate_critical', 'mortality_rate_high']:
            rule = cls._rules.get(rule_id)
            if not rule:
                continue

            threshold = rule.get('threshold')
            if mortality_rate > threshold:
                cache_key = f"{account_key}:{pond_id}:{rule_id}"
                if cls._check_cooldown(cache_key):
                    continue

                message = rule.get('message_template', '').format(
                    pond_name=pond_name,
                    value=round(mortality_rate, 2)
                )

                print(f"ALERT_RULES: Triggering alert - {rule.get('name')}")

                alert_id = AlertHandler.create_and_emit(
                    account_key=account_key,
                    title=rule.get('name'),
                    message=message,
                    alert_type=rule.get('type', 'warning'),
                    severity=rule.get('severity', 'high'),
                    source='fish',
                    source_id=pond_id,
                    created_by=created_by
                )

                if alert_id:
                    cls._set_cooldown(cache_key)
                    return alert_id

        return None

    @classmethod
    def check_task_deadline(
        cls,
        account_key: str,
        task_id: str,
        task_name: str,
        due_date: datetime,
        created_by: str = 'system'
    ) -> Optional[str]:
        """Check task deadline and create alerts if overdue or due soon.

        Args:
            account_key: Account key
            task_id: Task ID
            task_name: Task name
            due_date: Task due date
            created_by: User or 'system'

        Returns:
            Alert ID if created, None otherwise
        """
        now = datetime.utcnow()

        # Check if overdue
        if due_date < now:
            days_overdue = (now - due_date).days
            rule = cls._rules.get('task_overdue')

            cache_key = f"{account_key}:{task_id}:task_overdue"
            if cls._check_cooldown(cache_key):
                return None

            message = rule.get('message_template', '').format(
                task_name=task_name,
                days=days_overdue
            )

            print(f"ALERT_RULES: Task overdue - {task_name} by {days_overdue} days")

            alert_id = AlertHandler.create_and_emit(
                account_key=account_key,
                title=rule.get('name', 'Task Overdue'),
                message=message,
                alert_type=rule.get('type', 'warning'),
                severity=rule.get('severity', 'medium'),
                source='task',
                source_id=task_id,
                created_by=created_by
            )

            if alert_id:
                cls._set_cooldown(cache_key)
            return alert_id

        # Check if due soon (within threshold hours)
        rule = cls._rules.get('task_due_soon')
        threshold_hours = rule.get('threshold', 24)
        hours_until_due = (due_date - now).total_seconds() / 3600

        if 0 < hours_until_due <= threshold_hours:
            cache_key = f"{account_key}:{task_id}:task_due_soon"
            if cls._check_cooldown(cache_key):
                return None

            message = rule.get('message_template', '').format(
                task_name=task_name,
                hours=int(hours_until_due)
            )

            print(f"ALERT_RULES: Task due soon - {task_name} in {int(hours_until_due)} hours")

            alert_id = AlertHandler.create_and_emit(
                account_key=account_key,
                title=rule.get('name', 'Task Due Soon'),
                message=message,
                alert_type=rule.get('type', 'info'),
                severity=rule.get('severity', 'low'),
                source='task',
                source_id=task_id,
                created_by=created_by
            )

            if alert_id:
                cls._set_cooldown(cache_key)
            return alert_id

        return None

    @classmethod
    def check_feed_stock(
        cls,
        account_key: str,
        current_stock: float,
        created_by: str = 'system'
    ) -> Optional[str]:
        """Check feed stock level and alert if low.

        Args:
            account_key: Account key
            current_stock: Current feed stock in kg
            created_by: User or 'system'

        Returns:
            Alert ID if created, None otherwise
        """
        rule = cls._rules.get('feed_stock_low')
        if not rule:
            return None

        threshold = rule.get('threshold', 100)

        if current_stock < threshold:
            cache_key = f"{account_key}:feed_stock_low"
            if cls._check_cooldown(cache_key):
                return None

            message = rule.get('message_template', '').format(
                value=round(current_stock, 1),
                unit=rule.get('unit', 'kg')
            )

            print(f"ALERT_RULES: Feed stock low - {current_stock}kg")

            alert_id = AlertHandler.create_and_emit(
                account_key=account_key,
                title=rule.get('name', 'Feed Stock Low'),
                message=message,
                alert_type=rule.get('type', 'warning'),
                severity=rule.get('severity', 'medium'),
                source='feeding',
                created_by=created_by
            )

            if alert_id:
                cls._set_cooldown(cache_key)
            return alert_id

        return None

    @classmethod
    def create_custom_alert(
        cls,
        account_key: str,
        title: str,
        message: str,
        alert_type: str = 'info',
        severity: str = 'low',
        source: str = 'system',
        source_id: str = None,
        created_by: str = None
    ) -> Optional[str]:
        """Create a custom alert bypassing rules.

        Use this for one-off alerts not covered by standard rules.
        """
        print(f"ALERT_RULES: Creating custom alert - {title}")

        return AlertHandler.create_and_emit(
            account_key=account_key,
            title=title,
            message=message,
            alert_type=alert_type,
            severity=severity,
            source=source,
            source_id=source_id,
            created_by=created_by
        )

    @classmethod
    def clear_cooldown_cache(cls):
        """Clear the cooldown cache (useful for testing)."""
        cls._cooldown_cache.clear()
        print("ALERT_RULES: Cooldown cache cleared")


# =============================================================================
# Convenience Functions
# =============================================================================

def check_water_quality_alerts(account_key: str, pond_id: str, pond_name: str, data: Dict) -> List[str]:
    """Convenience function to check water quality alerts."""
    return AlertRulesService.check_water_quality(account_key, pond_id, pond_name, data)


def check_task_alerts(account_key: str, task_id: str, task_name: str, due_date: datetime) -> Optional[str]:
    """Convenience function to check task deadline alerts."""
    return AlertRulesService.check_task_deadline(account_key, task_id, task_name, due_date)


def create_alert(account_key: str, title: str, message: str, **kwargs) -> Optional[str]:
    """Convenience function to create a custom alert."""
    return AlertRulesService.create_custom_alert(account_key, title, message, **kwargs)

