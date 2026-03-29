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
        const res = await fetch('/api/incidents/recent');
        const data = await res.json();
        const container = document.getElementById('activity-feed');
        
        if (data.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Belum ada aktivitas tim yang dilaporkan bulan ini.</div>';
            return;
        }

        container.innerHTML = data.map(item => `
            <div class="feed-item">
                <div class="feed-meta">
                    <span>🕒 ${item.timestamp}</span>
                    <span>👤 ${item.author}</span>
                </div>
                <div class="feed-title">${item.title}</div>
                <div class="feed-body">${item.content}</div>
            </div>
        `).join('');
    } catch (err) { console.error(err); }
}

async function checkStatus() {
    try {
        const res = await fetch('/api/events/active/tasks');
        const data = await res.json();
        const badge = document.getElementById('status-badge');
        if (data.event_id) {
            badge.innerText = 'WASPADAI ' + data.status_level.toUpperCase();
            badge.className = 'status-badge status-waspada';
        } else {
            badge.innerText = 'AMAN';
            badge.className = 'status-badge status-normal';
        }
    } catch (err) {}
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
    setInterval(checkStatus, 30000);
    setInterval(fetchActivityFeed, 60000);
});
