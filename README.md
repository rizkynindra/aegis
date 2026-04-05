# AEGIS (Advanced Emergency & Guardian Intelligence System) 🛡️

AEGIS is a professional-grade, mobile-first Disaster Management System (DMS) designed for corporate and organizational safety. Built with a focus on real-time responsiveness and intuitive user experience, AEGIS connects employees, disaster response teams, and administrators into a unified safety network.

![AEGIS Dashboard](https://github.com/rizkynindra/aegis/raw/main/static/images/logo.jpeg)

## 🌟 Key Features

### 📱 Mobile-First PWA
AEGIS is designed as a **Progressive Web App**, providing a native-like experience on mobile devices.
- **Offline Readiness**: Basic functionality remains available even with intermittent connectivity.
- **App-like Navigation**: Thumb-friendly bottom navigation and fixed headers for rapid access.
- **Installable**: Can be added directly to the home screen of Android and iOS devices.

### 🛰️ Real-Time Hazard Monitoring
Full integration with **BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)** Open Data API.
- **Weather Forecasts**: Hourly localized weather data for proactive planning.
- **Dynamic Status**: Automated system status switching (Normal, Waspada, Siaga) based on environmental conditions.

### 👥 Role-Based Ecosystem
- **Employee Portal**: Personalized dashboards, weather awareness, and rapid incident reporting (Ad-Hoc).
- **Disaster Team (Tim KTD)**: Managed emergency event logs, task checklists, and team-specific actions.
- **Admin Command Center**: Complete oversight of system configuration, user management, and emergency orchestration.

### 🚨 Rapid Incident Reporting
Employees can report emergencies in seconds:
- **Category Selection**: Pre-defined disaster categories (Fire, Flood, Earthquake, etc.).
- **Photo Integration**: Upload photographic evidence directly from the field.
- **Real-Time Feed**: A synchronized activity feed visible to relevant responders.

### 🔔 Smart Notifications
Utilizes **Web Push Notifications** to ensure that critical alerts are seen immediately, even if the application is not actively open in the browser.

---

## 🛠️ Technology Stack

### Backend
- **FastAPI**: High-performance Python framework for building modern APIs.
- **SQLAlchemy**: Robust ORM for database abstraction and security.
- **Jinja2**: Server-side templating for dynamic SEO-friendly content.

### Frontend
- **Vanilla JavaScript**: Pure, high-performance logic with no heavy framework overhead.
- **Custom CSS3**: A premium, "Mobile-First" design system featuring glassmorphism and deep-maroon aesthetics.
- **Workbox/Service Workers**: Handling PWA caching and background sync.

### Infrastructure
- **Vercel**: Optimized deployment for serverless architecture.
- **Neon/PostgreSQL**: Scalable database layer for production environments.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- SQLite (Development) or PostgreSQL (Production)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/rizkynindra/aegis.git
   cd aegis
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables (.env):
   ```env
   DATABASE_URL=your_postgresql_url
   SESSION_SECRET=your_secret_key
   VAPID_PUBLIC_KEY=your_key
   VAPID_PRIVATE_KEY=your_key
   ```
4. Run the development server:
   ```bash
   python app.py
   ```

---

## 📖 Attribution
AEGIS proudly uses open data provided by **BMKG (Badan Meteorologi, Klimatologi, dan Geofisika)**. All weather information is processed in accordance with open data terms.

---
*Created with ❤️ by the AEGIS Development Team.*
