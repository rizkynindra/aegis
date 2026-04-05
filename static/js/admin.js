function openPhoto(src) {
    const modal = document.getElementById('photoModal');
    const modalImg = document.getElementById('modalImg');
    if (modal && modalImg) {
        modalImg.src = src;
        modal.classList.add('active');
        modal.style.display = 'flex';
    }
}

function toggleCategorySelect(role) {
    const catSelect = document.getElementById('category-select');
    if (catSelect) {
        if (role === 'disaster') {
            catSelect.style.display = 'block';
            catSelect.required = true;
        } else {
            catSelect.style.display = 'none';
            catSelect.required = false;
        }
    }
}

async function loadLeaders() {
    const listBody = document.getElementById('leaders-list');
    if (!listBody) return;

    try {
        const res = await fetch('/api/admin/teams');
        const teams = await res.json();

        if (teams.length === 0) {
            listBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 2rem; color: var(--text-muted);">Belum ada kategori tim.</td></tr>';
            return;
        }

        listBody.innerHTML = teams.map(team => `
            <tr>
                <td style="font-weight: 500; color: var(--text-primary); font-size: 0.95rem;">${team.name}</td>
                <td style="color: var(--text-secondary); font-size: 0.9rem;">
                    ${team.leader_name === "Belum Ditentukan" 
                        ? '<span style="color: var(--text-muted); font-style: italic;">Belum Ditentukan</span>' 
                        : `👑 <strong>${team.leader_name}</strong>`}
                </td>
                <td style="text-align: right;">
                    <button class="btn btn-ghost" onclick="openLeaderModal(${team.id}, '${team.name}')" style="padding: 0.4rem 0.8rem; font-size: 0.8rem;">
                        Ganti Leader
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error loading leaders:', err);
        listBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 2rem; color: #ff6b6b;">Gagal memuat data leader.</td></tr>';
    }
}

async function openLeaderModal(teamId, teamName) {
    const modal = document.getElementById('assignLeaderModal');
    const title = document.getElementById('assign-modal-team-name');
    const teamInput = document.getElementById('assign-modal-team-id');
    const select = document.getElementById('eligible-leader-select');

    if (!modal || !title || !teamInput || !select) return;

    title.innerText = `Menugaskan leader untuk ${teamName}`;
    teamInput.value = teamId;
    modal.style.display = 'flex';
    modal.classList.add('active');

    // Fetch eligible users
    try {
        select.innerHTML = '<option value="">Memuat user...</option>';
        const res = await fetch('/api/admin/eligible-leaders');
        const users = await res.json();

        let html = '<option value="">-- Tanpa Leader / Kosongkan --</option>';
        users.forEach(u => {
            html += `<option value="${u.id}">${u.name} (${u.emp_id})</option>`;
        });
        select.innerHTML = html;
    } catch (err) {
        select.innerHTML = '<option value="">Gagal memuat user</option>';
    }
}

function closeLeaderModal() {
    const modal = document.getElementById('assignLeaderModal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
    }
}

async function submitLeaderAssignment() {
    const teamId = document.getElementById('assign-modal-team-id').value;
    const userId = document.getElementById('eligible-leader-select').value;
    const btn = event.target;

    if (!teamId) return;

    btn.disabled = true;
    const originalText = btn.innerText;
    btn.innerText = 'Menyimpan...';

    try {
        const res = await fetch(`/api/admin/teams/${teamId}/assign-leader`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId ? parseInt(userId) : null })
        });
        const data = await res.json();
        if (data.status === 'success') {
            closeLeaderModal();
            loadLeaders();
        } else {
            alert('Gagal: ' + (data.detail || 'Terjadi kesalahan'));
        }
    } catch (err) {
        alert('Gagal: Terjadi kesalahan sistem');
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// Global modal close logic
document.addEventListener('DOMContentLoaded', () => {
    const photoModal = document.getElementById('photoModal');
    if (photoModal) {
        photoModal.addEventListener('click', (e) => {
            if (e.target === photoModal) {
                photoModal.classList.remove('active');
                photoModal.style.display = 'none';
            }
        });
    }

    const leaderModal = document.getElementById('assignLeaderModal');
    if (leaderModal) {
        leaderModal.addEventListener('click', (e) => {
            if (e.target === leaderModal) closeLeaderModal();
        });
    }

    // Initial load
    loadLeaders();
});
