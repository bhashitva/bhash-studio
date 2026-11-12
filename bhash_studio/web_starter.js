// SPDX-License-Identifier: Apache-2.0
const form = document.querySelector('#add');
const titleInput = document.querySelector('#title');
const message = document.querySelector('#status');
const list = document.querySelector('#tasks');

async function api(path, method = 'GET', payload) {
    const options = { method };
    if (payload !== undefined) {
        options.headers = { 'Content-Type': 'application/json' };
        options.body = JSON.stringify(payload);
    }
    const response = await fetch(path, options);
    if (!response.ok) throw new Error('अनुरोध असफल: ' + response.status);
    return response.status === 204 ? null : response.json();
}

function showError(error) {
    message.textContent = error.message;
}

async function refreshTasks() {
    const tasks = await api('/api/tasks');
    list.replaceChildren();

    for (const task of tasks) {
        const path = '/api/tasks/' + encodeURIComponent(task.id);
        const row = document.createElement('li');
        const check = document.createElement('input');
        const title = document.createElement('span');
        const remove = document.createElement('button');
        check.type = 'checkbox';
        check.checked = task.done;
        check.setAttribute('aria-label', 'पूरा हुआ: ' + task.title);
        title.textContent = task.title;
        title.style.textDecoration = task.done ? 'line-through' : 'none';
        remove.textContent = 'हटाएँ';

        check.onchange = async () => {
            try {
                await api(path, 'PUT', { title: task.title, done: check.checked });
                await refreshTasks();
            } catch (error) {
                check.checked = task.done;
                showError(error);
            }
        };

        remove.onclick = async () => {
            try {
                await api(path, 'DELETE');
                await refreshTasks();
            } catch (error) {
                showError(error);
            }
        };

        row.append(check, title, remove);
        list.append(row);
    }
}

form.onsubmit = async (event) => {
    event.preventDefault();
    try {
        await api('/api/tasks', 'POST', { id: crypto.randomUUID(), title: titleInput.value });
        form.reset();
        message.textContent = 'कार्य सहेजा गया।';
        await refreshTasks();
    } catch (error) {
        showError(error);
    }
};

refreshTasks().catch(showError);
