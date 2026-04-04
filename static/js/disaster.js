let currentTasks = [];
let selectedTaskId = null;

// Weather Fetching
async function fetchWeather() {
    try {
        const res = await fetch('/api/weather');
        const data = await res.json();
        if (data.error) throw new Error(data.error);
        
        const container = document.getElementById('weather-forecast');
        const days = data.data[0].cuaca;
        let html = '';
        
        days.forEach((dayForecast, dayIdx) => {
            // Day Marker
            html += `
                <div class="wx-card" style="background:var(--accent-glow); border-color:var(--accent);">
                    <div class="wx-time">HARI</div>
                    <div class="wx-temp">${dayIdx + 1}</div>
                    <div class="wx-desc">BMKG Data</div>
                </div>
            `;
            
            dayForecast.forEach(f => {
                const time = f.local_datetime.split(' ')[1].substring(0, 5);
                html += `
                    <div class="wx-card">
                        <div class="wx-time">${time}</div>
                        <img class="wx-icon" src="${f.image.replace(' ', '%20')}" alt="">
                        <div class="wx-temp">${f.t}°C</div>
                        <div class="wx-desc">${f.weather_desc}</div>
                    </div>
                `;
            });
        });
        container.innerHTML = html;
    } catch (err) { console.error(err); }
}

let lastStatus = 'normal';

function showStatusNotification(level) {
    const existing = document.getElementById('status-notif-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'status-notif-toast';
    toast.className = 'status-notification';
    toast.innerHTML = `
        <div class="notif-icon">🔔</div>
        <div class="notif-content">
            <div class="notif-title">PANGGILAN TUGAS: ${level.toUpperCase()}</div>
            <div class="notif-text">Status berubah menjadi waspada! Ada instruksi SOP baru yang harus segera dilaksanakan.</div>
        </div>
        <div class="notif-close" onclick="this.parentElement.classList.remove('active')">✕</div>
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('active'), 100);
    setTimeout(() => { if (toast) toast.classList.remove('active'); }, 10000);
}

// Tasks Fetching
async function fetchTasks() {
    try {

        const res = await fetch('/api/events/active/tasks');
        const data = await res.json();
        currentTasks = data.tasks || [];
        const container = document.getElementById('tasks-container');
        const badge = document.getElementById('status-badge');

        if (!data.event_id && !data.event) {
            container.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted);">✨ Semua aman. Tidak ada penugasan aktif.</div>`;
            badge.className = 'status-badge status-normal';
            badge.innerText = 'AMAN';
            lastStatus = 'normal';
            return;
        }

        const currentLevel = data.status_level || 'waspada';
        badge.innerText = 'STATUS ' + currentLevel.toUpperCase();
        badge.className = 'status-badge status-waspada';

        if (lastStatus === 'normal') {
            showStatusNotification(currentLevel);
        }
        lastStatus = 'waspada';

        
        let html = '';
        currentTasks.forEach((task) => {
            const isDone = task.is_completed;
            const isSelected = selectedTaskId === task.id;
            
            html += `
                <div class="task-item ${isDone ? 'done' : ''} ${isSelected ? 'selected' : ''}" 
                     onclick="${isDone ? '' : `selectTask(${task.id})`}">
                    <div class="task-top">
                        <span class="task-title">${task.title}</span>
                        <span class="task-status">${isDone ? '✓ SELESAI' : 'LAPORKAN'}</span>
                    </div>
                    <div class="task-meta-small">
                        ${isDone ? `Selesai pada: ${new Date(task.completed_at).toLocaleString('id-ID')}` : 'Belum dilaporkan. Klik untuk mengisi form.'}
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    } catch (err) { console.error(err); }
}

function selectTask(id) {
    selectedTaskId = id;
    const task = currentTasks.find(t => t.id === id);
    
    document.getElementById('no-task-selected').style.display = 'none';
    document.getElementById('report-form-container').style.display = 'block';
    document.getElementById('selected-task-id').value = id;
    document.getElementById('selected-task-title').innerText = task.title;
    
    // Highlight selected task in middle list
    fetchTasks(); 
}

function deselectTask() {
    selectedTaskId = null;
    document.getElementById('no-task-selected').style.display = 'block';
    document.getElementById('report-form-container').style.display = 'none';
    const form = document.getElementById('incidentForm');
    if (form) form.reset();
    const photoText = document.getElementById('photo-text');
    if (photoText) photoText.innerText = '📸 Ambil/Pilih Foto';
    fetchTasks();
}

function previewTaskPhoto() {
    const file = document.getElementById('photo-input').files[0];
    if (file) document.getElementById('photo-text').innerText = `✅ ${file.name.substring(0,15)}...`;
}

async function submitIncident(e) {
    e.preventDefault();
    const form = e.target;
    const taskId = document.getElementById('selected-task-id').value;
    const btn = form.querySelector('.btn-submit');
    const formData = new FormData(form);
    
    btn.innerText = 'Mengirim Laporan...';
    btn.disabled = true;

    try {
        const res = await fetch(`/api/tasks/${taskId}/report`, { 
            method: 'POST', 
            body: formData 
        });
        const data = await res.json();
        if (data.status === 'success') {
            alert('Laporan penugasan berhasil dikirim!');
            deselectTask();
            fetchTasks();
        } else {
            alert('Gagal mengirim laporan: ' + data.message);
        }
    } catch (err) {
        alert('Terjadi kesalahan koneksi.');
    } finally {
        btn.innerText = 'Selesaikan Tugas & Kirim Laporan';
        btn.disabled = false;
    }
}

async function openHistory() {
    const modal = document.getElementById('historyModal');
    const container = document.getElementById('history-container');
    if (!modal || !container) return;

    modal.classList.add('active');
    container.innerHTML = '<div style="color: var(--text-muted); padding:2rem;">Memuat riwayat...</div>';

    try {
        const res = await fetch('/api/incidents/recent');
        const data = await res.json();
        
        if (data.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 2rem;">Belum ada laporan penyelesaian SOP bulan ini.</div>';
            return;
        }

        container.innerHTML = data.map(r => `
            <div class="report-log-item">
                <div class="log-meta">
                    <span>👤 ${r.author}</span>
                    <span>🕒 ${r.timestamp}</span>
                </div>
                <div class="log-title">${r.title}</div>
                <div class="log-body">
                    <p style="margin-bottom:0.5rem"><strong>Detail Laporan:</strong> ${r.content}</p>
                    ${r.actions_taken ? `<p style="margin-bottom:0.3rem"><strong>Penanganan:</strong> ${r.actions_taken}</p>` : ''}
                    ${r.planned_actions ? `<p style="margin-bottom:0.3rem"><strong>Rencana Perbaikan:</strong> ${r.planned_actions}</p>` : ''}
                    ${r.monitoring_notes ? `<p style="margin-bottom:0.3rem"><strong>Hasil Pantauan:</strong> ${r.monitoring_notes}</p>` : ''}
                </div>
            </div>
        `).join('');
    } catch (err) {
        container.innerHTML = '<div style="padding:2rem;">Gagal memuat riwayat.</div>';
    }
}

function closeHistory() {
    const modal = document.getElementById('historyModal');
    if (modal) modal.classList.remove('active');
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchWeather();
    fetchTasks();
    setInterval(fetchTasks, 20000);
});
