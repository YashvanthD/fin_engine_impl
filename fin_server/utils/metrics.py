"""Simple in-memory metrics collector for HTTP API endpoints.

This collector stores counts and status-code breakdowns keyed by HTTP method + route
pattern (when available) to help identify which API endpoints are hit most and their
success/failure distribution.

This is an in-memory, thread-safe collector intended for lightweight observability
and debugging. For production you might export these metrics to Prometheus/Influx/Datadog
or persist them to a durable store.

API:
- collector.record(method, route, status_code, duration_ms)
- collector.get_metrics() -> dict snapshot
- collector.reset()
"""
from collections import defaultdict
from threading import Lock
from typing import Dict, Any


class MetricsCollector:
    def __init__(self):
        # key -> {hits: int, total_time_ms: float, status: {code: count}}
        self._data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {'hits': 0, 'total_time_ms': 0.0, 'status': defaultdict(int)})
        self._lock = Lock()

    def record(self, method: str, route: str, status_code: int, duration_ms: float):
        key = f"{method} {route}"
        with self._lock:
            entry = self._data[key]
            entry['hits'] += 1
            entry['total_time_ms'] += float(duration_ms or 0.0)
            entry['status'][int(status_code)] += 1

    def get_metrics(self) -> Dict[str, Any]:
        # Return a snapshot (copy) of aggregated metrics
        with self._lock:
            snapshot = {}
            for key, entry in self._data.items():
                hits = entry.get('hits', 0)
                total_time = entry.get('total_time_ms', 0.0)
                avg_ms = (total_time / hits) if hits else 0.0
                status_map = {str(k): v for k, v in entry.get('status', {}).items()}
                snapshot[key] = {
                    'hits': hits,
                    'total_time_ms': round(total_time, 2),
                    'avg_time_ms': round(avg_ms, 2),
                    'status_counts': status_map,
                }
            return snapshot

    def reset(self):
        with self._lock:
            self._data.clear()


# Shared singleton collector instance
collector = MetricsCollector()

