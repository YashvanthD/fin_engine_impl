import queue
import threading
import logging
from .dispatcher import NotificationDispatcher

class NotificationWorker:
    def __init__(self):
        self.q = queue.Queue()
        self.dispatcher = NotificationDispatcher()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.running = False

    def start(self):
        self.running = True
        self.thread.start()

    def stop(self):
        self.running = False
        self.thread.join()

    def enqueue_notification(self, task):
        self.q.put(task)

    def run(self):
        while self.running:
            try:
                task = self.q.get(timeout=1)
                logging.info(f"[Worker] Dequeued task '{task.get('title')}' for notification")
                self.dispatcher.send(task)
            except queue.Empty:
                continue
