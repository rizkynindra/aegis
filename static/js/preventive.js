let currentTab = 'pending';
let allTasks = [];

async function fetchTasks() {
    try {
        const response = await fetch('/api/tasks/preventive');
        const data = await response.json();
        allTasks = data.tasks;
        renderTasks();
    } catch (err) {
        console.error('Error fetching tasks:', err);
    }
}

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.tab-btn[onclick="switchTab('${tab}')"]`).classList.add('active');
    renderTasks();
}

function renderTasks() {
    const container = document.getElementById('task-list');
    const pendingTasks = allTasks.filter(t => !t.is_completed);
    const completedTasks = allTasks.filter(t => t.is_completed);
    const filteredTasks = currentTab === 'completed' ? completedTasks : pendingTasks;
    
    // Update counts
    document.getElementById('pending-count').textContent = pendingTasks.length;
    document.getElementById('completed-count').textContent = completedTasks.length;

    if (pendingTasks.length === 0 && currentTab === 'pending') {
        container.innerHTML = `<div style="text-align: center; padding: 4rem; color: var(--status-completed);">
            <div style="font-size: 4rem; margin-bottom: 1rem;">🎯</div>
            <h2 style="font-weight: 800; letter-spacing: 1px;">MONTHLY DONE</h2>
            <p style="font-size: 0.9rem; margin-top: 0.5rem; color: var(--text-muted);">Checklist preventive bulan ini sudah lengkap.</p>
            <button class="btn-checklist" style="margin-top: 2rem; background: var(--input-bg); color: var(--text-muted);" onclick="switchTab('completed')">Lihat Riwayat Bulan Ini</button>
        </div>`;
        return;
    }

    if (filteredTasks.length === 0) {
        container.innerHTML = `<div style="text-align: center; padding: 4rem; color: var(--text-muted);">
            <div style="font-size: 3rem; margin-bottom: 1rem;">✨</div>
            <h3>${currentTab === 'completed' ? 'Belum ada bukti' : 'Sudah Beres!'}</h3>
            <p style="font-size: 0.85rem; margin-top: 0.5rem;">${currentTab === 'completed' ? 'Cek tab Pending untuk melengkapi laporan.' : 'Semua checklist preventive sudah selesai dilaporkan.'}</p>
        </div>`;
        return;
    }

    container.innerHTML = filteredTasks.map(t => `
        <div class="task-card" onclick="${!t.is_completed ? `openModal(${t.id}, '${t.title}')` : ''}">
            <div class="task-icon-wrapper">
                ${t.is_completed ? '✅' : '📝'}
            </div>
            <div class="task-info">
                <div class="task-title">${t.title}</div>
                <div class="task-meta">Due before 12:00</div>
            </div>
            <div class="task-action">
                ${t.is_completed 
                    ? `<span class="status-label done">${t.completed_at}</span>` 
                    : `<button class="btn-checklist">Checklist</button>`}
            </div>
        </div>
    `).join('');
}

function openModal(taskId, title) {
    document.getElementById('modal-task-id').value = taskId;
    document.getElementById('modal-task-title').textContent = title;
    document.getElementById('evidence-modal').style.display = 'flex';
    resetModal();
}

function closeModal() {
    document.getElementById('evidence-modal').style.display = 'none';
}

function resetModal() {
    document.getElementById('photo-input').value = '';
    document.getElementById('photo-preview-img').style.display = 'none';
    document.getElementById('preview-placeholder').style.display = 'block';
}

function handlePhotoSelect(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = document.getElementById('photo-preview-img');
            img.src = e.target.result;
            img.style.display = 'block';
            document.getElementById('preview-placeholder').style.display = 'none';
        };
        reader.readAsDataURL(file);
    }
}

async function submitReport(event) {
    event.preventDefault();
    const taskId = document.getElementById('modal-task-id').value;
    const photo = document.getElementById('photo-input').files[0];

    if (!photo) {
        alert('Harap lampirkan bukti foto!');
        return;
    }

    const formData = new FormData();
    formData.append('photo', photo);

    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.textContent = 'Mengirim...';
    submitBtn.disabled = true;

    try {
        const res = await fetch(`/api/tasks/preventive/${taskId}/report`, {
            method: 'POST',
            body: formData
        });
        
        if (res.ok) {
            closeModal();
            fetchTasks(); // Refresh
        } else {
            alert('Gagal mengirim laporan. Coba lagi.');
        }
    } catch (err) {
        console.error('Submit error:', err);
        alert('Terjadi kesalahan sistem.');
    } finally {
        submitBtn.textContent = 'Kirim Laporan';
        submitBtn.disabled = false;
    }
}

// Init
window.onload = fetchTasks;
