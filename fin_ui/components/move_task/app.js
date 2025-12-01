// Move Task Component JS
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

window.onload = function() {
    fetchDropdown('/api/users', 'moveAssigneeDropdown');
};

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
