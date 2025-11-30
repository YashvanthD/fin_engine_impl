# Notification System Design

This package implements a scalable notification system for task reminders and overdue alerts.

**Components:**
- `scheduler.py`: Periodically scans the database for tasks needing notifications and enqueues jobs.
- `worker.py`: Background worker that processes notification jobs from a queue.
- `dispatcher.py`: Handles sending notifications (email, SMS, push, etc.).

**How it works:**
1. The scheduler runs every minute (configurable) and finds tasks with reminders or overdue status.
2. Each task is enqueued for notification.
3. The worker consumes jobs and calls the dispatcher to send notifications.
4. The dispatcher can be extended to integrate with any notification service.

**Extensibility:**
- Add new notification channels by extending `NotificationDispatcher`.
- Scale workers horizontally for high volume.
- Integrate with Celery, Redis, or other queue systems for production.

