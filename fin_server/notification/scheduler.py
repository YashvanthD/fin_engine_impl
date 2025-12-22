import time
import threading
from datetime import datetime
from fin_server.utils.time_utils import get_time_date
from .worker import NotificationWorker
from fin_server.repository.task_repository import TaskRepository
import logging

class TaskScheduler:
    def __init__(self, interval_seconds=60):
        self.interval = interval_seconds
        self.worker = NotificationWorker()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.running = False
        self.task_repository = TaskRepository()

    def start(self):
        self.running = True
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def run(self):
        while self.running:
            self.check_and_notify()
            time.sleep(self.interval)

    def check_and_notify(self):
        now = datetime.now()
        now_seconds = now.hour * 3600 + now.minute * 60 + now.second
        next_seconds = now_seconds + self.interval
        # Use IST date string for matching end_date stored in tasks
        today_str = get_time_date(include_time=False)
        # Find tasks with reminders due in the next interval (seconds), or overdue
        tasks = self.task_repository.collection.find({
            '$or': [
                {
                    'reminder': True,
                    'reminder_time': {'$exists': True},
                    'end_date': today_str
                },
                {
                    'status': {'$ne': 'completed'},
                    'end_date': {'$lte': today_str}
                }
            ]
        })
        for task in tasks:
            reminder_time_str = task.get('reminder_time')
            if reminder_time_str:
                try:
                    # Accept HH:MM:SS or HH:MM
                    parts = [int(p) for p in reminder_time_str.split(':')]
                    if len(parts) == 2:
                        reminder_seconds = parts[0] * 3600 + parts[1] * 60
                    elif len(parts) == 3:
                        reminder_seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                    else:
                        continue
                    logging.info(f"[Scheduler] Checking task '{task.get('title')}' at {reminder_time_str} ({reminder_seconds}s), now={now_seconds}s, next={next_seconds}s")
                    if now_seconds <= reminder_seconds < next_seconds:
                        logging.info(f"[Scheduler] Enqueueing notification for task '{task.get('title')}'")
                        self.worker.enqueue_notification(task)
                except Exception as e:
                    logging.error(f"[Scheduler] Error parsing reminder_time: {reminder_time_str} - {e}")
                    continue
            # Overdue tasks
            elif task.get('status', '').lower() != 'completed' and task.get('end_date') == today_str:
                logging.info(f"[Scheduler] Enqueueing overdue notification for task '{task.get('title')}'")
                self.worker.enqueue_notification(task)
