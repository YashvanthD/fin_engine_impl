// Task Page JS
async function fetchTasks() {
    try {
        const accessToken = window.getAccessToken();
        const res = await window.authFetch(`${window.BASE_URL}/task/`, {
            method: 'GET'
        }, window.BASE_URL);
        const result = await res.json();
        const taskList = document.getElementById('taskList');
        taskList.innerHTML = '';
        if (!res.ok) {
            let msg = result.error || result.message || 'Failed to fetch tasks.';
            taskList.textContent = msg;
            console.error('Task fetch error:', msg);
            return;
        }
        if(result.tasks && result.tasks.length) {
            result.tasks.forEach(task => {
                const div = document.createElement('div');
                div.className = 'task-item';
                div.textContent = `${task.title} - ${task.status}`;
                taskList.appendChild(div);
            });
        } else {
            taskList.textContent = 'No tasks found.';
        }
    } catch (err) {
        document.getElementById('taskList').textContent = 'Unexpected error occurred. Please try again.';
        console.error('Unexpected task fetch error:', err);
    }
}
window.onload = fetchTasks;

function navigateTo(path) {
    window.location.href = path;
}

const taskForm = document.getElementById('taskForm');
if (taskForm) {
    taskForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const form = e.target;
        const data = {
            title: form.title.value,
            description: form.description.value,
            end_date: form.end_date.value,
            reminder_time: form.reminder_time.value,
            role: form.role.value,
            assignee: form.assignee.value
        };
        try {
            const accessToken = window.getAccessToken();
            const res = await window.authFetch(`${window.BASE_URL}/task/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            }, window.BASE_URL);
            const result = await res.json();
            if (!res.ok) {
                let msg = result.error || result.message || 'Task creation failed.';
                document.getElementById('response').textContent = msg;
                console.error('Task creation error:', msg);
                return;
            }
            document.getElementById('response').textContent = JSON.stringify(result, null, 2);
        } catch (err) {
            document.getElementById('response').textContent = 'Unexpected error occurred. Please try again.';
            console.error('Unexpected task creation error:', err);
        }
    });
}
