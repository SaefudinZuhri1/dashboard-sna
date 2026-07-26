# Panduan Instalasi Dashboard Telkom Group

Panduan ini ditulis untuk pengguna yang belum pernah memasang atau menjalankan proyek Python. Ikuti urutan dari awal sampai akhir dan jangan melewati langkah verifikasi.

## Prasyarat

Sebelum memulai, siapkan:

1. Laptop atau komputer Windows 10/11, macOS, atau Linux.
2. Ruang penyimpanan kosong yang cukup. Library AI, cache Hugging Face, data, dan model dapat menggunakan beberapa gigabita.
3. Koneksi internet stabil, terutama saat pertama kali menginstal PyTorch, Transformers, dan model.
4. Python 3.10 atau 3.11. Walaupun proyek mensyaratkan Python 3.10+, versi 3.10 atau 3.11 adalah pilihan paling aman untuk dependency proyek saat ini.
5. Git jika ingin mengunduh proyek dengan perintah clone. Git tidak wajib apabila menggunakan Download ZIP.
6. Browser seperti Google Chrome atau Microsoft Edge.

## Cara Memeriksa Python

### Windows

1. Tekan tombol **Windows** pada keyboard.
2. Ketik `cmd`.
3. Klik **Command Prompt**.
4. Ketik:

```bat
python --version
```

5. Tekan **Enter**.

Jika muncul versi 3.10 atau 3.11, Python siap digunakan. Contoh:

```text
Python 3.10.11
```

Jika `python` tidak dikenali, coba:

```bat
py --version
```

Untuk melihat seluruh Python yang terpasang:

```bat
py -0p
```

### macOS/Linux

Buka Terminal, lalu jalankan:

```bash
python3 --version
```

## Cara Memeriksa Git

Jalankan:

```bat
git --version
```

Hasil yang benar berbentuk:

```text
git version 2.x.x
```

Jika Git belum ada, ikuti bagian instalasi Git di bawah.

# Instalasi di Windows

## Langkah 1: Instal Python

### A. Download Python yang kompatibel

Gunakan halaman resmi Python 3.10.11 yang masih menyediakan installer Windows 64-bit:

```text
https://www.python.org/downloads/release/python-31011/
```

1. Buka Google Chrome.
2. Salin alamat di atas ke kolom alamat browser.
3. Tekan **Enter**.
4. Gulir ke bagian **Files**.
5. Cari **Windows installer (64-bit)**.
6. Klik tulisan tersebut.
7. Tunggu file installer selesai diunduh.

### B. Jalankan installer

1. Buka folder **Downloads**.
2. Klik dua kali file installer Python.
3. Pada layar pertama, cari kotak **Add Python to PATH**.
4. **Wajib centang kotak tersebut.**
5. Klik **Install Now**.
6. Jika Windows meminta izin, klik **Yes**.
7. Tunggu sampai muncul tulisan **Setup was successful**.
8. Klik **Close**.

`PATH` adalah daftar lokasi yang boleh dicari Windows ketika Anda mengetik perintah. Tanpa pengaturan ini, Windows dapat menampilkan pesan bahwa `python` tidak dikenali.

### C. Verifikasi instalasi

1. Tutup semua jendela CMD lama.
2. Buka CMD baru.
3. Jalankan:

```bat
py -3.10 --version
```

Target hasil:

```text
Python 3.10.11
```

## Langkah 2: Instal Git

Halaman resmi Git for Windows:

```text
https://git-scm.com/install/windows
```

1. Buka alamat tersebut melalui browser.
2. Download versi **x64**.
3. Buka file installer.
4. Jika Windows meminta izin, klik **Yes**.
5. Pada setiap layar installer, gunakan pilihan bawaan dengan menekan **Next**.
6. Ketika instalasi selesai, klik **Finish**.
7. Tutup CMD lama dan buka CMD baru.
8. Jalankan:

```bat
git --version
```

Jika nomor versi tampil, Git siap digunakan.

## Langkah 3: Download atau Clone Proyek

### Pilihan A — Clone menggunakan Git

1. Buka File Explorer.
2. Pilih lokasi penyimpanan, misalnya drive `G:`.
3. Klik kolom alamat File Explorer.
4. Ketik `cmd`, lalu tekan **Enter**.
5. Jalankan:

```bat
git clone https://github.com/SaefudinZuhri1/dashboard-sna.git
```

6. Setelah selesai, masuk ke folder proyek:

```bat
cd dashboard-sna
```

7. Pastikan `app.py` tersedia:

```bat
dir app.py
```

### Pilihan B — Download ZIP tanpa Git

1. Buka:

```text
https://github.com/SaefudinZuhri1/dashboard-sna
```

2. Klik tombol **Code**.
3. Klik **Download ZIP**.
4. Tunggu download selesai.
5. Buka folder **Downloads**.
6. Klik kanan file ZIP.
7. Pilih **Extract All**.
8. Klik **Extract**.
9. Buka folder hasil ekstrak.
10. Pastikan di dalamnya ada `app.py` dan `requirements.txt`.

## Langkah 4: Buka Terminal di Folder Proyek

Cara termudah:

1. Buka folder proyek di File Explorer.
2. Pastikan `app.py` terlihat.
3. Klik kolom alamat di bagian atas.
4. Ketik:

```text
cmd
```

5. Tekan **Enter**.

CMD akan terbuka tepat di folder proyek. Contoh:

```text
G:\skripsi_aul>
```

Alternatif menggunakan perintah `cd`:

```bat
cd /d "G:\skripsi_aul"
```

`/d` memungkinkan CMD berpindah drive dan folder sekaligus. Tanda kutip menjaga alamat folder yang mengandung spasi tetap terbaca dengan benar.

## Langkah 5: Buat Virtual Environment

Virtual environment adalah folder terpisah yang menyimpan library proyek agar tidak bercampur dengan proyek lain.

Jalankan:

```bat
py -3.10 -m venv venv
```

Tunggu sampai folder `venv` muncul. Biasanya tidak ada pesan khusus jika berhasil.

Aktifkan dengan:

```bat
venv\Scripts\activate
```

Hasil yang benar:

```text
(venv) G:\skripsi_aul>
```

Periksa Python aktif:

```bat
where python
```

Baris pertama harus mengarah ke:

```text
G:\skripsi_aul\venv\Scripts\python.exe
```

## Langkah 6: Install Library Python

### A. Perbarui pip

```bat
python -m pip install --upgrade pip
```

### B. Instal dependency proyek

```bat
python -m pip install -r requirements.txt
```

Yang terjadi saat proses ini berjalan:

- pip membaca `requirements.txt`;
- library diunduh dari internet;
- PyTorch, Transformers, Streamlit, Plotly, NetworkX, Pyvis, dan dependency lain dipasang ke folder `venv`;
- proses dapat memerlukan waktu sekitar 10–45 menit, tergantung kecepatan internet dan komputer;
- beberapa baris bertuliskan `Requirement already satisfied` adalah normal;
- jangan menutup CMD sebelum proses selesai.

Proses berhasil jika tidak ada pesan akhir `ERROR` dan muncul `Successfully installed` atau seluruh paket sudah tersedia.

Verifikasi Streamlit:

```bat
python -m streamlit --version
```

Target baseline:

```text
Streamlit, version 1.59.2
```

## Langkah 7: Setting API Key Gemini (Opsional)

Gemini hanya dibutuhkan oleh fitur rekomendasi dan ide konten berbasis AI. Dashboard tetap dapat dibuka tanpa API key karena tersedia fallback lokal.

### A. Dapatkan API key

Buka halaman resmi Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

1. Login menggunakan akun Google.
2. Buka halaman **API Keys**.
3. Klik **Create API key** apabila belum ada key.
4. Pilih proyek Google Cloud milik Anda.
5. Klik tombol pembuatan key.
6. Klik ikon **Copy**.
7. Jangan mengirim key melalui chat atau screenshot.

### B. Buat atau buka file `.env`

1. Kembali ke folder proyek yang berisi `app.py`.
2. Cari file `.env`.
3. Jika ada, klik kanan lalu pilih **Open with → Notepad**.
4. Jika belum ada, buka Notepad dan tulis:

```env
GEMINI_API_KEY=API_KEY_ASLI_ANDA
```

5. Ganti `API_KEY_ASLI_ANDA` dengan key yang sudah disalin.
6. Pilih **File → Save As**.
7. Pada **File name**, tulis `.env`.
8. Pada **Save as type**, pilih **All Files**.
9. Simpan sejajar dengan `app.py`.
10. Pastikan nama file bukan `.env.txt`.

Format yang benar:

```env
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

Jangan menggunakan spasi atau tanda kutip pada file `.env`.

## Langkah 8: Siapkan Data dan Model

Folder `data/` dan `models/` dapat tidak ikut di repository karena berukuran besar atau bersifat lokal.

- Jika data penelitian tersedia, letakkan file hasil sentimen, topik, dan SNA di folder `data/` sesuai nama yang digunakan aplikasi.
- Jika model lokal tersedia, letakkan konfigurasi, tokenizer, dan weight di `models/indihome/`, `models/indibiz/`, dan `models/telkomsel/`.
- Jika folder tersebut belum tersedia, dashboard akan memakai data dummy atau menampilkan status yang sesuai.
- Jangan menyalin file model satu layanan ke folder layanan lain.

## Langkah 9: Jalankan Dashboard

Pastikan awal terminal menampilkan `(venv)`, lalu jalankan:

```bat
streamlit run app.py
```

Jika perintah tersebut tidak dikenali, gunakan:

```bat
python -m streamlit run app.py
```

Jika berhasil, terminal menampilkan alamat seperti:

```text
Local URL: http://localhost:8501
```

Browser biasanya terbuka otomatis. Jika tidak:

1. Buka Google Chrome.
2. Ketik:

```text
http://localhost:8501
```

3. Tekan **Enter**.

## Langkah 10: Login Pertama

Gunakan akun awal:

```text
Username : admin
Password : admin123
```

Setelah login, segera buka **Profil → Ubah Password Akun** dan ganti password awal.

## Cara Menghentikan Dashboard

1. Kembali ke CMD yang menjalankan Streamlit.
2. Klik area CMD.
3. Tekan:

```text
Ctrl + C
```

4. Tunggu sampai kembali ke prompt `(venv)`.
5. Tutup browser atau tab dashboard.

# Instalasi di macOS

## 1. Periksa Python dan Git

```bash
python3 --version
git --version
```

## 2. Clone proyek

```bash
git clone https://github.com/SaefudinZuhri1/dashboard-sna.git
cd dashboard-sna
```

Atau download ZIP dari GitHub, ekstrak, lalu buka Terminal pada folder proyek.

## 3. Buat dan aktifkan virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 4. Instal dependency

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 5. Isi `.env` bila memakai Gemini

```bash
printf 'GEMINI_API_KEY=API_KEY_ASLI_ANDA\n' > .env
```

Buka `.env` menggunakan editor teks, lalu ganti nilai contoh dengan API key asli.

## 6. Jalankan dashboard

```bash
python -m streamlit run app.py
```

Buka `http://localhost:8501` apabila browser tidak terbuka otomatis.

# Instalasi di Linux

Perintah berikut menggunakan Ubuntu/Debian. Distribusi Linux lain dapat memiliki nama paket yang berbeda.

## 1. Instal Python, venv, pip, dan Git

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

## 2. Clone dan masuk ke proyek

```bash
git clone https://github.com/SaefudinZuhri1/dashboard-sna.git
cd dashboard-sna
```

## 3. Buat virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 4. Instal dependency

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 5. Jalankan dashboard

```bash
python -m streamlit run app.py
```

# Konfigurasi Streamlit Community Cloud

1. Pastikan proyek sudah ada pada repository GitHub.
2. Pastikan `.env`, `.streamlit/secrets.toml`, `database/users.db`, dan model besar tidak ikut commit.
3. Buka Streamlit Community Cloud:

```text
https://share.streamlit.io/
```

4. Login menggunakan akun GitHub.
5. Klik **Create app**.
6. Pilih repository `SaefudinZuhri1/dashboard-sna`.
7. Pilih branch yang digunakan, umumnya `main`.
8. Isi **Main file path** dengan:

```text
app.py
```

9. Buka **Advanced settings** atau pengaturan Secrets.
10. Masukkan:

```toml
GEMINI_API_KEY = "API_KEY_ASLI_ANDA"
```

11. Klik **Deploy**.
12. Tunggu proses build selesai.
13. Baca log deployment jika aplikasi gagal dibuka.

# Troubleshooting

## “python tidak dikenal” atau “python is not recognized”

Penyebab umum: Python belum terpasang atau belum masuk PATH.

Solusi:

1. Tutup CMD.
2. Buka CMD baru.
3. Coba:

```bat
py -3.10 --version
```

4. Jika berhasil, gunakan `py -3.10` untuk membuat venv.
5. Jika gagal, instal ulang Python dan centang **Add Python to PATH**.

## “pip tidak ditemukan”

Jangan memanggil `pip` secara langsung. Gunakan:

```bat
python -m pip --version
python -m pip install -r requirements.txt
```

Jika masih gagal:

```bat
python -m ensurepip --upgrade
python -m pip install --upgrade pip
```

## “No module named streamlit”

Artinya Streamlit tidak terpasang pada Python yang sedang aktif.

1. Aktifkan venv:

```bat
venv\Scripts\activate
```

2. Periksa lokasi Python:

```bat
where python
```

3. Instal dependency:

```bat
python -m pip install -r requirements.txt
```

4. Jalankan:

```bat
python -m streamlit run app.py
```

## “Port 8501 already in use”

Artinya ada Streamlit lain yang masih berjalan.

Pilihan pertama: cari CMD lama dan tekan `Ctrl + C`.

Pilihan kedua: gunakan port lain:

```bat
python -m streamlit run app.py --server.port 8502
```

Lalu buka:

```text
http://localhost:8502
```

## “Error loading model”

Kemungkinan penyebab:

- folder model belum tersedia;
- file weight belum lengkap;
- model belum selesai diunduh;
- RAM tidak cukup;
- versi Python atau dependency tidak sesuai.

Langkah pemeriksaan:

1. Pastikan memakai Python 3.10 atau 3.11.
2. Pastikan venv aktif.
3. Periksa folder `models/indihome`, `models/indibiz`, atau `models/telkomsel`.
4. Jangan mencampur file model antar layanan.
5. Jalankan ulang dashboard.
6. Jika model belum ada, gunakan Mode Demo untuk memeriksa tampilan tanpa inferensi nyata.

## Dashboard tidak terbuka di browser

1. Jangan tutup CMD.
2. Cari `Local URL` pada terminal.
3. Buka browser.
4. Ketik `http://localhost:8501`.
5. Jika gagal, coba port lain:

```bat
python -m streamlit run app.py --server.port 8502
```

6. Pastikan firewall tidak memblokir Python untuk jaringan lokal.

## Layar putih atau blank saat pertama dibuka

1. Tunggu proses pemuatan awal selesai.
2. Tekan `Ctrl + Shift + R` untuk hard refresh.
3. Pastikan CMD tidak menampilkan error fatal.
4. Hentikan Streamlit dengan `Ctrl + C`.
5. Aktifkan kembali venv.
6. Jalankan:

```bat
python -m streamlit run app.py --server.port 8502
```

7. Buka alamat port baru di browser.

## API key Gemini tidak ditemukan

1. Pastikan file bernama `.env`, bukan `.env.txt`.
2. Pastikan `.env` sejajar dengan `app.py`.
3. Pastikan formatnya:

```env
GEMINI_API_KEY=API_KEY_ASLI_ANDA
```

4. Simpan file.
5. Hentikan Streamlit.
6. Jalankan ulang dashboard.

## Instalasi berhenti saat PyTorch

1. Pastikan internet stabil.
2. Jangan menutup CMD.
3. Jalankan kembali:

```bat
python -m pip install -r requirements.txt
```

pip akan melewati paket yang sudah selesai dipasang.

## Smart App Control memblokir file `.bat`

Baseline proyek dapat dijalankan tanpa file `.bat`. Buka CMD pada folder proyek, aktifkan venv, lalu jalankan:

```bat
python -m streamlit run app.py
```

Tidak perlu mematikan Smart App Control.

# Checklist Instalasi

- [ ] Python 3.10 atau 3.11 dapat dipanggil dari terminal.
- [ ] Git tersedia atau ZIP proyek sudah diekstrak.
- [ ] Folder proyek berisi `app.py` dan `requirements.txt`.
- [ ] Folder `venv` sudah dibuat.
- [ ] Terminal menampilkan `(venv)`.
- [ ] `python -m pip install -r requirements.txt` selesai tanpa error akhir.
- [ ] `.env` terisi jika fitur Gemini akan digunakan.
- [ ] `python -m streamlit run app.py` menampilkan Local URL.
- [ ] Halaman login terbuka di browser.
- [ ] Password admin awal sudah diganti sebelum deployment.
