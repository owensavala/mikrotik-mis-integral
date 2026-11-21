# Panel Kontrol & Monitoring MikroTik - MIS Integral Ternate

Sistem Manajemen Jaringan dan Monitoring Jarak Jauh berbasis Web untuk router MikroTik (RouterOS v7) di lingkungan Madrasah Ibtidaiyah Swasta (MIS) Integral Ternate.

## 🌟 Fitur Utama
1. **Sakelar Mode Jaringan (1-Klik)**:
   - **Mode Harian**: Hotspot aktif dengan autentikasi akun resmi guru (Rate limit 5M/5M).
   - **Mode Ujian**: Hotspot dinonaktifkan (bebas login tanpa captive portal) dan pembagian bandwidth adil aktif otomatis menggunakan **PCQ 3 Mbps**.
2. **Monitoring Real-Time & Wave Chart**:
   - Pemantauan CPU, Memori, Uptime, dan Status Dual-WAN (Indibiz & Telkomsel Orbit).
   - Grafik gelombang visual throughput Download (RX) & Upload (TX) detik-per-detik.
3. **Manajemen Akun Guru (CRUD)**:
   - Tambah, Lihat, Edit, dan Hapus akun Hotspot Guru.
   - Pencarian instan dan ekspor rekap ke **Excel (CSV)**.
   - Fitur **Cetak Laporan Resmi** lengkap dengan Kop Surat Sekolah dan Kolom Tanda Tangan Kepala Madrasah.
4. **Manajemen Profil Bandwidth (CRUD)**:
   - Pengaturan batas kecepatan (*Rate Limit*) dan jumlah perangkat per akun (*Shared Users*).
5. **Akses Jarak Jauh (Remote Management)**:
   - Terintegrasi dengan VPN Tunnel ID (SSTP Port 443 / API) sehingga dapat dikontrol dari mana saja.

## 🚀 Teknologi
- **Backend**: Python Flask 3, RouterOS API
- **Frontend**: HTML5, CSS3 Glassmorphism, Vanilla JS, HTML5 Canvas
- **Hardware Target**: MikroTik RouterBOARD (hEX / E50UG) RouterOS v7

## 💻 Penggunaan Lokal
```bash
# Jalankan langsung via batch script:
run_dashboard.bat

# Atau via python:
python app.py
```
Akses dashboard di browser: `http://localhost:5000`

---
&copy; 2026 MIS Integral Ternate • Administrator Jaringan: Muh. Sattar Barakati
