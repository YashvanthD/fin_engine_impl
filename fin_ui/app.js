// Utility to fetch dropdown data from API
async function fetchDropdown(endpoint, dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    dropdown.innerHTML = '<option>Loading...</option>';
    try {
        const res = await fetch(endpoint);
        const items = await res.json();
        dropdown.innerHTML = '';
        items.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.key || item;
            opt.textContent = item.name || item;
            dropdown.appendChild(opt);
        });
    } catch {
        dropdown.innerHTML = '<option>Error loading</option>';
    }
}

// Load roles and assignees on page load
window.onload = function() {
    fetchDropdown('/api/roles', 'roleDropdown');
    fetchDropdown('/api/users', 'assigneeDropdown');
    fetchDropdown('/api/users', 'moveAssigneeDropdown');
};

// Handle task creation
const taskForm = document.getElementById('taskForm');
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
        const res = await fetch('/task/', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await res.json();
        document.getElementById('response').textContent = JSON.stringify(result, null, 2);
    } catch (err) {
        document.getElementById('response').textContent = 'Error: ' + err;
    }
});

// Handle move task
const moveTaskForm = document.getElementById('moveTaskForm');
moveTaskForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const form = e.target;
    const data = {
        task_id: form.task_id.value,
        new_assignee: form.new_assignee.value
    };
    try {
        const res = await fetch('/task/move', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await res.json();
        document.getElementById('moveResponse').textContent = JSON.stringify(result, null, 2);
    } catch (err) {
        document.getElementById('moveResponse').textContent = 'Error: ' + err;
    }
});
