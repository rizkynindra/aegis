let userRole = 'normal';

function showWarning(condition) {
    if (userRole === 'disaster') {
        const modal = document.getElementById('disaster-modal');
        modal.querySelector('p').textContent = `Kondisi ${condition} diprediksi terjadi 3 hari ke depan. Harap isi form di bawah ini untuk konfirmasi kesiapan aksi bantuan karyawan.`;
        modal.classList.add('active');
    } else {
        const modal = document.getElementById('rain-modal');
        modal.querySelector('h2').textContent = `Waspada Cuaca!`;
        modal.querySelector('p').textContent = `Perhatian! Kondisi ${condition} diprediksi akan terjadi selama 3 hari berturut-turut. Tetap waspada dan persiapkan diri Anda sebelum beraktivitas.`;
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

function submitDisasterForm() {
    const actionPlan = document.getElementById('action-plan').value;
    const teamLead = document.getElementById('team-lead').value;

    if (!actionPlan || !teamLead) {
        alert('Harap isi semua field formulir!');
        return;
    }

    // Mock submission
    console.log('Disaster action confirmed:', { actionPlan, teamLead });
    alert('Laporan diterima. Terima kasih atas kesiagaan Anda!');
    closeModal('disaster-modal');
}

async function fetchWeather() {
    try {
        // Fetch user role first
        const userResp = await fetch('/api/user');
        const userData = await userResp.json();
        userRole = userData.role || 'normal';

        // Fetch active conditions from backend
        const condResp = await fetch('/api/active-conditions');
        const condData = await condResp.json();
        const activeConditions = condData.conditions || ['hujan ringan'];

        const response = await fetch('/api/weather');
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        renderWeather(data);
        checkRainConsecutive(data, activeConditions);

        document.getElementById('loader').style.opacity = '0';
        setTimeout(() => document.getElementById('loader').style.display = 'none', 500);
    } catch (err) {
        console.error(err);
        document.getElementById('dashboard').innerHTML = `<div class="error-msg">Gagal memuat data: ${err.message}</div>`;
        document.getElementById('loader').style.display = 'none';
    }
}

function checkRainConsecutive(data, activeConditions) {
    const days = data.data[0].cuaca;

    for (let condition of activeConditions) {
        let rainStreak = 0;
        let shouldWarn = false;

        for (let dayForecast of days) {
            const hasCondition = dayForecast.some(f =>
                f.weather_desc.toLowerCase().includes(condition.toLowerCase())
            );

            if (hasCondition) {
                rainStreak++;
                if (rainStreak >= 3) {
                    shouldWarn = true;
                    break;
                }
            } else {
                rainStreak = 0;
            }
        }

        if (shouldWarn) {
            showWarning(condition);
            return; // Exit early once a warning condition is met
        }
    }
}

function renderWeather(data) {
    const loc = data.lokasi;
    document.getElementById('loc-text').textContent = `${loc.desa}, ${loc.kecamatan}, ${loc.kotkab}`;

    const dashboard = document.getElementById('dashboard');
    dashboard.innerHTML = '';

    const days = data.data[0].cuaca;
    days.forEach((dayForecast, dayIdx) => {
        const dayHeader = document.createElement('div');
        dayHeader.className = 'day-label';
        dayHeader.textContent = `Prakiraan Hari ke-${dayIdx + 1}`;
        dashboard.appendChild(dayHeader);

        const grid = document.createElement('div');
        grid.className = 'weather-grid';

        dayForecast.forEach(f => {
            const card = document.createElement('div');
            card.className = 'weather-card';
            card.innerHTML = `
                <div class="wc-header">
                    <span class="wc-time">${f.local_datetime.split(' ')[1].substring(0, 5)}</span>
                    <span class="wc-desc">${f.weather_desc}</span>
                </div>
                <div class="wc-main">
                    <img src="${f.image.replace(' ', '%20')}" class="wc-icon" alt="icon">
                    <span class="wc-temp">${f.t}°C</span>
                </div>
                <div class="wc-details">
                    <div>
                        <div class="wc-detail-label">Kelembapan</div>
                        <div class="wc-detail-value">${f.hu}%</div>
                    </div>
                    <div>
                        <div class="wc-detail-label">Angin</div>
                        <div class="wc-detail-value">${f.ws} km/h ${f.wd}</div>
                    </div>
                    <div>
                        <div class="wc-detail-label">Jarak Pandang</div>
                        <div class="wc-detail-value">${f.vs_text}</div>
                    </div>
                    <div>
                        <div class="wc-detail-label">Update</div>
                        <div class="wc-detail-value">${f.analysis_date.substring(11, 16)}</div>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
        dashboard.appendChild(grid);
    });
}

// Push Notification Logic
async function setupPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

    try {
        const registration = await navigator.serviceWorker.ready;

        // Check current subscription
        let subscription = await registration.pushManager.getSubscription();

        if (!subscription) {
            // Get public key from server
            const response = await fetch('/api/vapid-public-key');
            const { publicKey } = await response.json();

            // Subscribe
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey)
            });

            // Send to backend
            await fetch('/api/subscribe', {
                method: 'POST',
                body: JSON.stringify(subscription),
                headers: { 'Content-Type': 'application/json' }
            });
            console.log('Push subscription successful');
        }
    } catch (err) {
        console.warn('Push registration failed:', err);
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// Start fetching on load
document.addEventListener('DOMContentLoaded', () => {
    fetchWeather();
    setupPushNotifications();
});
