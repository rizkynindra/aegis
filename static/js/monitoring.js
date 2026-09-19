const WATER_LEVEL_POLL_MS = 20000;
const HISTORY_HOURS = 6;

let waterLevelChart = null;

function formatClockLabel(ts) {
    return new Date(ts).toLocaleTimeString("id-ID", {
        hour: "2-digit",
        minute: "2-digit",
    });
}

function formatUpdatedAt(ts) {
    if (!ts) return "Belum ada data";
    return new Date(ts).toLocaleString("id-ID", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function mapSensorStatus(status, tinggi) {
    if (status === "SENSOR_ERROR") {
        return {
            label: "Sensor Error",
            className: "status-bahaya",
            summary: "Sensor melaporkan error. Periksa koneksi ESP32_Sungai.",
        };
    }

    if (tinggi == null) {
        return {
            label: "Menunggu Data",
            className: "status-waspada",
            summary: "Belum ada pembacaan ketinggian air dari ThingsBoard.",
        };
    }

    if (tinggi >= 100) {
        return {
            label: "Siaga",
            className: "status-bahaya",
            summary: `Ketinggian air ${tinggi.toFixed(1)} cm. Status SIAGA — pantau terus.`,
        };
    }

    if (tinggi >= 60) {
        return {
            label: "Waspada",
            className: "status-waspada",
            summary: `Ketinggian air ${tinggi.toFixed(1)} cm. Status WASPADA.`,
        };
    }

    return {
        label: "Aman (Normal)",
        className: "status-aman",
        summary: `Ketinggian air ${tinggi.toFixed(1)} cm. Tren saat ini relatif stabil.`,
    };
}

function initChart() {
    const canvas = document.getElementById("waterLevelChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    waterLevelChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "Ketinggian Air (cm)",
                    data: [],
                    borderColor: "#ff4d4d",
                    backgroundColor: "rgba(255, 77, 77, 0.1)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            plugins: {
                legend: { display: false },
                tooltip: {
                    mode: "index",
                    intersect: false,
                    callbacks: {
                        label: (context) => `${context.parsed.y} cm`,
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: "#94a3b8",
                        font: { size: 10 },
                        maxTicksLimit: 8,
                    },
                },
                y: {
                    beginAtZero: true,
                    grid: { color: "rgba(255,255,255,0.05)" },
                    ticks: {
                        color: "#94a3b8",
                        font: { size: 10 },
                        callback: (value) => `${value} cm`,
                    },
                },
            },
        },
    });
}

function updateLatestUi(latest) {
    const valueEl = document.getElementById("water-level-value");
    const updatedEl = document.getElementById("water-level-updated");
    const pillEl = document.getElementById("water-level-status");
    const summaryEl = document.getElementById("water-level-summary");

    if (!latest || latest.error) {
        if (valueEl) valueEl.textContent = "--";
        if (updatedEl) updatedEl.textContent = latest?.error || "Gagal memuat data";
        if (pillEl) {
            pillEl.textContent = "Offline";
            pillEl.className = "status-pill status-bahaya";
        }
        if (summaryEl) {
            summaryEl.innerHTML =
                "Tidak dapat mengambil data ThingsBoard. Periksa konfigurasi API key / koneksi.";
        }
        return;
    }

    const tinggi = latest.tinggi;
    const mapped = mapSensorStatus(latest.status, tinggi);

    if (valueEl) {
        valueEl.textContent = tinggi == null ? "--" : tinggi.toFixed(1);
    }
    if (updatedEl) {
        updatedEl.textContent = `Update: ${formatUpdatedAt(latest.ts)}`;
    }
    if (pillEl) {
        pillEl.textContent = mapped.label;
        pillEl.className = `status-pill ${mapped.className}`;
    }
    if (summaryEl) {
        summaryEl.innerHTML = mapped.summary;
    }
}

function updateChart(history) {
    if (!waterLevelChart) return;

    if (!history || history.error || !history.series) {
        waterLevelChart.data.labels = [];
        waterLevelChart.data.datasets[0].data = [];
        waterLevelChart.update();
        return;
    }

    const labels = history.series.map((point) => formatClockLabel(point.ts));
    const values = history.series.map((point) => point.value);

    waterLevelChart.data.labels = labels;
    waterLevelChart.data.datasets[0].data = values;
    waterLevelChart.update();
}

async function fetchWaterLevel() {
    try {
        const [latestRes, historyRes] = await Promise.all([
            fetch("/api/water-level/latest"),
            fetch(`/api/water-level/history?hours=${HISTORY_HOURS}&limit=500`),
        ]);

        const latest = await latestRes.json();
        const history = await historyRes.json();

        updateLatestUi(latest);
        updateChart(history);
    } catch (err) {
        console.error("Water level fetch failed:", err);
        updateLatestUi({ error: "Gagal memuat data sensor" });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    fetchWaterLevel();
    setInterval(fetchWaterLevel, WATER_LEVEL_POLL_MS);
});
