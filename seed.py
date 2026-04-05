import os
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base, SessionLocal
from database import User, TeamCategory, NotificationSetting, ActivityLog, TaskTemplate, EmergencyTask, AdHocReport, PreventiveTask, PreventiveReport

def seed_database():
    print("🚀 Memulai proses reset dan seeding database...")
    
    # 1. Drop all tables to fix schema mismatch
    print("🗑 Menghapus tabel lama...")
    try:
        if "postgresql" in str(engine.url):
            from sqlalchemy import text
            with engine.connect() as conn:
                # Terminate other connections to prevent Deadlock/In-use errors
                print("🔌 Memutus koneksi aktif lainnya...")
                conn.execute(text("""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = current_database()
                      AND pid <> pg_backend_pid();
                """))
                conn.commit()
                
                print("♻️ Dropping and recreating schema...")
                conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
                conn.commit()
                print("✅ Schema public berhasil direset.")
        else:
            Base.metadata.drop_all(bind=engine)
    except Exception as e:
        print(f"⚠️ Warning during drop: {e}")
    
    # 2. Create all tables with updated schema
    print("🏗 Membuat tabel baru...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 3. Seed Team Categories
        print("🏷 Menambah kategori tim KTD...")
        team_names = [
            "Tim Fire & Floods", "Tim Pengamanan", 
            "Tim Evakuasi", "Tim P3K", 
            "Tim Logistik", "Tim Rehabilitasi", "Tim Security"
        ]
        teams = []
        for name in team_names:
            team = TeamCategory(name=name)
            db.add(team)
            teams.append(team)
        db.flush() 
        
        # 4. Seed Admin User
        print("👤 Menambah akun Admin...")
        admin = User(
            employee_id="admin",
            username="admin",
            password="123",
            role="admin",
            name="Administrator Utama"
        )
        db.add(admin)
        db.flush()
        
        # 5. Seed Team Leaders and Members
        print("👥 Menambah anggota tim dan leader...")
        team_map = {t.name: t for t in teams}
        
        for team_name in team_names:
            team = team_map[team_name]
            # Leader for this team
            leader_username = team_name.lower().replace(" ", "_").replace("&", "and") + "_leader"
            leader = User(
                employee_id=leader_username.replace("_", ""),
                username=leader_username,
                password="123",
                role="disaster",
                name=f"Leader {team_name}",
                team_category_id=team.id
            )
            db.add(leader)
            db.flush()
            
            # Assign as leader in TeamCategory
            team.leader_id = leader.id
            
            # One extra member for each team (to show swapping options)
            member_username = team_name.lower().replace(" ", "_").replace("&", "and") + "_member"
            member = User(
                employee_id=member_username.replace("_", ""),
                username=member_username,
                password="123",
                role="disaster",
                name=f"Anggota {team_name}",
                team_category_id=team.id
            )
            db.add(member)
            
        # 6. Seed Normal Users
        print("👨‍💼 Menambah user normal...")
        for i in range(1, 4):
            normal_user = User(
                employee_id=f"user{i}",
                username=f"user{i}",
                password="123",
                role="normal",
                name=f"User Lapangan {i}"
            )
            db.add(normal_user)
        db.flush()
            
        # 7. Seed Preventive Tasks (Based on PREVENTIVE_CHECKLIST.md)
        print("📋 Menambah checklist tugas preventif (mockup/PREVENTIVE_CHECKLIST.md)...")
        checklist_data = {
            "Tim Fire & Floods": [
                "Pemeriksaan APAR (tekanan & kondisi)", 
                "Cek hydrant & pompa air berfungsi normal", 
                "Pastikan jalur drainase tidak tersumbat", 
                "Identifikasi area rawan genangan", 
                "Inspeksi instalasi listrik berisiko"
            ],
            "Tim Pengamanan": [
                "Cek akses jalur evakuasi tidak terhalang", 
                "Pastikan signage evakuasi terlihat jelas", 
                "Kontrol area rawan (gudang, genset, dll)", 
                "Briefing kesiapsiagaan kepada karyawan", 
                "Simulasi pengamanan area darurat"
            ],
            "Tim Evakuasi": [
                "Verifikasi titik kumpul aman & jelas", 
                "Uji jalur evakuasi secara berkala", 
                "Sosialisasi jalur evakuasi ke karyawan", 
                "Pendataan jumlah karyawan aktif", 
                "Simulasi evakuasi minimal berkala"
            ],
            "Tim P3K": [
                "Cek kelengkapan & masa berlaku alat P3K", 
                "Menyediakan obat dasar & alat medis", 
                "Update daftar petugas P3K", 
                "Simulasi penanganan korban", 
                "Koordinasi dengan klinik/RS terdekat"
            ],
            "Tim Logistik": [
                "Cek ketersediaan alat darurat (pompa, APAR, dll)",
                "Stok air minum & konsumsi darurat",
                "Kesiapan alat komunikasi (HT, dll)",
                "Penempatan alat mudah dijangkau",
                "Update inventaris logistic"
            ],
            "Tim Rehabilitasi": [
                "Identifikasi area prioritas pemulihan",
                "Kesiapan alat perbaikan",
                "Backup fasilitas penting (genset, dll)",
                "Rencana pemulihan operasional",
                "Dokumentasi kondisi awal area"
            ],
            "Tim Security": [
                "Identifikasi area prioritas pemulihan",
                "Kesiapan alat perbaikan",
                "Backup fasilitas penting (genset, dll)",
                "Rencana pemulihan operasional",
                "Dokumentasi kondisi awal area"
            ]
        }
        
        for team_name, tasks in checklist_data.items():
            team = team_map[team_name]
            for t_title in tasks:
                db.add(PreventiveTask(team_category_id=team.id, title=t_title))
        
        # 8. Seed Emergency Task Templates (Unique per Team)
        print("🚨 Menambah template tugas darurat (Emergency Task Templates)...")
        emergency_task_data = {
            "Tim Fire & Floods": ["Cek Pasokan Air & Pompa", "Siapkan Karung Pasir", "Matikan Panel Listrik Berisiko"],
            "Tim Pengamanan": ["Kunci Akses Non-Evakuasi", "Amankan Aset Berharga", "Pos Jaga Pintu Utama"],
            "Tim Evakuasi": ["Siapkan Megaphone/Siren", "Buka Jalur Evakuasi Total", "Penyisiran Ruangan"],
            "Tim P3K": ["Siapkan Tandu/Obat di Titik Kumpul", "Buka Posko Medis", "Siagakan Ambulans"],
            "Tim Logistik": ["Distribusikan Senter/HT", "Siapkan Air Minum Darurat", "Cek Stok Jas Hujan/Selimut"],
            "Tim Rehabilitasi": ["Identifikasi Kerusakan Infrastruktur", "Amankan Sisa Barang", "Koordinasi Pembersihan"],
            "Tim Security": ["Pantau CCTV & Alarm", "Pastikan Area Steril", "Siapkan Laporan Kejadian"]
        }
        
        for team_name, tasks in emergency_task_data.items():
            team = team_map[team_name]
            print(f" - {team_name} ({len(tasks)} tasks)...")
            for t_title in tasks:
                db.add(TaskTemplate(
                    status_level="Waspada", 
                    team_category_id=team.id, 
                    title=t_title,
                    requires_photo=True
                ))
        db.flush()
        print(f"✅ Created {db.query(TaskTemplate).count()} task templates in session.")
        
        # 9. Seed Notification Trigger Settings
        print("⚙️ Menambah kondisi pemicu notifikasi...")
        conditions = ["hujan petir", "hujan lebat", "angin kencang", "hujan sedang"]
        for cond in conditions:
            db.add(NotificationSetting(condition=cond, is_active=True))
            
        # 10. Seed Activity logs
        print("🕒 Menambah riwayat aktivitas dummy...")
        messages = [
            "Peringatan: Hujan petir terdeteksi. Tim Fire & Floods harap siaga.",
            "Normal: Kondisi cuaca cerah di area AEGIS.",
            "Laporan: Unit security melakukan patroli area rawan genangan.",
            "System: Notifikasi push terkirim ke 14 perangkat tim KTD."
        ]
        for i in range(15):
            log = ActivityLog(
                timestamp=datetime.utcnow() - timedelta(minutes=i*20),
                message=random.choice(messages),
                condition_matched=random.choice(conditions) if i % 2 == 0 else "manual"
            )
            db.add(log)
            
        # 11. Seed AdHoc Reports (Dummy Reports from Users)
        print("📝 Menambah laporan lapangan...")
        normal_users = db.query(User).filter(User.role == "normal").all()
        for i in range(5):
            report = AdHocReport(
                user_id=random.choice(normal_users).id,
                category="Cuaca Ekstrim",
                content=f"Ditemukan genangan air di area {random.choice(['Gudang A', 'Parkir Selatan', 'Area Produksi'])}. Mohon bantuan tim terkait.",
                timestamp=datetime.utcnow() - timedelta(hours=i),
                photo_path="https://images.unsplash.com/photo-1541919329513-35f7af297129?q=80&w=1000&auto=format&fit=crop"
            )
            db.add(report)
            
        db.commit()
        print("✅ Database SEEDED successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
