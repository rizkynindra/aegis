import os
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal, TaskTemplate, TeamCategory, EmergencyTask, EmergencyEvent

db = SessionLocal()
try:
    # 1. Clean up old TaskTemplates for the new 7 teams (IDs 12-18)
    # Actually, the user might want a fresh start for ALL templates since they've renamed teams.
    # I will delete all existing TaskTemplates to prevent ID/Category mismatches.
    print("Cleaning up old Emergency Tasks and Events...")
    db.query(EmergencyTask).delete()
    db.query(EmergencyEvent).delete()
    print("Cleaning up old Task Templates...")
    db.query(TaskTemplate).delete()
    
    # 2. Define the new 28 Emergency Task Templates (4 per team: 2 Waspada, 2 Siaga)
    new_templates = [
        # ID 12: Tim Fire & Floods
        {"cat_id": 12, "level": "Waspada", "title": "Periksa kesiapan unit pompa portable & ketersediaan bahan bakar."},
        {"cat_id": 12, "level": "Waspada", "title": "Pantau ketinggian air di sumur resapan & drainase utama gudang."},
        {"cat_id": 12, "level": "Siaga", "title": "Aktifkan pompa penyedot di area genangan tertinggi & amankan panel listrik."},
        {"cat_id": 12, "level": "Siaga", "title": "Pasang barikade pasir (sandbags) di pintu masuk rawan luapan air."},
        
        # ID 13: Tim Pengamanan
        {"cat_id": 13, "level": "Waspada", "title": "Monitor seluruh akses masuk/keluar & pagar pembatas secara rutin."},
        {"cat_id": 13, "level": "Waspada", "title": "Beri pengarahan ringkas kesiapsiagaan kepada staf di area kerja."},
        {"cat_id": 13, "level": "Siaga", "title": "Sterilisasi area insiden & amankan perimeter dari pihak luar."},
        {"cat_id": 13, "level": "Siaga", "title": "Bantu pengalihan arus kendaraan operasional ke area aman."},
        
        # ID 14: Tim Evakuasi
        {"cat_id": 14, "level": "Waspada", "title": "Pastikan seluruh jalur evakuasi bebas hambatan & lampu darurat menyala."},
        {"cat_id": 14, "level": "Waspada", "title": "Siapkan daftar absensi karyawan versi terbaru untuk verifikasi titik kumpul."},
        {"cat_id": 14, "level": "Siaga", "title": "Komando mobilisasi karyawan & tamu menuju Assembly Point."},
        {"cat_id": 14, "level": "Siaga", "title": "Pengecekan akhir (sweeping) ruangan untuk memastikan tidak ada yang tertinggal."},
        
        # ID 15: Tim P3K
        {"cat_id": 15, "level": "Waspada", "title": "Siapkan tas P3K darurat, tandu, dan stok obat-obatan luka."},
        {"cat_id": 15, "level": "Waspada", "title": "Pastikan jalur komunikasi ke klinik/RS rujukan tetap terbuka."},
        {"cat_id": 15, "level": "Siaga", "title": "Berikan pertolongan pertama & identifikasi korban di titik kumpul."},
        {"cat_id": 15, "level": "Siaga", "title": "Pantau kondisi kesehatan pengungsi & lakukan rujukan medis jika kritis."},
        
        # ID 16: Tim Logistik
        {"cat_id": 16, "level": "Waspada", "title": "Cek ketersediaan air minum & makanan darurat (ransum) di gudang logistik."},
        {"cat_id": 16, "level": "Waspada", "title": "Siapkan tenda darurat & selimut di area penyimpanan sementara."},
        {"cat_id": 16, "level": "Siaga", "title": "Distribusikan bantuan logistik & konsumsi kepada tim penolong & pengungsi."},
        {"cat_id": 16, "level": "Siaga", "title": "Pendataan & pengamanan aset operasional yang berhasil diselamatkan."},
        
        # ID 17: Tim Rehabilitasi
        {"cat_id": 17, "level": "Waspada", "title": "Siapkan peralatan perbaikan teknis & identifikasi vendor respon cepat."},
        {"cat_id": 17, "level": "Waspada", "title": "Backup data penting & amankan perangkat IT kritikal."},
        {"cat_id": 17, "level": "Siaga", "title": "Melakukan penilaian kerusakan awal (Damage Assessment) pada aset fisik."},
        {"cat_id": 17, "level": "Siaga", "title": "Rencanakan pembersihan area terdampak & koordinasi pemulihan daya listrik."},
        
        # ID 18: Tim Security
        {"cat_id": 18, "level": "Waspada", "title": "Tingkatkan frekuensi patroli & monitoring CCTV di area risiko tinggi."},
        {"cat_id": 18, "level": "Waspada", "title": "Koordinasi standby dengan aparat Kepolisian/TNI setempat."},
        {"cat_id": 18, "level": "Siaga", "title": "Cegah potensi penjarahan & amankan aset dari kerusakan lebih lanjut."},
        {"cat_id": 18, "level": "Siaga", "title": "Atur barikade lalu lintas untuk prioritas kendaraan darurat (Damkar/Ambulan)."}
    ]
    
    for t in new_templates:
        tmpl = TaskTemplate(
            team_category_id=t["cat_id"],
            status_level=t["level"],
            title=t["title"]
        )
        db.add(tmpl)
    
    db.commit()
    print(f"Successfully seeded {len(new_templates)} Emergency Task Templates.")
    
finally:
    db.close()
