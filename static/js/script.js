let userRole = 'normal';

function showWarning() {
    if (userRole === 'disaster') {
        document.getElementById('disaster-modal').classList.add('active');
    } else {
        document.getElementById('rain-modal').classList.add('active');
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

        const response = await fetch('/api/weather');
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        renderWeather(data);
        checkRainConsecutive(data);

        document.getElementById('loader').style.opacity = '0';
        setTimeout(() => document.getElementById('loader').style.display = 'none', 500);
    } catch (err) {
        console.error(err);
        document.getElementById('dashboard').innerHTML = `<div class="error-msg">Gagal memuat data: ${err.message}</div>`;
        document.getElementById('loader').style.display = 'none';
    }
}

function checkRainConsecutive(data) {
    const days = data.data[0].cuaca;
    let rainStreak = 0;

    for (let dayForecast of days) {
        const hasLightRain = dayForecast.some(f =>
            f.weather_desc.toLowerCase().includes('berawan')
        );

        if (hasLightRain) {
            rainStreak++;
            if (rainStreak >= 3) {
                showWarning();
                break;
            }
        } else {
            rainStreak = 0;
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
        dayHeader.className = 'day-separator';
        dayHeader.textContent = `Prakiraan Hari ke-${dayIdx + 1}`;
        dashboard.appendChild(dayHeader);

        dayForecast.forEach(f => {
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <div class="card-header">
                    <span class="time">${f.local_datetime.split(' ')[1].substring(0, 5)}</span>
                    <span class="condition">${f.weather_desc}</span>
                </div>
                <div class="main-stat">
                    <img src="${f.image.replace(' ', '%20')}" class="weather-icon" alt="icon">
                    <span class="temp">${f.t}°C</span>
                </div>
                <div class="details">
                    <div class="detail-item">
                        <span class="detail-label">Kelembapan</span>
                        <span class="detail-value">${f.hu}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Angin</span>
                        <span class="detail-value">${f.ws} km/h ${f.wd}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Visibility</span>
                        <span class="detail-value">${f.vs_text}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Terakhir Update</span>
                        <span class="detail-value">${f.analysis_date.substring(11, 16)}</span>
                    </div>
                </div>
            `;
            dashboard.appendChild(card);
        });
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
