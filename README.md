# Panel Kontrol & Monitoring MikroTik - MIS Integral Ternate

Sistem Manajemen Jaringan dan Monitoring Jarak Jauh berbasis Web untuk router MikroTik (RouterOS v7) di lingkungan Madrasah Ibtidaiyah Swasta (MIS) Integral Ternate.

---

## 🌟 Fitur Utama
1. **Keamanan & Autentikasi Admin Terproteksi**:
   - Dilengkapi halaman **Login Administrator** dengan proteksi *HttpOnly Session Cookie*.
   - Seluruh endpoint API terproteksi dari akses publik tanpa izin.
   - Kredensial dapat dikonfigurasi aman via **Server Environment Variables**.
2. **Sakelar Mode Jaringan (1-Klik)**:
   - **Mode Harian**: Hotspot aktif dengan autentikasi akun resmi guru (Rate limit 5M/5M).
   - **Mode Ujian**: Hotspot dinonaktifkan (bebas login tanpa captive portal) dan pembagian bandwidth adil aktif otomatis menggunakan **PCQ 3 Mbps**.
3. **Monitoring Trafik Adaptif (Serverless-Friendly)**:
   - Pemantauan CPU, Memori, Uptime, dan Status Dual-WAN (Indibiz & Telkomsel Orbit).
   - Grafik gelombang visual throughput Download (RX) & Upload (TX).
   - Dilengkapi selektor frekuensi polling (*5 Detik*, *2 Detik*, *Jeda*) dan otomatis jeda saat tab browser tidak aktif untuk menghemat resource.
4. **Manajemen Akun Guru (CRUD)**:
   - Tambah, Lihat, Edit, dan Hapus akun Hotspot Guru.
   - Pencarian instan dan ekspor rekap ke **Excel (CSV)**.
   - Fitur **Cetak Laporan Resmi** lengkap dengan Kop Surat Sekolah dan Kolom Tanda Tangan Kepala Madrasah.
5. **Manajemen Profil Bandwidth (CRUD)**:
   - Pengaturan batas kecepatan (*Rate Limit*) dan jumlah perangkat per akun (*Shared Users*).
6. **Akses Jarak Jauh (Remote Management)**:
   - Terintegrasi dengan VPN Tunnel ID (SSTP Port 443 / API 3017) sehingga dapat dikontrol dari mana saja.

---

## 🔐 Kredensial Default Login Admin
- **Username**: `admin`
- **Password**: `admin123` *(Dapat diubah via menu Pengaturan atau via Environment Variable `ADMIN_PASSWORD`)*

---

## 🛠️ Konfigurasi Environment Variables
Untuk keamanan produksi di cloud (Vercel / Railway), atur Environment Variables berikut:

```env
# Koneksi Router MikroTik
MIKROTIK_HOST=idn32.tunnel.id
MIKROTIK_PORT=3017
MIKROTIK_USER=admin
MIKROTIK_PASSWORD=0020913463

# Akun Admin Web Dashboard
ADMIN_USER=admin
ADMIN_PASSWORD=admin123
SECRET_KEY=kunci-rahasia-acak-keamanan-session-2026
```

---

## 🚀 Pilihan Metode Deployment

### 1. Vercel (Serverless Cloud - Gratis & Cepat)
- Sangat praktis, tanpa perlu mengelola server atau membayar biaya bulanan.
- Gunakan frekuensi polling **5 Detik** agar koneksi tunnel tetap stabil dan hemat kuota invocation.
- Simpan kredensial di **Project Settings -> Environment Variables** di dashboard Vercel.

### 2. Railway / VPS (Persistent Server - Direkomendasikan untuk Monitoring 24/7)
- Menjalankan container Docker dengan proses Gunicorn yang terus menyala (*always-on*).
- Koneksi socket ke router MikroTik tidak mengalami *cold start*.
- Cukup hubungkan repository GitHub ini ke Railway, sistem akan mendeteksi `Dockerfile` dan `railway.json` secara otomatis.

### 3. Penggunaan Lokal (PC Operator / Server Ujian Sekolah)
```bash
# Jalankan langsung via batch script di Windows:
run_dashboard.bat

# Atau via python:
python app.py
```
Akses dashboard di browser: `http://localhost:5000`

---
&copy; 2026 MIS Integral Ternate • Administrator Jaringan: Muh. Sattar Barakati
