const UI = {
    toast(msg, type = 'success') {
        const el = document.createElement('div');
        el.className = `toast align-items-center text-bg-${type} border-0 show position-fixed top-0 end-0 m-3`;
        el.style.zIndex = 1055;
        el.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${msg}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>`;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    },
    statusBadge(status) {
        const map = {
            new: ['Новое', 'bg-new'],
            progress: ['В работе', 'bg-progress'],
            done: ['Завершено', 'bg-done'],
            reject: ['Отклонено', 'bg-reject']
        };
        const [txt, cls] = map[status] || ['Неизвестно', 'bg-secondary'];
        return `<span class="badge-status ${cls}">${txt}</span>`;
    }
};


document.addEventListener('DOMContentLoaded', () => {
    // Форма подачи обращения
    const form = document.getElementById('appealForm');
    if (form) {
        const desc = form.querySelector('[name="description"]');
        const countEl = document.getElementById('charCount');
        desc.addEventListener('input', () => {
            countEl.textContent = `${desc.value.length} / 2000`;
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!form.checkValidity()) {
                form.classList.add('was-validated');
                return;
            }
            const btn = document.getElementById('btnSubmit');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Отправка...';

            const formData = new FormData(form);
            const res = await fetch('/submit', {
                method: 'POST',
                body: new URLSearchParams(formData)
            });
            const data = await res.json();
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-send me-1"></i> Отправить обращение';

            if (data.success) {
                document.getElementById('modalCode').textContent = data.code;
                new bootstrap.Modal(document.getElementById('successModal')).show();
                form.reset();
                form.classList.remove('was-validated');
                countEl.textContent = '0 / 2000';
                UI.toast('Обращение успешно зарегистрировано');
            } else {
                UI.toast(data.error || 'Ошибка отправки', 'danger');
            }
        });
    }

    // Трекинг статуса
    const btnTrack = document.getElementById('btnTrack');
    if (btnTrack) {
        btnTrack.addEventListener('click', async () => {
            const code = document.getElementById('trackCode').value.trim().toUpperCase();
            if (!code) return UI.toast('Введите код отслеживания', 'warning');

            const res = await fetch('/api/track', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });
            const data = await res.json();

            document.getElementById('trackResult').classList.add('d-none');
            document.getElementById('trackEmpty').classList.add('d-none');

            if (data.success) {
                const d = data.data;
                document.getElementById('trackResult').classList.remove('d-none');
                document.getElementById('trTitle').textContent = d.title;
                document.getElementById('trCode').textContent = d.code;
                document.getElementById('trStatus').outerHTML = UI.statusBadge(d.status).replace('span', 'span id="trStatus"');
                document.getElementById('trType').textContent = d.type;
                document.getElementById('trCat').textContent = d.category;
                document.getElementById('trDate').textContent = d.date;
                document.getElementById('trDesc').textContent = d.description;

                const tl = document.getElementById('trTimeline');
                tl.innerHTML = '';
                d.history.forEach(h => {
                    tl.innerHTML += `
                        <div class="timeline-item">
                            <div class="timeline-dot ${h.status}"></div>
                            <div class="ms-2">
                                <strong>${UI.statusBadge(h.status)}</strong>
                                <small class="text-muted d-block">${h.date}</small>
                                <p class="mb-0 small mt-1">${h.comment || '-'}</p>
                                <small class="text-muted">Сотрудник: ${h.user}</small>
                            </div>
                        </div>`;
                });
            } else {
                document.getElementById('trackEmpty').classList.remove('d-none');
            }
        });
    }

    // Панель оператора
    window.appOp = {
        renderTable: async () => {
            const status = document.getElementById('opFilterStatus')?.value || 'all';
            const category = document.getElementById('opFilterCat')?.value || 'all';
            const search = document.getElementById('opSearch')?.value || '';

            const res = await fetch(`/api/operator/appeals?status=${status}&category=${category}&search=${search}`);
            const data = await res.json();
            const tb = document.getElementById('opTableBody');
            if (!tb) return;

            tb.innerHTML = '';
            if (!data.length) {
                tb.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Записи не найдены</td></tr>';
                return;
            }

            data.forEach(a => {
                tb.innerHTML += `
                    <tr>
                        <td><code>${a.code}</code></td>
                        <td>${a.type}</td>
                        <td class="text-truncate" style="max-width:250px">${a.title}</td>
                        <td>${UI.statusBadge(a.status)}</td>
                        <td>${a.date}</td>
                        <td class="text-end">
                            <button class="btn btn-outline-primary btn-sm" onclick="appOp.openModal(${a.id})">Изменить</button>
                        </td>
                    </tr>`;
            });
        },
        openModal: (id) => {
            document.getElementById('smId').value = id;
            document.getElementById('smComment').value = '';
            new bootstrap.Modal(document.getElementById('statusModal')).show();
        },
        saveStatus: async () => {
            const id = parseInt(document.getElementById('smId').value);
            const newStatus = document.getElementById('smNew').value;
            const comment = document.getElementById('smComment').value;

            const res = await fetch('/api/operator/status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id, new_status: newStatus, comment })
            });
            if ((await res.json()).success) {
                bootstrap.Modal.getInstance(document.getElementById('statusModal')).hide();
                UI.toast('Статус обновлён');
                appOp.renderTable();
            }
        }
    };
    if (document.getElementById('opTableBody')) appOp.renderTable();


    if (document.getElementById('chartStatus')) {
        const fetchAdminData = async () => {
            const sRes = await fetch('/api/admin/stats');
            const sData = await sRes.json();
            
            new Chart(document.getElementById('chartStatus'), {
                type: 'doughnut',
                data: {
                    labels: ['Новые', 'В работе', 'Завершены', 'Отклонены'],
                    datasets: [{
                        data: [sData.status.new, sData.status.progress, sData.status.done, sData.status.reject],
                        backgroundColor: ['#0dcaf0', '#fd7e14', '#198754', '#dc3545'],
                        borderWidth: 0
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });

            new Chart(document.getElementById('chartCat'), {
                type: 'bar',
                data: {
                    labels: Object.keys(sData.category),
                    datasets: [{
                        label: 'Количество',
                        data: Object.values(sData.category),
                        backgroundColor: '#0d6efd',
                        borderRadius: 6
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } }, x: { grid: { display: false } } } }
            });
        };
        fetchAdminData();

        const renderLogs = async () => {
            const res = await fetch('/api/admin/logs');
            const logs = await res.json();
            const el = document.getElementById('adminLogs');
            el.innerHTML = logs.map(l => `
                <div class="border-bottom pb-2 mb-2 small">
                    <div class="fw-semibold">${l.action}</div>
                    <div class="text-muted">${l.user} — ${l.detail} <span class="float-end">${l.timestamp}</span></div>
                </div>`).join('');
        };
        renderLogs();

        const renderUsers = async () => {
            const res = await fetch('/api/admin/users');
            const users = await res.json();
            document.getElementById('adminUsers').innerHTML = users.map(u => `
                <tr>
                    <td>${u.login}</td>
                    <td><span class="badge bg-${u.role === 'admin' ? 'primary' : 'success'}">${u.role}</span></td>
                    <td class="small text-muted">${u.created}</td>
                    <td>
                        <button class="btn btn-outline-danger btn-sm" onclick="delUser(${u.id})" ${u.login === 'admin' ? 'disabled' : ''}>
                            <i class="bi bi-trash"></i>
                        </button>
                    </td>
                </tr>`).join('');
        };
        renderUsers();

        window.delUser = async (id) => {
            if (!confirm('Удалить пользователя?')) return;
            await fetch(`/api/admin/users/${id}`, { method: 'DELETE' });
            renderUsers();
            UI.toast('Пользователь удалён');
        };

        document.getElementById('addUserForm')?.addEventListener('submit', async (e) => {
            e.preventDefault();
            const res = await fetch('/api/admin/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    login: document.getElementById('auLogin').value,
                    role: document.getElementById('auRole').value,
                    password: document.getElementById('auPass').value
                })
            });
            const d = await res.json();
            if (d.success) {
                UI.toast('Пользователь добавлен');
                e.target.reset();
                renderUsers();
            } else {
                UI.toast(d.error, 'danger');
            }
        });
    }
});