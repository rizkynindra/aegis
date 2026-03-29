import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load env vars from .env file
load_dotenv()

from database import Base, engine, TeamCategory, User, TaskTemplate, NotificationSetting

def migrate():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment.")
        return

    print(f"Starting migration on: {DATABASE_URL.split('@')[-1]}") # Print host only for security

    # 1. Ensure all tables are created (idempotent)
    Base.metadata.create_all(bind=engine)
    print("Core tables ensured.")

    # 2. Add missing columns to existing tables (Direct SQL for PostgreSQL/SQLite)
    with engine.connect() as conn:
        # Add employee_id to users
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN employee_id VARCHAR(100)"))
            conn.commit()
            print("Added employee_id to users.")
        except Exception:
            print("employee_id already exists or skipped.")

        # Add team_category_id to users
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN team_category_id INTEGER"))
            conn.commit()
            print("Added team_category_id to users.")
        except Exception:
            print("team_category_id already exists or skipped.")

        # Add condition_matched to activity_logs
        try:
            conn.execute(text("ALTER TABLE activity_logs ADD COLUMN condition_matched VARCHAR(200)"))
            conn.commit()
            print("Added condition_matched to activity_logs.")
        except Exception:
            print("condition_matched already exists or skipped.")

    # 3. Seed Data & Migrate Legacy Users
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Migrate legacy users: Set employee_id = username if null
        legacy_users = db.query(User).filter(User.employee_id == None).all()
        if legacy_users:
            for u in legacy_users:
                u.employee_id = u.username
            db.commit()
            print(f"👤 Migrated {len(legacy_users)} legacy users (employee_id set to username).")

        # Seed categories if empty
        if not db.query(TeamCategory).first():
            categories = [
                "Pimpinan Pengendali (Kacab)",
                "Koordinator Penanggulangan & Pengamanan (Kabeng)",
                "Koordinator Evakuasi & Penyelamatan",
                "Tim Komunikasi",
                "Tim Pelaksana / Fire & Floods",
                "Tim Keamanan (Security)",
                "Tim Listrik & Sarana",
                "Tim P3K & P3GD",
                "Tim Karyawan & Logistik",
                "Tim Barang Inventaris & Dokumen",
                "Tim Kendaraan"
            ]
            db.add_all([TeamCategory(name=cat) for cat in categories])
            db.commit()
            print(f"📂 Seeded {len(categories)} team categories.")

        # Seed specialized tasks
        all_cats = db.query(TeamCategory).all()
        cat_map = {c.name: c.id for c in all_cats}
        
        category_tasks = {
            "Pimpinan Pengendali (Kacab)": "Monitoring Situasi & Pengambilan Keputusan",
            "Koordinator Penanggulangan & Pengamanan (Kabeng)": "Koordinasi dan Pengerahan Tim",
            "Koordinator Evakuasi & Penyelamatan": "Pengawasan Jalur Evakuasi dan Titik Kumpul",
            "Tim Komunikasi": "Menghubungi Instansi Terkait (Damkar, Polisi, PLN, RS)",
            "Tim Pelaksana / Fire & Floods": "Pengecekan Kesiapan APAR/Hydrant & Tanggul",
            "Tim Keamanan (Security)": "Pengamanan Area dan Aset Kantor",
            "Tim Listrik & Sarana": "Pemutusan Arus Listrik Utama (Panel)",
            "Tim P3K & P3GD": "Penyiapan Posko Medis dan Alat P3K",
            "Tim Karyawan & Logistik": "Penyiapan Bahan Makanan dan Konsumsi Darurat",
            "Tim Barang Inventaris & Dokumen": "Penyelamatan Dokumen Penting dan Backup Data",
            "Tim Kendaraan": "Pemindahan Kendaraan ke Area Aman"
        }

        created_count = 0
        for cat_name, task_title in category_tasks.items():
            cat_id = cat_map.get(cat_name)
            if not cat_id: continue
            
            for level in ["Waspada", "Siaga", "Darurat"]:
                full_title = f"SIAGA: {task_title}" if level == "Siaga" else (f"DARURAT: {task_title}" if level == "Darurat" else task_title)
                
                exists = db.query(TaskTemplate).filter(
                    TaskTemplate.status_level == level,
                    TaskTemplate.team_category_id == cat_id,
                    TaskTemplate.title == full_title
                ).first()
                
                if not exists:
                    db.add(TaskTemplate(
                        status_level=level,
                        team_category_id=cat_id,
                        title=full_title,
                        description=f"Instruksi khusus for {cat_name}.",
                        requires_photo=True
                    ))
                    created_count += 1
        
        db.commit()
        if created_count > 0:
            print(f"📋 Seeded {created_count} missing task templates.")
        else:
            print("📋 All task templates already up to date.")

        # Seed default settings
        if not db.query(NotificationSetting).first():
            db.add(NotificationSetting(condition="hujan ringan", is_active=True))
            db.commit()
            print("🔔 Seeded notification settings.")

        print("🏁 Migration completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error during data seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
