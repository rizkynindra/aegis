import os
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from database import engine, TaskTemplate, TeamCategory, User, NotificationSetting

load_dotenv()

def sync_templates():
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print("🛠️ Cleaning and Syncing Task Templates...")
        
        # 1. Fetch categories
        categories = db.query(TeamCategory).all()
        cat_map = {c.name: c.id for c in categories}
        
        if not categories:
            print("❌ No categories found. Please run migrate_db.py first or seed categories.")
            return

        # 2. Define the exact desired templates
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

        # 3. Synchronize: Check each task before adding
        created_count = 0
        for cat_name, task_title in category_tasks.items():
            cat_id = cat_map.get(cat_name)
            if not cat_id: continue
            
            # Check all levels
            for level in ["Waspada", "Siaga", "Darurat"]:
                full_title = f"SIAGA: {task_title}" if level == "Siaga" else (f"DARURAT: {task_title}" if level == "Darurat" else task_title)
                
                # Check for existing
                exists = db.query(TaskTemplate).filter(
                    TaskTemplate.status_level == level,
                    TaskTemplate.team_category_id == cat_id,
                    TaskTemplate.title == full_title
                ).first()
                
                if not exists:
                    new_t = TaskTemplate(
                        status_level=level,
                        team_category_id=cat_id,
                        title=full_title,
                        description=f"Instruksi khusus untuk {cat_name} berdasarkan SOP Job Desk.",
                        requires_photo=True
                    )
                    db.add(new_t)
                    created_count += 1
        
        db.commit()
        print(f"✅ Deduplication complete! Created {created_count} missing templates.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error during sync: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    sync_templates()
