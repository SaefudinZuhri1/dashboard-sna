# Dashboard Analisis Sentimen & SNA — Telkom Group

Dashboard penelitian berbasis Streamlit untuk menganalisis sentimen publik, topik percakapan, jaringan sosial, influencer, dan rekomendasi komunikasi pada layanan digital Telkom Group.

## 📋 Tentang Proyek

Proyek ini merupakan aplikasi web pendukung Tugas Akhir Program Studi S1 Sains Data Universitas Logistik dan Bisnis Internasional (ULBI) Bandung tahun 2026. Dashboard menyatukan hasil penelitian mengenai tiga layanan digital Telkom Group:

- **IndiHome**
- **IndiBiz**
- **Telkomsel**

Data penelitian berasal dari percakapan publik pada:

- **Twitter/X**
- **Instagram**
- **TikTok**

Metode utama yang digunakan adalah:

- **Social Network Analysis (SNA)** untuk membentuk graf interaksi, menghitung metrik jaringan, dan mengidentifikasi akun yang berpotensi menjadi influencer.
- **IndoBERT** untuk mengklasifikasikan sentimen teks menjadi positif, netral, atau negatif.
- **Analisis topik dan WordCloud** untuk membantu membaca kata serta isu yang dominan.
- **Gemini API** untuk menghasilkan rekomendasi dan ide konten pada fitur yang membutuhkannya.

Dashboard tidak melakukan scraping media sosial secara langsung. Aplikasi membaca file hasil pengumpulan dan pengolahan data yang sudah disiapkan sebelumnya. Jika file analitik belum tersedia, dashboard tetap dapat dibuka menggunakan data dummy atau Mode Demo yang diberi penanda jelas.

## 🛠️ Tech Stack

| Teknologi | Fungsi dalam proyek |
|---|---|
| Python 3.10+ | Bahasa pemrograman utama. Untuk kompatibilitas paling aman dengan dependency proyek, gunakan Python 3.10 atau 3.11. |
| Streamlit 1.59.2 | Framework untuk membangun dan menjalankan dashboard web interaktif. |
| streamlit-option-menu | Menyediakan navigasi menu pada sidebar. |
| Pandas | Membaca, membersihkan, memfilter, dan merangkum data tabular. |
| NumPy | Mendukung operasi numerik. |
| Plotly | Membuat grafik interaktif seperti pie chart, bar chart, timeline, heatmap, dan visualisasi statistik. |
| Matplotlib | Digunakan khusus untuk menghasilkan WordCloud dan gambar statis tertentu. |
| WordCloud | Menampilkan kata yang paling sering muncul dalam percakapan. |
| NetworkX | Membentuk graf terarah dan menghitung metrik Social Network Analysis. |
| Pyvis | Menampilkan graf jaringan interaktif pada browser. |
| Transformers | Memuat tokenizer dan model IndoBERT dari Hugging Face. |
| PyTorch | Menjalankan inferensi model IndoBERT. |
| scikit-learn | Mendukung proses pengolahan dan analitik teks. |
| SQLite | Menyimpan akun pengguna, profil, role, dan data autentikasi lokal. |
| bcrypt | Mengamankan password dengan hashing. |
| Pillow | Memproses avatar dan gambar. |
| openpyxl | Membaca dan membuat file Excel `.xlsx`. |
| google-genai | SDK resmi yang digunakan untuk terhubung ke Gemini API. |
| python-dotenv | Membaca API key lokal dari file `.env`. |
| Git dan GitHub | Menyimpan versi kode dan mendistribusikan proyek. |

Versi dependency lengkap dan terkunci tersedia di `requirements.txt`.

## 📁 Struktur Folder

Struktur berikut menggambarkan baseline proyek saat ini dan folder runtime yang digunakan aplikasi.

```text
project/
├── app.py                         # Titik masuk aplikasi, autentikasi, sidebar, dan routing halaman
├── README.md                      # Ringkasan proyek dan panduan cepat
├── requirements.txt               # Daftar library Python dan versinya
├── Procfile                       # Perintah startup untuk platform deployment yang mendukung Procfile
├── UI_UX_LOCK.md                  # Aturan penguncian tampilan dashboard
├── .env                           # API key lokal; rahasia dan tidak boleh diunggah ke GitHub
├── .gitignore                     # Daftar file lokal/rahasia yang diabaikan Git
├── .streamlit/
│   ├── config.toml                # Tema, upload maksimum, browser, dan pengaturan Streamlit
│   ├── secrets.toml.example       # Contoh struktur secrets untuk deployment
│   └── secrets.toml               # Secrets lokal; tidak boleh diunggah ke GitHub
├── auth/
│   ├── auth_utils.py              # Database, hashing password, login, registrasi, dan CRUD pengguna
│   ├── login.py                   # Halaman login
│   ├── register.py                # Halaman registrasi
│   └── profile.py                 # Profil, avatar, edit akun, dan ubah password
├── pages/
│   ├── home.py                    # Beranda dan ringkasan tiga layanan
│   ├── dataset.py                 # Eksplorasi, filter, upload, preview, dan ekspor dataset
│   ├── sentiment.py               # Analisis sentimen dan prediksi manual
│   ├── topic_analysis.py          # Analisis topik, WordCloud, dan frekuensi kata
│   ├── sna.py                     # Social Network Analysis dan identifikasi influencer
│   ├── recommendation.py          # Rekomendasi konten, influencer, dan integrasi Gemini
│   ├── public_content_ai.py       # AI Content Studio yang dapat dibuka dari alur publik terkait
│   ├── admin_panel.py             # Manajemen pengguna, statistik, dan audit sistem
│   ├── about.py                   # Informasi penelitian dan metodologi
│   ├── wordcloud_page.py          # Modul WordCloud kompatibilitas halaman lama
│   └── insight.py                 # Modul insight kompatibilitas halaman lama
├── utils/
│   ├── access_control.py          # Aturan role dan hak akses halaman
│   ├── app_version.py             # Versi aplikasi yang tampil pada login dan sidebar
│   ├── audit_logger.py            # Pencatatan aktivitas pengguna
│   ├── data_loader.py             # Pemuatan data aktual dan fallback dummy
│   ├── preprocessor.py            # Pembersihan dan normalisasi teks
│   ├── chart_builder.py           # Fungsi grafik Plotly yang dapat dipakai ulang
│   ├── topic_classifier.py        # Klasifikasi dan ringkasan topik
│   ├── topic_data_service.py      # Penyedia data topik per layanan
│   ├── gemini_client.py           # Koneksi Gemini API, cache, dan fallback lokal
│   ├── dummy_data.py              # Data simulasi untuk Mode Demo dan fallback
│   ├── export_utils.py            # Ekspor CSV, Excel, dan gambar
│   ├── css_loader.py              # Tema visual yang dikunci
│   └── loading_screen.py          # Custom loading dashboard
├── database/
│   └── users.db                   # Database SQLite lokal; dibuat otomatis jika belum ada
├── assets/                        # Logo, avatar awal, dan aset visual
├── contoh_data/                   # Contoh dataset relevan dan tidak relevan untuk pengujian upload
├── data/                          # Folder runtime untuk file hasil sentimen, topik, dan SNA
├── models/
│   ├── indihome/                  # Model dan tokenizer khusus IndiHome
│   ├── indibiz/                   # Model dan tokenizer khusus IndiBiz
│   └── telkomsel/                 # Model dan tokenizer khusus Telkomsel
└── docs/
    ├── PANDUAN_INSTALASI.md       # Panduan instalasi untuk pengguna pemula
    └── PANDUAN_PENGGUNAAN.md      # Panduan penggunaan seluruh halaman utama
```

> **Catatan baseline:** Arsip proyek dapat tidak menyertakan folder `data/` dan `models/` karena ukurannya besar atau bersifat lokal. Aplikasi tetap dapat dibuka dengan fallback dummy. Baseline `skripsi_v4.18` juga belum menyertakan `run.bat` dan `run.sh`; perintah resmi yang digunakan adalah `streamlit run app.py`.

## 🚀 Cara Menjalankan (Lokal)

### 1. Buka terminal pada folder proyek

Di Windows, buka File Explorer, masuk ke folder yang berisi `app.py`, klik kolom alamat, ketik `cmd`, lalu tekan **Enter**.

### 2. Buat virtual environment

Gunakan Python 3.10 jika tersedia:

```bat
py -3.10 -m venv venv
```

Jika perintah `py -3.10` tidak tersedia tetapi `python --version` menunjukkan Python 3.10 atau 3.11, gunakan:

```bat
python -m venv venv
```

### 3. Aktifkan virtual environment

Windows Command Prompt:

```bat
venv\Scripts\activate
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS atau Linux:

```bash
source venv/bin/activate
```

Virtual environment berhasil aktif jika awal baris terminal menampilkan `(venv)`.

### 4. Perbarui pip

```bat
python -m pip install --upgrade pip
```

### 5. Instal seluruh library

```bat
python -m pip install -r requirements.txt
```

Proses ini dapat memerlukan waktu karena PyTorch dan Transformers berukuran besar.

### 6. Isi Gemini API key bila fitur AI akan digunakan

Buka `.env`, lalu tulis:

```env
GEMINI_API_KEY=API_KEY_ASLI_ANDA
```

Jangan menambahkan spasi di sekitar tanda `=` dan jangan mengunggah `.env` ke GitHub.

### 7. Jalankan dashboard

```bat
streamlit run app.py
```

Jika perintah `streamlit` tidak dikenali, gunakan:

```bat
python -m streamlit run app.py
```

Browser akan membuka alamat lokal, biasanya:

```text
http://localhost:8501
```

Panduan instalasi yang lebih rinci tersedia di [`docs/PANDUAN_INSTALASI.md`](docs/PANDUAN_INSTALASI.md).

## ☁️ Akses Online (Streamlit Community Cloud)

**Alamat dashboard:** `[URL akan diisi setelah deployment]`

Setelah alamat deployment tersedia:

1. Buka browser seperti Google Chrome atau Microsoft Edge.
2. Tempel alamat dashboard pada kolom alamat.
3. Tekan **Enter**.
4. Tunggu sampai halaman login tampil.
5. Masuk menggunakan akun yang sudah diberikan administrator.

Pengguna online tidak perlu menginstal Python atau library di komputernya.

## 📊 Fitur Dashboard

### Beranda

Menampilkan ringkasan data tiga layanan, status sumber data, statistik utama, distribusi sentimen, timeline, dan pintasan menuju analisis berikutnya.

### Dataset

Menyediakan pemilihan layanan, filter platform, sentimen, pencarian komentar, tabel, pagination, ringkasan, ekspor, serta upload file CSV atau Excel untuk analisis awal.

### Analisis Sentimen

Menampilkan distribusi positif, netral, dan negatif, perbandingan antarplatform, confidence model, contoh komentar, WordCloud sentimen, serta prediksi manual apabila model layanan tersedia.

### Analisis Topik

Menampilkan WordCloud, kata dominan, frekuensi topik, filter sentimen/platform, contoh komentar, dan hasil analisis topik per layanan.

### Social Network Analysis

Membentuk graf interaksi akun, menampilkan node dan edge, menghitung metrik jaringan, memperlihatkan graf Pyvis interaktif, dan menyusun tabel influencer berdasarkan posisi jaringan serta indikator jangkauan.

### Rekomendasi

Menghubungkan hasil topik dan influencer menjadi rekomendasi komunikasi, kartu kandidat influencer, matriks kesesuaian, strategi per topik, serta ide konten yang dapat menggunakan Gemini API.

### Profil

Memungkinkan pengguna melihat identitas akun, mengunggah avatar, mengubah data profil, mengganti password, dan melihat statistik penggunaan sesuai hak akses.

### Admin Panel

Tersedia bagi Data Analis. Fitur ini mencakup manajemen pengguna, perubahan role, statistik sistem, status kesiapan data, dan audit aktivitas. Akun utama dengan `user_id=1` dilindungi dari penghapusan.

### Tentang

Menampilkan konteks penelitian, identitas peneliti, metodologi, teknologi, dan informasi akademik.

## 👤 Akun Default

Akun awal dibuat otomatis saat database pertama kali diinisialisasi:

```text
Username : admin
Password : admin123
Role     : Data Analis
```

Akun ini merupakan akun utama dengan `user_id=1` dan memiliki akses penuh. Demi keamanan:

1. Login menggunakan akun tersebut.
2. Buka halaman **Profil**.
3. Pilih bagian **Ubah Password Akun**.
4. Ganti `admin123` dengan password yang kuat sebelum dashboard dipublikasikan.
5. Jangan membagikan password administrator melalui chat, screenshot, atau repository.

## 🔐 Hak Akses Pengguna

| Role | Halaman yang dapat dibuka |
|---|---|
| Manajemen | Beranda dan Rekomendasi |
| Sosmed Officer | Beranda, Social Network Analysis, Rekomendasi, Profil, dan Tentang |
| Data Analis | Seluruh halaman, termasuk Dataset, Analisis Sentimen, Analisis Topik, Profil, dan Admin Panel |

Akun baru yang dibuat melalui halaman registrasi memperoleh role **Manajemen**. Perubahan role dilakukan oleh Data Analis melalui Admin Panel.

## ⚙️ Konfigurasi API Key Gemini

### Lokal menggunakan `.env`

1. Buat atau buka file `.env` pada folder yang sama dengan `app.py`.
2. Isi satu baris berikut:

```env
GEMINI_API_KEY=API_KEY_ASLI_ANDA
```

3. Simpan file.
4. Hentikan Streamlit dengan `Ctrl + C` jika sedang berjalan.
5. Jalankan kembali dashboard.

API key dapat dibuat melalui Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

### Streamlit Community Cloud

1. Buka dashboard aplikasi di Streamlit Community Cloud.
2. Pilih **App settings** atau **Settings**.
3. Buka bagian **Secrets**.
4. Masukkan konfigurasi TOML berikut:

```toml
GEMINI_API_KEY = "API_KEY_ASLI_ANDA"
```

5. Simpan Secrets.
6. Reboot atau restart aplikasi jika diperlukan.

Jangan menyimpan API key asli di `README.md`, source code, notebook, atau commit GitHub.

## 📝 Konteks Penelitian

**Judul Tugas Akhir:**

> Analisis Jaringan dan Sentimen Publik terhadap Layanan Digital PT Telekomunikasi Indonesia untuk Identifikasi Influencer di Media Sosial Menggunakan Social Network Analysis (SNA) dan IndoBERT

**Peneliti:** Aulia Rahmadiva Wardana  
**NPM:** 184220019  
**Pembimbing:** Woro Isti Rahayu, S.T., M.T.  
**Penguji:** Dr. Riharsono Prastyantoro, S.Si., M.T.  
**Program Studi:** S1 Sains Data  
**Institusi:** Universitas Logistik dan Bisnis Internasional, Bandung  
**Tahun:** 2026

## 📚 Dokumentasi Lanjutan

- [Panduan Instalasi](docs/PANDUAN_INSTALASI.md)
- [Panduan Penggunaan](docs/PANDUAN_PENGGUNAAN.md)

## ⚠️ Catatan Interpretasi

Dashboard adalah alat bantu analisis dan presentasi penelitian. Hasil sentimen dapat dipengaruhi konteks, sarkasme, bahasa informal, kualitas data, serta keterbatasan model. Metrik jaringan menjelaskan posisi akun pada jaringan yang diamati, bukan pengaruh universal di luar dataset dan periode penelitian. Jumlah followers menunjukkan potensi jangkauan, bukan jaminan kredibilitas atau dampak nyata.
