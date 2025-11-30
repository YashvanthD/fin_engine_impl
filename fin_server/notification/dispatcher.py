import logging

class NotificationDispatcher:
    def send(self, task):
        user = task.get('assignee')
        message = self.build_message(task)
        # Log notification to console
        logging.info(f"Notify {user}: {message}")
        print(f"Notify {user}: {message}")

    def build_message(self, task):
        title = task.get('title', 'Task')
        status = task.get('status', 'pending')
        end_date = task.get('end_date')
        if status != 'completed' and end_date:
            return f"Reminder: '{title}' is due on {end_date}."
        return f"Task '{title}' status: {status}."
