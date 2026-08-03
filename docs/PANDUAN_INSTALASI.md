# Panduan Instalasi Dashboard dari Nol

## Dashboard Analisis Sentimen dan SNA Telkom Group

Panduan ini dibuat untuk pengguna pemula yang belum terbiasa menggunakan File Explorer, Command Prompt, Git, Python, virtual environment, atau Streamlit. Ikuti langkah secara berurutan dan jangan melewati satu langkah pun.

---

## 1. Tujuan pengujian instalasi fresh

Pengujian ini mensimulasikan kondisi laptop baru dengan cara:

1. Mengamankan folder proyek lama sebagai backup.
2. Mengunduh ulang proyek dari GitHub menggunakan `git clone`.
3. Memastikan Python yang kompatibel tersedia.
4. Menjalankan launcher otomatis `run.bat` pada Windows atau `run.sh` pada macOS/Linux.
5. Memeriksa login, seluruh halaman utama, Mode Demo, terminal, dan Console browser.
6. Mencatat waktu instalasi dan seluruh error yang ditemukan.

> Jangan menghapus folder proyek lama. Folder tersebut hanya diganti nama sementara agar data dan pekerjaan sebelumnya tetap aman.

---

## 2. Persiapan sebelum mulai

Siapkan hal berikut:

- Koneksi internet yang stabil.
- Ruang kosong penyimpanan minimal sekitar 6 GB. Library PyTorch, Transformers, cache, dan virtual environment dapat berukuran besar.
- Browser Google Chrome atau Microsoft Edge.
- Git untuk Windows.
- Python 3.10 atau Python 3.11. Python 3.12 masih diterima launcher, tetapi Python 3.10 atau 3.11 adalah pilihan yang paling aman untuk dependency proyek ini.

Akun awal lokal:

```text
Username: admin
Password: admin123
```

Password tersebut hanya untuk instalasi awal dan demonstrasi lokal. Ganti password sebelum aplikasi dipublikasikan.

---

# BAGIAN A — SIMULASI INSTALASI FRESH DI WINDOWS

## Langkah 1 — Menutup dashboard lama

1. Lihat taskbar di bagian bawah layar Windows.
2. Cari jendela Command Prompt atau terminal yang sebelumnya menjalankan Streamlit.
3. Klik jendela terminal tersebut.
4. Tekan tombol `Ctrl` dan `C` secara bersamaan.
5. Jika muncul pertanyaan seperti `Terminate batch job (Y/N)?`, ketik `Y`, lalu tekan `Enter`.
6. Tutup browser dashboard lama.

Ciri berhasil:

- Terminal kembali menampilkan baris tempat mengetik perintah, atau jendela launcher berhenti.
- Alamat `http://localhost:8501` tidak lagi menampilkan dashboard lama setelah beberapa saat.

---

## Langkah 2 — Membuka File Explorer

1. Tekan tombol `Windows` dan `E` secara bersamaan.
2. File Explorer akan terbuka.
3. Pada panel sebelah kiri, klik lokasi tempat folder proyek disimpan, misalnya `Documents`, `Downloads`, atau `Desktop`.
4. Cari folder proyek lama. Nama folder dapat berupa `dashboard-sna`, `project`, atau nama versi skripsi yang Anda gunakan.

---

## Langkah 3 — Mengganti nama folder proyek lama menjadi backup

1. Klik satu kali folder proyek lama.
2. Klik kanan folder tersebut.
3. Klik menu **Rename** atau **Ganti nama**.
4. Ubah nama menjadi:

```text
dashboard-sna_backup
```

5. Tekan `Enter`.

Ciri berhasil:

- Folder lama masih ada.
- Namanya berubah menjadi `dashboard-sna_backup`.
- Isi folder tidak terhapus.

Jika Windows menolak penggantian nama:

1. Pastikan Streamlit dan semua terminal yang menggunakan folder tersebut sudah ditutup.
2. Tutup aplikasi editor seperti Visual Studio Code atau Cursor.
3. Ulangi proses rename.

---

## Langkah 4 — Membuka Command Prompt

1. Tekan tombol `Windows` pada keyboard.
2. Ketik:

```text
cmd
```

3. Klik **Command Prompt**, atau tekan `Enter`.
4. Jendela hitam akan terbuka.

Anda tidak perlu menjalankan Command Prompt sebagai Administrator untuk proses normal ini.

---

## Langkah 5 — Berpindah ke folder induk

Folder induk adalah lokasi tempat folder proyek baru akan dibuat. Contoh berikut menggunakan folder `Documents`.

Ketik perintah berikut, lalu tekan `Enter`:

```bat
cd /d "%USERPROFILE%\Documents"
```

Untuk menggunakan Desktop, ketik:

```bat
cd /d "%USERPROFILE%\Desktop"
```

Untuk memastikan lokasi sudah benar, ketik:

```bat
dir
```

Ciri berhasil:

- Nama folder yang tampil sesuai lokasi tujuan.
- Folder `dashboard-sna_backup` terlihat jika backup disimpan di lokasi yang sama.

Ciri gagal:

- Muncul pesan `The system cannot find the path specified`.

Solusi:

1. Buka File Explorer.
2. Masuk ke folder tujuan.
3. Klik kolom alamat di bagian atas File Explorer.
4. Salin alamat folder.
5. Kembali ke Command Prompt.
6. Ketik `cd /d`, beri satu spasi, lalu tempel alamat dalam tanda kutip. Contoh:

```bat
cd /d "D:\Skripsi"
```

---

## Langkah 6 — Memastikan Git tersedia

Di Command Prompt, ketik:

```bat
git --version
```

Hasil yang diharapkan menyerupai:

```text
git version 2.x.x.windows.x
```

Jika muncul pesan `git is not recognized`:

1. Buka browser Chrome atau Edge.
2. Cari **Git for Windows**.
3. Buka situs resmi Git.
4. Unduh installer Windows.
5. Jalankan installer.
6. Gunakan pilihan default dengan menekan **Next** sampai instalasi selesai.
7. Tutup Command Prompt lama.
8. Buka Command Prompt baru.
9. Jalankan kembali `git --version`.

---

## Langkah 7 — Clone proyek dari GitHub

Pastikan Command Prompt berada di folder induk, lalu copy-paste perintah berikut:

```bat
git clone https://github.com/SaefudinZuhri1/dashboard-sna.git
```

Tekan `Enter` dan tunggu sampai proses selesai.

Ciri clone berhasil:

- Muncul teks `Cloning into 'dashboard-sna'...`.
- Proses berakhir tanpa kata `fatal:`.
- Folder baru bernama `dashboard-sna` muncul di File Explorer.

Ciri clone gagal:

- Muncul teks `fatal:`.
- Muncul pesan repository tidak ditemukan, autentikasi gagal, atau koneksi gagal.

Solusi umum:

- Periksa koneksi internet.
- Pastikan alamat repository diketik persis.
- Jika folder `dashboard-sna` sudah ada, rename atau hapus folder clone yang gagal terlebih dahulu. Jangan menghapus folder backup.

Setelah clone selesai, masuk ke folder proyek:

```bat
cd dashboard-sna
```

Periksa isi folder:

```bat
dir
```

File minimum yang harus terlihat:

```text
app.py
requirements.txt
run.bat
run.sh
UI_UX_LOCK.md
docs
```

Jika `run.bat` atau folder `docs` tidak terlihat, repository GitHub belum berisi patch instalasi terbaru. Jangan lanjut ke launcher sebelum file tersebut dipush ke GitHub.

---

## Langkah 8 — Memastikan versi Python

Di Command Prompt yang masih berada di folder `dashboard-sna`, ketik:

```bat
python --version
```

Jika perintah tersebut gagal, coba:

```bat
py --version
```

Hasil yang disarankan:

```text
Python 3.10.x
```

atau:

```text
Python 3.11.x
```

Launcher menerima Python 3.10 sampai 3.12. Python 3.13 atau lebih baru belum digunakan sebagai baseline dependency proyek.

### Jika Python belum terpasang

1. Buka browser Chrome atau Edge.
2. Masuk ke situs resmi `python.org`.
3. Buka menu **Downloads**.
4. Pilih installer Python 3.11 untuk Windows 64-bit.
5. Setelah file selesai diunduh, klik dua kali installer.
6. Pada layar pertama installer, cari kotak **Add Python to PATH**.
7. Centang kotak tersebut. Langkah ini wajib.
8. Klik **Install Now**.
9. Tunggu sampai muncul pesan instalasi berhasil.
10. Tutup installer.
11. Tutup Command Prompt lama.
12. Buka Command Prompt baru.
13. Jalankan kembali:

```bat
python --version
```

---

## Langkah 9 — Menjalankan `run.bat`

Cara paling mudah:

1. Buka File Explorer dengan `Windows + E`.
2. Masuk ke folder hasil clone bernama `dashboard-sna`.
3. Cari file `run.bat`.
4. Klik dua kali `run.bat`.
5. Jendela terminal hitam akan terbuka.
6. Jangan menutup jendela tersebut.

Pada penggunaan pertama, launcher akan:

1. Memastikan `app.py` dan `requirements.txt` tersedia.
2. Mencari Python 3.10, 3.11, atau 3.12.
3. Membuat folder `venv`.
4. Memperbarui pip.
5. Menginstal dependency dari `requirements.txt`.
6. Memeriksa library inti.
7. Menjalankan Streamlit.
8. Membuka browser secara otomatis.

Teks sukses yang dapat muncul:

```text
[OK] Python ditemukan
[OK] Virtual environment berhasil dibuat
[OK] Seluruh dependency berhasil dipasang
[INFO] Memulai dashboard
```

Teks gagal yang perlu dicatat:

```text
[GAGAL]
ERROR
FAILED
No matching distribution found
ModuleNotFoundError
Traceback
```

Launcher sengaja menahan jendela ketika gagal agar pesan error tidak langsung hilang.

---

## Langkah 10 — Mencatat waktu instalasi

Sebelum klik dua kali `run.bat`:

1. Lihat jam Windows di pojok kanan bawah.
2. Catat jam mulai pada tabel berikut.
3. Setelah browser menampilkan halaman login dan siap digunakan, catat jam selesai.
4. Hitung selisih waktunya.

| Catatan | Isi setelah pengujian |
|---|---|
| Tanggal pengujian |  |
| Jam mulai `run.bat` |  |
| Jam halaman login siap |  |
| Total durasi |  |
| Kecepatan internet |  |
| Versi Windows |  |
| Versi Python |  |

Unduhan PyTorch dan dependency NLP dapat memerlukan waktu lama. Selama persentase unduhan atau aktivitas instalasi masih berubah dan tidak muncul `ERROR`, proses belum tentu bermasalah.

---

# BAGIAN B — CHECKLIST VERIFIKASI WAJIB

## CEK 1 — Clone GitHub berhasil

1. Buka File Explorer.
2. Masuk ke folder induk tempat clone dilakukan.
3. Pastikan ada folder baru `dashboard-sna`.
4. Buka folder tersebut.
5. Pastikan `app.py` terlihat.
6. Kembali ke terminal dan pastikan tidak ada teks `fatal:` pada proses clone.

Status:

- [ ] Berhasil
- [ ] Gagal

Catatan error:

```text
Tempel error di sini.
```

---

## CEK 2 — Versi Python benar

1. Buka Command Prompt.
2. Masuk ke folder proyek:

```bat
cd /d "LOKASI_FOLDER_ANDA\dashboard-sna"
```

3. Jalankan:

```bat
python --version
```

4. Pastikan hasil menunjukkan Python 3.10, 3.11, atau 3.12.

Status:

- [ ] Berhasil
- [ ] Gagal

---

## CEK 3 — `run.bat` berhasil dijalankan

1. Buka folder `dashboard-sna` di File Explorer.
2. Klik dua kali `run.bat`.
3. Pastikan jendela terminal tidak langsung tertutup.
4. Pastikan muncul teks pemeriksaan Python, virtual environment, atau dependency.

Jika jendela langsung tertutup:

1. Buka Command Prompt.
2. Masuk ke folder proyek.
3. Jalankan launcher dari terminal agar error tetap terlihat:

```bat
run.bat
```

Untuk membuka isi launcher tanpa menjalankannya:

1. Klik kanan `run.bat`.
2. Pilih **Show more options** jika tersedia.
3. Pilih **Edit** atau **Open with > Notepad**.
4. Jangan mengubah isinya jika hanya ingin membaca.

Status:

- [ ] Berhasil
- [ ] Gagal

---

## CEK 4 — Semua library terpasang tanpa error

Saat `run.bat` berjalan:

1. Biarkan terminal terbuka.
2. Perhatikan baris instalasi.
3. Jangan menganggap teks kuning sebagai error. Teks kuning biasanya hanya warning.
4. Cari kata `ERROR`, `FAILED`, atau `No matching distribution found`.
5. Jika tidak ada kata tersebut dan muncul `[OK] Seluruh dependency berhasil dipasang`, instalasi dependency berhasil.

Cara menyalin error dari Command Prompt:

1. Klik kanan bagian atas jendela Command Prompt.
2. Pilih **Edit > Select All**, atau blok teks error menggunakan mouse.
3. Tekan `Enter` untuk menyalin teks yang dipilih.
4. Tempel error ke chat menggunakan `Ctrl + V`.

Status:

- [ ] Berhasil
- [ ] Gagal

---

## CEK 5 — Dashboard terbuka di browser

1. Tunggu browser terbuka otomatis.
2. Periksa kolom alamat browser.
3. Alamat biasanya:

```text
http://localhost:8501
```

4. Jika port 8501 sedang dipakai, launcher menggunakan:

```text
http://localhost:8502
```

5. Jika browser tidak terbuka otomatis, buka Chrome atau Edge secara manual.
6. Klik kolom alamat.
7. Ketik salah satu alamat di atas.
8. Tekan `Enter`.
9. Alternatif alamat:

```text
http://127.0.0.1:8501
```

Ciri berhasil:

- Halaman login dashboard tampil.
- Tidak muncul pesan `This site can't be reached`.

Status:

- [ ] Berhasil
- [ ] Gagal

---

## CEK 6 — Login admin berhasil

1. Pada halaman login, klik kolom **Username**.
2. Ketik:

```text
admin
```

3. Klik kolom **Password**.
4. Ketik:

```text
admin123
```

5. Klik tombol **Masuk** atau **Login**.
6. Tunggu sampai halaman Beranda tampil.

Ciri berhasil:

- Halaman login menghilang.
- Sidebar dan halaman Beranda terlihat.
- Tidak ada pesan kredensial salah.

Status:

- [ ] Berhasil
- [ ] Gagal

---

## CEK 7 — Semua halaman utama dapat dibuka

Sidebar adalah panel navigasi yang berada di sebelah kiri layar dashboard. Jika sidebar tertutup, klik ikon panah atau menu di pojok kiri atas Streamlit.

Buka menu berikut satu per satu:

1. Klik **Beranda**. Pastikan ringkasan tampil dan tidak ada kotak error merah.
2. Klik **Dataset**. Pastikan tabel atau fallback data tampil.
3. Klik **Analisis Sentimen**. Pastikan grafik atau ringkasan sentimen tampil.
4. Klik **Analisis Topik**. Pastikan WordCloud atau konten topik tampil.
5. Klik **Social Network Analysis / SNA**. Pastikan statistik atau visualisasi jaringan tampil.
6. Klik **Rekomendasi**. Pastikan konten rekomendasi tampil.
7. Klik **Tentang / About**. Pastikan informasi penelitian tampil.
8. Jika akun admin menampilkan **Admin Panel**, buka dan pastikan halaman tampil.

Gunakan tabel berikut:

| Halaman | Tampil | Tidak ada error merah | Catatan |
|---|---:|---:|---|
| Beranda | [ ] | [ ] |  |
| Dataset | [ ] | [ ] |  |
| Analisis Sentimen | [ ] | [ ] |  |
| Analisis Topik | [ ] | [ ] |  |
| SNA | [ ] | [ ] |  |
| Rekomendasi | [ ] | [ ] |  |
| About | [ ] | [ ] |  |
| Admin Panel | [ ] | [ ] |  |

---

## CEK 8 — Mode Demo aktif dan berfungsi

1. Lihat sidebar sebelah kiri.
2. Cari toggle bertuliskan **Mode Demo (Sidang)**.
3. Klik toggle sampai aktif.
4. Pastikan muncul penanda bahwa Mode Demo aktif.
5. Buka halaman Beranda, Dataset, Analisis Sentimen, Analisis Topik, SNA, dan Rekomendasi.
6. Pastikan setiap halaman menampilkan data sample dan tidak blank.

Status:

- [ ] Toggle Mode Demo dapat diaktifkan
- [ ] Beranda menampilkan data demo
- [ ] Dataset menampilkan data demo
- [ ] Sentimen menampilkan data demo
- [ ] Analisis Topik menampilkan data demo
- [ ] SNA menampilkan data demo
- [ ] Rekomendasi menampilkan data demo

---

## CEK 9 — Tidak ada error terminal saat halaman dibuka

1. Jangan tutup terminal launcher.
2. Atur browser dan terminal berdampingan:
   - Klik browser.
   - Tekan `Windows + Panah Kiri`.
   - Klik terminal.
   - Tekan `Windows + Panah Kanan`.
3. Klik setiap menu dashboard dari browser.
4. Setelah setiap klik, lihat terminal.
5. Cari kata `Traceback`, `ERROR`, `Exception`, atau baris merah.

Ciri aman:

- Tidak ada traceback baru.
- Terminal hanya menampilkan log normal atau warning yang tidak menghentikan aplikasi.

Status:

- [ ] Berhasil
- [ ] Gagal

---

## CEK 10 — Console browser tidak menampilkan error JavaScript kritis

1. Aktifkan browser dashboard.
2. Tekan tombol `F12`.
3. Jika F12 mengatur volume atau fungsi laptop lain, tekan `Fn + F12`.
4. Panel Developer Tools akan terbuka di sisi kanan atau bawah browser.
5. Klik tab **Console**.
6. Klik ikon tempat sampah atau tombol **Clear console** agar log lama hilang.
7. Muat ulang dashboard dengan `Ctrl + R`.
8. Buka beberapa halaman dashboard.
9. Periksa apakah ada baris merah dengan kata `Error`.

Catatan:

- Warning kuning belum tentu merusak aplikasi.
- Error dari ekstensi browser dapat diuji ulang melalui jendela Incognito.
- Salin error merah jika tampilan dashboard rusak atau kontrol tidak berfungsi.

Status:

- [ ] Tidak ada error JavaScript kritis
- [ ] Ada error dan sudah dicatat

---

## CEK 11 — Waktu instalasi tercatat

Isi data berikut:

| Data | Hasil |
|---|---|
| Jam mulai |  |
| Jam selesai |  |
| Total waktu |  |
| Tahap paling lama |  |
| Ada error instalasi | Ya / Tidak |

Status:

- [ ] Selesai dicatat

---

## CEK 12 — Mengembalikan folder backup

Jangan melakukan langkah ini sebelum pengujian selesai dan folder clone baru sudah diperiksa.

Pilihan yang paling aman adalah mempertahankan dua folder dengan nama berbeda:

```text
dashboard-sna
 dashboard-sna_backup
```

Jika folder backup harus dikembalikan menjadi nama utama:

1. Hentikan Streamlit dengan `Ctrl + C`.
2. Tutup terminal dan editor.
3. Di File Explorer, rename folder clone baru menjadi `dashboard-sna_fresh_test`.
4. Klik kanan `dashboard-sna_backup`.
5. Klik **Rename**.
6. Ubah menjadi `dashboard-sna`.
7. Tekan `Enter`.

Status:

- [ ] Backup tetap aman
- [ ] Nama folder sudah sesuai kebutuhan

---

## CEK 13 — Konfirmasi akhir

Pengujian hanya dinyatakan selesai apabila semua pemeriksaan penting berhasil.

Kalimat konfirmasi akhir:

```text
App berhasil diinstall dan dijalankan dari nol ✅
```

Jangan mengirim kalimat tersebut jika masih ada satu cek yang gagal. Kirim pesan error, screenshot, dan nama cek yang gagal untuk proses debug.

---

# BAGIAN C — TROUBLESHOOTING

## Error: Python tidak ditemukan

Ciri pesan:

```text
Python was not found
```

atau:

```text
'python' is not recognized
```

Solusi:

1. Instal Python 3.10 atau 3.11 dari situs resmi Python.
2. Centang **Add Python to PATH**.
3. Tutup dan buka kembali Command Prompt.
4. Jalankan `python --version`.
5. Jalankan `run.bat` kembali.

---

## Error: Git tidak ditemukan

Ciri pesan:

```text
'git' is not recognized
```

Solusi:

1. Instal Git for Windows.
2. Gunakan opsi instalasi default.
3. Tutup dan buka kembali Command Prompt.
4. Jalankan `git --version`.

---

## Error: pip gagal atau tidak dikenali

Launcher tidak menggunakan perintah `pip` langsung. Launcher menggunakan Python di dalam `venv`:

```bat
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cara manual:

```bat
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Error: `No module named streamlit`

1. Buka Command Prompt pada folder proyek.
2. Jalankan:

```bat
venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Setelah selesai, jalankan:

```bat
venv\Scripts\python.exe -m streamlit run app.py
```

---

## Error: virtual environment rusak

Ciri masalah:

- `venv\Scripts\python.exe` tidak ditemukan.
- Python lama sudah dihapus atau dipindahkan.
- Import library gagal terus walaupun requirements tidak berubah.

Solusi aman:

1. Hentikan Streamlit.
2. Tutup terminal.
3. Buka folder proyek di File Explorer.
4. Hapus hanya folder `venv`.
5. Jangan menghapus `app.py`, `data`, `models`, `database`, atau file proyek lain.
6. Klik dua kali `run.bat`.
7. Launcher akan membuat `venv` baru.

---

## Error: PyTorch atau dependency gagal diunduh

Kemungkinan penyebab:

- Koneksi internet putus.
- Ruang penyimpanan kurang.
- Versi Python tidak kompatibel.
- Server package sedang lambat.

Langkah:

1. Pastikan Python adalah 3.10 atau 3.11.
2. Pastikan ruang kosong masih tersedia.
3. Jalankan kembali `run.bat`.
4. Jika masih gagal, salin baris mulai dari `ERROR` sampai akhir pesan.

Unduhan besar yang masih berjalan bukan error. Jangan menutup terminal selama ukuran unduhan masih bertambah.

---

## Error: port 8501 sudah digunakan

Launcher otomatis mencoba port 8502 jika 8501 terdeteksi sedang dipakai.

Buka:

```text
http://localhost:8502
```

Jika kedua port bermasalah:

1. Tutup terminal Streamlit lama.
2. Buka Task Manager dengan `Ctrl + Shift + Esc`.
3. Cari proses Python yang memang berasal dari dashboard lama.
4. Akhiri proses hanya jika Anda yakin proses tersebut adalah server lama.
5. Jalankan kembali `run.bat`.

---

## Browser tidak terbuka otomatis

1. Pastikan terminal menampilkan `[INFO] Alamat dashboard`.
2. Buka Chrome atau Edge secara manual.
3. Ketik alamat yang ditampilkan terminal.
4. Coba `http://localhost:8501`.
5. Jika launcher memilih port alternatif, coba `http://localhost:8502`.
6. Coba juga `http://127.0.0.1:8501`.

---

## Database terkunci atau login gagal

1. Pastikan hanya satu server Streamlit proyek yang berjalan.
2. Hentikan server lama dengan `Ctrl + C`.
3. Jalankan kembali `run.bat`.
4. Coba akun awal `admin / admin123`.
5. Jangan menghapus `database/users.db` tanpa backup karena akun pengguna tersimpan di dalamnya.

---

## Model IndoBERT tidak tersedia

Folder model besar dapat tidak ikut GitHub. Kondisi tersebut tidak boleh membuat seluruh dashboard gagal dibuka. Gunakan Mode Demo untuk memeriksa antarmuka dan fallback data.

Untuk pengujian model aktual, salin folder model yang sesuai ke:

```text
models\indihome
models\indibiz
models\telkomsel
```

Jangan menganggap hasil Mode Demo sebagai hasil penelitian aktual.

---

# BAGIAN D — MACOS DAN LINUX

## Menjalankan launcher

1. Buka Terminal.
2. Masuk ke folder proyek. Contoh:

```bash
cd ~/Documents/dashboard-sna
```

3. Berikan izin eksekusi satu kali:

```bash
chmod +x run.sh
```

4. Jalankan:

```bash
./run.sh
```

Launcher akan mencari Python 3.11, 3.10, 3.12, `python3`, lalu `python`. Browser dibuka otomatis jika perintah sistem mendukungnya.

Jika `python3 -m venv` gagal pada Ubuntu/Debian, jalankan:

```bash
sudo apt update
sudo apt install python3-venv
```

Kemudian jalankan kembali:

```bash
./run.sh
```

---

# BAGIAN E — CATATAN HASIL AUDIT FASE 15

Audit kode dilakukan tanpa mengubah UI/UX dashboard.

Temuan sebelum patch:

1. Launcher lama belum berhenti secara aman ketika pembuatan `venv` atau instalasi dependency gagal.
2. Launcher lama menggunakan `pip` dan `streamlit` secara langsung sehingga lebih rentan memakai Python di luar `venv`.
3. Launcher lama belum memeriksa versi Python yang kompatibel.
4. Launcher lama belum memeriksa perubahan `requirements.txt`.
5. Launcher lama belum memeriksa port 8501 sebelum menjalankan server.
6. Folder `docs/` dan `docs/PANDUAN_INSTALASI.md` belum tersedia pada arsip yang diaudit.
7. Fresh clone hanya dapat diuji setelah `run.bat`, `run.sh`, dan folder `docs/` benar-benar dipush ke GitHub.

Validasi teknis patch:

- Pemeriksaan sintaks Python proyek: lulus `compileall`.
- Pemeriksaan sintaks `run.sh`: wajib lulus `bash -n run.sh` sebelum rilis.
- Pengujian penuh launcher Windows dan unduhan dependency tetap harus dilakukan pada komputer Windows dengan internet karena lingkungan audit bukan Windows dan tidak memiliki akses unduhan package.

---

## Form hasil akhir pengujian pengguna

| Pemeriksaan | Hasil | Catatan |
|---|---|---|
| Clone GitHub | Lulus / Gagal |  |
| Python | Lulus / Gagal |  |
| run.bat | Lulus / Gagal |  |
| Dependency | Lulus / Gagal |  |
| Browser | Lulus / Gagal |  |
| Login admin | Lulus / Gagal |  |
| Semua halaman | Lulus / Gagal |  |
| Mode Demo | Lulus / Gagal |  |
| Terminal | Lulus / Gagal |  |
| DevTools Console | Lulus / Gagal |  |
| Durasi tercatat | Lulus / Gagal |  |
| Backup aman | Lulus / Gagal |  |

Konfirmasi final hanya setelah semua pemeriksaan penting lulus:

```text
App berhasil diinstall dan dijalankan dari nol ✅
```
