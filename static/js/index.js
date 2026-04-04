async function fetchWeather() {
    try {
        const res = await fetch('/api/weather');
        const data = await res.json();
        if (data.error) throw new Error(data.error);

        const container = document.getElementById('weather-forecast');
        const days = data.data[0].cuaca;
        let html = '';

        days.forEach((dayForecast, dayIdx) => {
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

async function fetchActivityFeed() {
    try {
        // Fetch both team incidents and ad-hoc reports
        const [teamRes, adhocRes] = await Promise.all([
            fetch('/api/incidents/recent'),
            fetch('/api/reports/adhoc/recent')
        ]);

        const teamData = await teamRes.json();
        const adhocData = await adhocRes.json();

        // Merge and tag them
        const allItems = [
            ...teamData.map(i => ({ ...i, type: 'team' })),
            ...adhocData.map(i => ({ ...i, type: 'adhoc' }))
        ];

        // Sort by timestamp descending
        allItems.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        const container = document.getElementById('activity-feed');
        if (allItems.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Belum ada aktivitas yang dilaporkan bulan ini.</div>';
            return;
        }

        container.innerHTML = allItems.map(item => `
            <div class="feed-item">
                <div class="feed-badge ${item.type === 'team' ? 'badge-team' : 'badge-adhoc'}">
                    ${item.type === 'team' ? '🛡️ Tim KTD' : '👤 Laporan Karyawan'}
                </div>
                <div class="feed-meta">
                    <span>🕒 ${item.timestamp}</span>
                    <span>👤 ${item.author}</span>
                </div>
                <div class="feed-title">${item.type === 'adhoc' ? item.category : item.title}</div>
                <div class="feed-body">${item.content}</div>
                ${item.photo_path ? `<img src="${item.photo_path}" style="width:100%; border-radius:8px; margin-top:10px; border:1px solid var(--border);">` : ''}
            </div>
        `).join('');
    } catch (err) { console.error(err); }
}

let lastStatus = 'normal';

function showStatusNotification(level) {
    // Remove if exists
    const existing = document.getElementById('status-notif-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.id = 'status-notif-toast';
    toast.className = 'status-notification';
    toast.innerHTML = `
        <div class="notif-icon">⚠️</div>
        <div class="notif-content">
            <div class="notif-title">PERINGATAN STATUS: ${level.toUpperCase()}</div>
            <div class="notif-text">Kondisi cuaca terpantau ekstrem. Mohon tetap waspada dan ikuti panduan kesiapsiagaan di bawah.</div>
        </div>
        <div class="notif-close" onclick="this.parentElement.classList.remove('active')">✕</div>
    `;
    document.body.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('active'), 100);

    // Auto hide after 10s
    setTimeout(() => {
        if (toast) toast.classList.remove('active');
    }, 10000);
}

async function checkStatus() {
    try {

        const res = await fetch('/api/events/active/tasks');
        const data = await res.json();
        const badge = document.getElementById('status-badge');
        if (data.event_id) {
            // badge.innerText = 'WASPADA ' + data.status_level.toUpperCase();
            badge.innerText = 'WASPADA';
            badge.className = 'status-badge status-waspada';

            if (lastStatus === 'normal') {
                showStatusNotification(data.status_level || 'waspada');
            }
            lastStatus = 'waspada';
        } else {
            badge.innerText = 'AMAN';
            badge.className = 'status-badge status-normal';
            lastStatus = 'normal';
        }
    } catch (err) { }
}


// Modal Logic
function initModal() {
    const modal = document.getElementById('reportModal');
    const openBtn = document.getElementById('openReportModal');
    const closeBtn = document.getElementById('closeReportModal');
    const form = document.getElementById('reportForm');

    openBtn.onclick = () => modal.classList.add('active');
    closeBtn.onclick = () => modal.classList.remove('active');
    window.onclick = (e) => { if (e.target == modal) modal.classList.remove('active'); };

    form.onsubmit = async (e) => {
        e.preventDefault();
        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        submitBtn.innerText = 'Mengirim...';

        try {
            const formData = new FormData(form);
            const res = await fetch('/api/reports/adhoc', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (data.status === 'success') {
                showStatusNotification('Sukses: Laporan Terkirim');
                form.reset();
                modal.classList.remove('active');
                fetchActivityFeed();
            } else {
                showStatusNotification('Gagal: ' + data.message);
            }
        } catch (err) {
            showStatusNotification('Gagal: Terjadi kesalahan sistem');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerText = 'Kirim Laporan';
        }
    };
}

// PWA update logic
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').then(reg => { reg.update(); });
    });
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    fetchWeather();
    fetchActivityFeed();
    checkStatus();
    initModal();
    setInterval(checkStatus, 30000);
    setInterval(fetchActivityFeed, 60000);
});
