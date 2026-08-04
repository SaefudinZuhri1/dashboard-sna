# Panduan Instalasi Dashboard Analisis Sentimen & SNA
## Telkom Group — Skripsi ULBI Bandung 2026

---

Panduan ini menjelaskan cara memasang dan menjalankan **Dashboard Analisis Sentimen & Social Network Analysis (SNA) Layanan Telkom Group** pada komputer pribadi.

Panduan ditulis untuk pengguna yang belum pernah menggunakan Python, Command Prompt, Terminal, Git, atau Streamlit. Ikuti langkah secara berurutan. Jangan melewati langkah yang diberi tanda **⚠️ PENTING**.

Dashboard mencakup analisis layanan:

- IndiHome;
- IndiBiz;
- Telkomsel;
- platform Twitter/X, Instagram, dan TikTok;
- analisis sentimen menggunakan IndoBERT;
- Social Network Analysis menggunakan NetworkX dan Pyvis.

Aplikasi dijalankan secara lokal melalui alamat:

```text
http://localhost:8501
```

Jika port 8501 sedang digunakan aplikasi lain, launcher proyek dapat memakai:

```text
http://localhost:8502
```

### Gambaran proses instalasi

```text
[Install Python]
       |
       v
[Download proyek dari GitHub]
       |
       v
[Buka folder proyek]
       |
       v
[Jalankan run.bat atau run.sh]
       |
       v
[Dependency dipasang otomatis]
       |
       v
[Browser membuka dashboard]
       |
       v
[Login: admin / admin123]
```

---

## Prasyarat Sistem

Sebelum memulai, pastikan komputer memenuhi kebutuhan berikut.

| Komponen | Kebutuhan minimum | Rekomendasi | Keterangan |
|---|---:|---:|---|
| Sistem operasi | Windows 10/11 atau macOS 11+ | Windows 11 atau macOS terbaru yang masih didukung | Linux juga dapat digunakan melalui `run.sh`. |
| RAM | 8 GB | 16 GB | IndoBERT dan PyTorch membutuhkan memori cukup besar. |
| Penyimpanan kosong | 5 GB | 8–10 GB | Dibutuhkan untuk proyek, virtual environment, library, dan cache model. |
| Internet | Wajib saat instalasi pertama | Stabil, tanpa VPN | Dibutuhkan untuk mengunduh Git, library Python, dan model IndoBERT. |
| Browser | Chrome, Edge, Firefox, atau Safari | Versi terbaru | Digunakan untuk membuka dashboard Streamlit. |
| Python | Python 3.10 | Python 3.10.11 64-bit | Launcher Windows proyek dikunci ke Python 3.10. |

> ⚠️ **PENTING UNTUK WINDOWS:** file `run.bat` pada proyek ini secara sengaja hanya menerima **Python 3.10**. Python 3.11, 3.12, atau 3.13 tidak digunakan oleh launcher Windows ini.

> ℹ️ **UNTUK macOS/LINUX:** file `run.sh` dapat mencari Python 3.10, 3.11, atau 3.12, tetapi Python 3.10 tetap menjadi pilihan paling konsisten dengan launcher Windows dan baseline proyek.

### Sebelum melanjutkan

Pastikan Anda mengetahui tempat menyimpan folder proyek. Untuk pemula, lokasi yang paling mudah adalah:

```text
Desktop
```

atau:

```text
Documents
```

Hindari menyimpan proyek terlalu dalam, misalnya:

```text
C:\Users\Nama\Downloads\Folder A\Folder B\Folder C\dashboard-sna
```

Lokasi yang lebih sederhana lebih mudah digunakan, misalnya:

```text
C:\Users\Nama\Desktop\dashboard-sna
```

---

## Langkah 1: Install Python

## Windows — langkah per langkah sangat detail

### A. Download installer Python 3.10

1. Nyalakan komputer dan tunggu sampai halaman Desktop tampil.
2. Buka browser, misalnya Google Chrome, Microsoft Edge, atau Mozilla Firefox.
3. Klik satu kali kolom alamat di bagian paling atas browser.
4. Hapus alamat yang sedang tampil, lalu ketik:

   ```text
   https://www.python.org/downloads/release/python-31011/
   ```

5. Tekan tombol `Enter` pada keyboard.
6. Tunggu halaman **Python 3.10.11** terbuka.
7. Gulir halaman ke bawah sampai menemukan bagian **Files**.
8. Cari baris **Windows installer (64-bit)**.
9. Klik tulisan **Windows installer (64-bit)**.
10. Tunggu proses download selesai.
11. File yang diunduh biasanya bernama:

    ```text
    python-3.10.11-amd64.exe
    ```

12. Jika browser bertanya lokasi penyimpanan, pilih folder **Downloads**, lalu klik **Save** atau **Simpan**.

> ⚠️ Jangan memilih **embeddable package**, **source tarball**, atau installer 32-bit. Gunakan **Windows installer (64-bit)**.

### B. Menjalankan installer Python

1. Tekan tombol `Windows + E` secara bersamaan untuk membuka File Explorer.
2. Pada panel kiri, klik folder **Downloads**.
3. Cari file:

   ```text
   python-3.10.11-amd64.exe
   ```

4. Klik dua kali file tersebut.
5. Jika muncul jendela **User Account Control** yang menanyakan izin perubahan, klik **Yes** atau **Ya**.
6. Jendela installer Python akan terbuka.
7. Lihat bagian paling bawah jendela installer.
8. Cari kotak kecil dengan tulisan serupa:

   ```text
   Add Python 3.10 to PATH
   ```

9. **Centang kotak tersebut.**
10. Pastikan tanda centang terlihat.
11. Klik tombol **Install Now**.
12. Tunggu sampai proses selesai. Proses biasanya membutuhkan beberapa menit.
13. Jangan menutup installer saat progress bar masih berjalan.
14. Jika muncul tulisan **Setup was successful**, instalasi berhasil.
15. Jika tersedia tombol **Disable path length limit**, klik tombol tersebut.
16. Jika muncul permintaan izin, klik **Yes**.
17. Klik **Close** untuk menutup installer.

> ⚠️ **PENTING SEKALI:** apabila `Add Python 3.10 to PATH` tidak dicentang, perintah Python dapat tidak dikenali oleh Command Prompt.

### C. Memverifikasi Python di Windows

1. Tutup semua jendela Command Prompt yang sebelumnya terbuka.
2. Tekan tombol `Windows` pada keyboard.
3. Ketik:

   ```text
   cmd
   ```

4. Klik **Command Prompt**, atau tekan `Enter`.
5. Jendela hitam akan muncul.
6. Ketik perintah berikut persis:

   ```bat
   py -3.10 --version
   ```

7. Tekan `Enter`.
8. Hasil yang benar harus menyerupai:

   ```text
   Python 3.10.11
   ```

9. Lakukan pemeriksaan kedua dengan mengetik:

   ```bat
   python --version
   ```

10. Tekan `Enter`.
11. Hasil ideal juga menunjukkan Python 3.10.x.

### D. Konfirmasi berhasil

Python sudah siap apabila minimal salah satu perintah berikut berhasil:

```bat
py -3.10 --version
```

atau:

```bat
python --version
```

dan hasilnya menampilkan:

```text
Python 3.10.x
```

### E. Jika muncul `python is not recognized`

1. Jangan panik.
2. Coba perintah:

   ```bat
   py -3.10 --version
   ```

3. Jika perintah `py -3.10` berhasil, Python sebenarnya sudah terpasang dan launcher `run.bat` tetap dapat menemukannya.
4. Jika kedua perintah gagal, ulangi instalasi Python.
5. Saat installer dibuka kembali, pastikan **Add Python 3.10 to PATH** dicentang.
6. Setelah instalasi selesai, tutup Command Prompt lama.
7. Buka Command Prompt baru.
8. Ulangi pemeriksaan versi.

---

## macOS — langkah per langkah sangat detail

### A. Mengetahui jenis prosesor Mac

1. Klik ikon Apple `` di pojok kiri atas layar.
2. Klik **About This Mac** atau **Mengenai Mac Ini**.
3. Cari bagian **Chip** atau **Processor**.
4. Catat apakah tertulis:
   - Apple M1, M2, M3, M4, atau generasi Apple Silicon lain; atau
   - Intel.
5. Installer **macOS 64-bit universal2** dapat digunakan untuk Mac Apple Silicon maupun Intel yang didukung.

### B. Download Python 3.10 untuk macOS

1. Buka Safari, Chrome, atau Firefox.
2. Klik kolom alamat browser.
3. Ketik:

   ```text
   https://www.python.org/downloads/release/python-31011/
   ```

4. Tekan `Return` atau `Enter`.
5. Tunggu halaman Python 3.10.11 terbuka.
6. Gulir ke bagian **Files**.
7. Cari tulisan:

   ```text
   macOS 64-bit universal2 installer
   ```

8. Klik tulisan tersebut.
9. Tunggu download selesai.
10. File biasanya masuk ke folder **Downloads** dan memiliki nama serupa:

    ```text
    python-3.10.11-macos11.pkg
    ```

### C. Menjalankan installer di macOS

1. Buka Finder dengan mengklik ikon wajah biru di Dock.
2. Pada panel kiri Finder, klik **Downloads**.
3. Cari file installer Python yang berakhiran `.pkg`.
4. Klik dua kali file tersebut.
5. Jendela installer akan terbuka.
6. Klik **Continue**.
7. Baca informasi instalasi, lalu klik **Continue** lagi.
8. Klik **Agree** untuk menyetujui lisensi.
9. Pilih lokasi instalasi default.
10. Klik **Install**.
11. Masukkan password akun Mac apabila diminta.
12. Klik **Install Software**.
13. Tunggu sampai proses selesai.
14. Jika muncul tulisan instalasi berhasil, klik **Close**.
15. Apabila Finder membuka folder Python di Applications, cari file:

    ```text
    Install Certificates.command
    ```

16. Klik dua kali file tersebut.
17. Terminal dapat terbuka sebentar untuk memasang sertifikat.
18. Tunggu sampai proses selesai, lalu tutup jendela Terminal tersebut.

> ℹ️ Langkah pemasangan sertifikat membantu Python terhubung dengan layanan HTTPS saat mengunduh library atau model.

### D. Memverifikasi Python di macOS

1. Tekan `Command + Space` untuk membuka Spotlight Search.
2. Ketik:

   ```text
   Terminal
   ```

3. Tekan `Return`.
4. Jendela Terminal akan terbuka.
5. Ketik:

   ```bash
   python3.10 --version
   ```

6. Tekan `Return`.
7. Hasil yang benar harus menyerupai:

   ```text
   Python 3.10.11
   ```

8. Periksa lokasi Python dengan mengetik:

   ```bash
   which python3.10
   ```

9. Tekan `Return`.
10. Hasil biasanya menunjukkan lokasi Python, misalnya:

    ```text
    /usr/local/bin/python3.10
    ```

### E. Jika `python3.10: command not found`

1. Tutup Terminal.
2. Buka Terminal baru.
3. Jalankan lagi:

   ```bash
   python3.10 --version
   ```

4. Jika masih gagal, buka Finder.
5. Buka folder **Applications**.
6. Cari folder **Python 3.10**.
7. Pastikan folder tersebut ada.
8. Jika folder tidak ada, instalasi belum selesai dan perlu diulang.
9. Jalankan kembali installer `.pkg` dari folder Downloads.
10. Setelah selesai, restart Mac, lalu lakukan verifikasi ulang.

### F. Konfirmasi berhasil

Python siap apabila Terminal menampilkan:

```text
Python 3.10.x
```

setelah perintah:

```bash
python3.10 --version
```

---

## Langkah 2: Download Proyek dari GitHub

Repository proyek:

```text
https://github.com/SaefudinZuhri1/dashboard-sna
```

Tersedia dua cara. Gunakan **Opsi A** jika ingin mudah mengambil pembaruan dari GitHub. Gunakan **Opsi B** jika hanya ingin menjalankan proyek dengan cara paling sederhana.

---

## Opsi A — Dengan Git

### Kapan memilih Opsi A?

Pilih Git apabila Anda ingin:

- mengambil versi terbaru menggunakan `git pull`;
- mengirim perubahan menggunakan `git push`;
- mempertahankan riwayat perubahan proyek;
- menyinkronkan komputer dengan GitHub.

### A. Install Git di Windows

1. Buka browser.
2. Ketik alamat:

   ```text
   https://git-scm.com/download/win
   ```

3. Tekan `Enter`.
4. Download Git for Windows biasanya dimulai otomatis.
5. Tunggu file installer selesai diunduh.
6. Buka folder **Downloads**.
7. Klik dua kali installer Git.
8. Jika muncul User Account Control, klik **Yes**.
9. Pada setiap halaman installer, gunakan pilihan default.
10. Klik **Next** berulang kali sampai menemukan tombol **Install**.
11. Klik **Install**.
12. Tunggu proses selesai.
13. Klik **Finish**.
14. Tutup semua Command Prompt lama.
15. Buka Command Prompt baru.
16. Ketik:

    ```bat
    git --version
    ```

17. Tekan `Enter`.
18. Jika muncul `git version ...`, Git berhasil dipasang.

### B. Install Git di macOS

Cara paling sederhana:

1. Buka Terminal.
2. Ketik:

   ```bash
   git --version
   ```

3. Tekan `Return`.
4. Jika Git belum tersedia, macOS dapat menampilkan popup untuk memasang **Command Line Developer Tools**.
5. Klik **Install**.
6. Klik **Agree** apabila diminta menyetujui lisensi.
7. Tunggu instalasi selesai.
8. Tutup Terminal lama.
9. Buka Terminal baru.
10. Jalankan lagi:

    ```bash
    git --version
    ```

11. Jika versi Git tampil, instalasi berhasil.

Alternatifnya, Git dapat diunduh melalui:

```text
https://git-scm.com/download/mac
```

### C. Clone proyek di Windows

1. Tekan `Windows + E` untuk membuka File Explorer.
2. Pilih lokasi penyimpanan, misalnya **Desktop**.
3. Klik satu kali kolom alamat di bagian atas File Explorer.
4. Ketik:

   ```text
   cmd
   ```

5. Tekan `Enter`.
6. Command Prompt akan terbuka langsung pada lokasi tersebut.
7. Ketik:

   ```bat
   git clone https://github.com/SaefudinZuhri1/dashboard-sna.git
   ```

8. Tekan `Enter`.
9. Tunggu sampai proses selesai.
10. Jangan tutup jendela ketika masih muncul progress download.
11. Jika berhasil, akan terbentuk folder:

    ```text
    dashboard-sna
    ```

12. Masuk ke folder proyek dengan perintah:

    ```bat
    cd dashboard-sna
    ```

13. Tekan `Enter`.
14. Tampilkan isi folder dengan:

    ```bat
    dir
    ```

15. Pastikan terlihat minimal file berikut:

    ```text
    app.py
    requirements.txt
    run.bat
    run.sh
    UI_UX_LOCK.md
    docs
    auth
    pages
    utils
    ```

### D. Clone proyek di macOS

1. Buka Terminal.
2. Untuk menyimpan proyek di Desktop, ketik:

   ```bash
   cd ~/Desktop
   ```

3. Tekan `Return`.
4. Ketik:

   ```bash
   git clone https://github.com/SaefudinZuhri1/dashboard-sna.git
   ```

5. Tekan `Return`.
6. Tunggu proses clone selesai.
7. Masuk ke folder proyek:

   ```bash
   cd dashboard-sna
   ```

8. Tampilkan isi folder:

   ```bash
   ls
   ```

9. Pastikan file `app.py`, `requirements.txt`, dan `run.sh` terlihat.

### E. Konfirmasi clone berhasil

Clone berhasil apabila:

- tidak ada pesan yang diawali `fatal:`;
- folder `dashboard-sna` terbentuk;
- file `app.py` berada di dalam folder tersebut.

---

## Opsi B — Download ZIP

Opsi ZIP lebih mudah karena tidak membutuhkan Git.

### A. Download ZIP di Windows atau macOS

1. Buka browser.
2. Masuk ke:

   ```text
   https://github.com/SaefudinZuhri1/dashboard-sna
   ```

3. Tunggu halaman repository terbuka.
4. Cari tombol hijau atau tombol bertulis **Code** di bagian atas daftar file.
5. Klik tombol **Code**.
6. Klik **Download ZIP**.
7. Tunggu download selesai.
8. File biasanya bernama:

   ```text
   dashboard-sna-main.zip
   ```

### B. Extract ZIP di Windows

1. Tekan `Windows + E`.
2. Buka folder **Downloads**.
3. Cari file `dashboard-sna-main.zip`.
4. Klik kanan file tersebut.
5. Klik **Extract All...** atau **Ekstrak Semua...**.
6. Pilih lokasi yang mudah, misalnya Desktop.
7. Centang pilihan untuk menampilkan file setelah proses selesai apabila tersedia.
8. Klik **Extract**.
9. Tunggu proses selesai.
10. Buka folder hasil extract.
11. Sering kali terdapat folder luar dan folder dalam dengan nama mirip.
12. Pastikan Anda membuka folder yang langsung berisi `app.py`.

Contoh lokasi benar:

```text
Desktop\dashboard-sna-main\app.py
```

Contoh lokasi yang masih satu tingkat terlalu luar:

```text
Desktop\dashboard-sna-main\dashboard-sna-main\app.py
```

Jika ada folder ganda, gunakan folder paling dalam yang berisi `app.py`.

### C. Extract ZIP di macOS

1. Buka Finder.
2. Klik folder **Downloads**.
3. Cari `dashboard-sna-main.zip`.
4. Klik dua kali file ZIP tersebut.
5. macOS akan membuat folder hasil extract secara otomatis.
6. Pindahkan folder hasil extract ke Desktop apabila lebih mudah.
7. Buka folder tersebut.
8. Pastikan file `app.py` terlihat.

### D. Kekurangan Opsi ZIP

Folder hasil Download ZIP tidak memiliki konfigurasi Git lokal. Artinya:

- Anda tidak dapat langsung menjalankan `git pull`;
- perubahan tidak dapat langsung dipush sebelum Git diinisialisasi;
- untuk mengambil versi terbaru, biasanya perlu download ZIP ulang.

Untuk penggunaan jangka panjang, Opsi A dengan Git lebih direkomendasikan.

---

## Langkah 3: Jalankan Aplikasi

Sebelum menjalankan aplikasi, buka folder proyek dan pastikan file berikut berada pada tingkat folder yang sama:

```text
app.py
requirements.txt
run.bat
run.sh
```

---

## Windows — Cara Termudah dengan Double Click `run.bat`

File `run.bat` adalah launcher otomatis untuk Windows. Launcher akan:

1. mencari Python 3.10;
2. membuat folder virtual environment bernama `venv` jika belum ada;
3. memasang library dari `requirements.txt` jika diperlukan;
4. memeriksa apakah port 8501 tersedia;
5. menggunakan port 8502 jika port 8501 sedang dipakai;
6. menjalankan Streamlit;
7. membuka browser secara otomatis.

### Langkah menjalankan

1. Tekan `Windows + E` untuk membuka File Explorer.
2. Masuk ke folder proyek yang berisi `app.py`.
3. Cari file bernama:

   ```text
   run.bat
   ```

4. Jika ekstensi file disembunyikan, file dapat terlihat hanya sebagai `run` dengan tipe **Windows Batch File**.
5. Klik dua kali `run.bat`.
6. Jendela Command Prompt berwarna hitam akan terbuka.
7. Jangan langsung menutup jendela tersebut.
8. Launcher akan menampilkan pemeriksaan Python.
9. Hasil yang benar memuat tulisan serupa:

   ```text
   [OK] Python proyek ditemukan: Python 3.10.x
   ```

10. Jika folder `venv` belum ada, launcher akan membuatnya.
11. Jika dependency belum tersedia, launcher akan mengunduh dan memasangnya.
12. Proses pertama dapat berlangsung cukup lama karena PyTorch dan library NLP berukuran besar.
13. Jangan menekan tombol apa pun selama instalasi masih berjalan, kecuali muncul pertanyaan yang jelas.
14. Setelah selesai, terminal akan menampilkan alamat dashboard.
15. Browser seharusnya terbuka otomatis.
16. Alamat yang digunakan adalah salah satu dari:

    ```text
    http://localhost:8501
    ```

    atau:

    ```text
    http://localhost:8502
    ```

17. Jika browser tidak terbuka, buka Chrome atau Edge secara manual.
18. Ketik alamat yang ditampilkan terminal.
19. Tekan `Enter`.

### Jika muncul `Windows protected your PC`

1. Jangan langsung menutup popup.
2. Klik **More info** atau **Info selengkapnya**.
3. Pastikan nama file yang ditampilkan adalah `run.bat` dari proyek Anda.
4. Klik **Run anyway** atau **Tetap jalankan**.
5. Jika tombol tersebut tidak tersedia, klik kanan `run.bat`.
6. Pilih **Properties**.
7. Jika ada kotak **Unblock**, centang kotak tersebut.
8. Klik **Apply**.
9. Klik **OK**.
10. Jalankan kembali `run.bat`.

### Berapa lama proses pertama?

Perkiraan bergantung pada kecepatan internet dan komputer:

| Tahap | Perkiraan umum |
|---|---:|
| Membuat `venv` | 1–3 menit |
| Memasang library | 5–20 menit |
| Membuka aplikasi | 1–5 menit |
| Download model saat fitur sentimen pertama digunakan | Dapat membutuhkan beberapa menit |

> ⚠️ Waktu di atas bukan batas pasti. Komputer dengan internet lambat dapat membutuhkan waktu lebih lama.

### Ciri launcher berhasil

Terminal menampilkan informasi serupa:

```text
[INFO] Memulai dashboard...
[INFO] Alamat dashboard: http://localhost:8501
[INFO] Browser akan dibuka otomatis.
```

Browser menampilkan halaman login dashboard.

---

## Windows — Cara Manual melalui Command Prompt

Gunakan cara manual apabila `run.bat` bermasalah atau Anda perlu melihat proses satu per satu.

### A. Membuka Command Prompt pada folder yang benar

1. Buka folder proyek di File Explorer.
2. Pastikan file `app.py` terlihat.
3. Klik kolom alamat di bagian atas File Explorer.
4. Ketik:

   ```text
   cmd
   ```

5. Tekan `Enter`.
6. Command Prompt akan terbuka pada folder proyek.
7. Ketik:

   ```bat
   dir
   ```

8. Tekan `Enter`.
9. Pastikan `app.py` dan `requirements.txt` terlihat.

### B. Membuat virtual environment

1. Ketik:

   ```bat
   py -3.10 -m venv venv
   ```

2. Tekan `Enter`.
3. Tunggu sampai kursor kembali muncul.
4. Aktifkan virtual environment:

   ```bat
   venv\Scripts\activate
   ```

5. Tekan `Enter`.
6. Jika berhasil, bagian awal baris Command Prompt akan memuat:

   ```text
   (venv)
   ```

### C. Memasang dependency

1. Perbarui pip:

   ```bat
   python -m pip install --upgrade pip
   ```

2. Tekan `Enter` dan tunggu selesai.
3. Pasang semua kebutuhan proyek:

   ```bat
   python -m pip install -r requirements.txt
   ```

4. Tekan `Enter`.
5. Tunggu sampai proses selesai.
6. Proses dapat mengunduh file berukuran besar.
7. Jangan tutup Command Prompt saat instalasi berjalan.
8. Instalasi berhasil apabila tidak berakhir dengan pesan `ERROR` atau `FAILED`.

Perintah ringkas yang memiliki tujuan sama adalah:

```bat
pip install -r requirements.txt
```

Namun bentuk `python -m pip` lebih aman karena memastikan pip yang digunakan berasal dari Python di dalam `venv`.

### D. Menjalankan Streamlit

1. Pastikan tulisan `(venv)` masih terlihat di awal baris.
2. Ketik:

   ```bat
   python -m streamlit run app.py
   ```

3. Tekan `Enter`.
4. Tunggu sampai muncul:

   ```text
   Local URL: http://localhost:8501
   ```

5. Jika browser tidak terbuka, buka browser manual.
6. Ketik:

   ```text
   http://localhost:8501
   ```

7. Tekan `Enter`.

Perintah alternatif:

```bat
streamlit run app.py
```

### E. Menjalankan pada port 8502

Jika port 8501 sedang digunakan:

```bat
python -m streamlit run app.py --server.port 8502
```

Kemudian buka:

```text
http://localhost:8502
```

---

## macOS / Linux — Menjalankan dengan `run.sh`

File `run.sh` adalah launcher otomatis untuk macOS dan Linux. Launcher akan mencari Python yang kompatibel, membuat `venv`, memasang dependency, memilih port, dan membuka browser jika sistem mendukung.

### A. Membuka Terminal

#### macOS

1. Tekan `Command + Space`.
2. Ketik `Terminal`.
3. Tekan `Return`.

#### Linux

1. Tekan `Ctrl + Alt + T`.
2. Terminal akan terbuka.

### B. Masuk ke folder proyek

Contoh apabila proyek berada di Desktop:

```bash
cd ~/Desktop/dashboard-sna
```

Jika nama folder hasil ZIP adalah `dashboard-sna-main`, gunakan:

```bash
cd ~/Desktop/dashboard-sna-main
```

Untuk memastikan lokasi benar, jalankan:

```bash
ls
```

Pastikan `app.py`, `requirements.txt`, dan `run.sh` terlihat.

### C. Memberikan izin eksekusi

Izin ini biasanya hanya perlu diberikan satu kali:

```bash
chmod +x run.sh
```

Tekan `Return`.

### D. Menjalankan launcher

Ketik:

```bash
./run.sh
```

Tekan `Return`.

Launcher akan:

1. memeriksa Python;
2. membuat folder `venv` jika belum ada;
3. memasang dependency;
4. memilih port 8501 atau 8502;
5. membuka browser apabila memungkinkan;
6. menjalankan aplikasi.

### E. Jika muncul `permission denied`

Jalankan kembali:

```bash
chmod +x run.sh
```

Lalu:

```bash
./run.sh
```

### F. Cara manual di macOS/Linux

Jika `run.sh` tidak dapat digunakan, jalankan perintah berikut satu per satu:

```bash
python3.10 -m venv venv
```

```bash
source venv/bin/activate
```

```bash
python -m pip install --upgrade pip
```

```bash
python -m pip install -r requirements.txt
```

```bash
python -m streamlit run app.py
```

Jika `python3.10` tidak ditemukan tetapi `python3 --version` menunjukkan Python 3.10–3.12, perintah pertama dapat diganti dengan:

```bash
python3 -m venv venv
```

### G. Konfirmasi berhasil

Dashboard berhasil berjalan apabila:

- Terminal tetap terbuka tanpa error fatal;
- alamat `http://localhost:8501` atau `http://localhost:8502` tampil;
- browser menampilkan halaman login.

---

## Konfigurasi API Gemini — opsional

Aplikasi memiliki fitur yang dapat menggunakan Google Gemini. Untuk membuka dashboard dan menggunakan fitur dasar, API key tidak selalu wajib karena proyek memiliki penanganan error atau fallback. Namun fitur AI yang benar-benar memanggil Gemini memerlukan API key.

### Windows

1. Buka folder proyek.
2. Cari file `.env.template`.
3. Salin file tersebut.
4. Tempel salinannya pada folder yang sama.
5. Ubah nama salinan menjadi:

   ```text
   .env
   ```

6. Buka `.env` menggunakan Notepad atau Visual Studio Code.
7. Isi API key sesuai nama variabel yang sudah disediakan di template.
8. Simpan dengan `Ctrl + S`.
9. Jangan membagikan file `.env` kepada orang lain.
10. Jangan upload `.env` ke GitHub.

### macOS

1. Buka Terminal pada folder proyek.
2. Salin template:

   ```bash
   cp .env.template .env
   ```

3. Buka `.env` menggunakan editor teks.
4. Isi API key sesuai template.
5. Simpan file.
6. Jangan commit `.env` ke GitHub.

> ⚠️ Jangan pernah menulis API key langsung di `app.py`, file halaman, README, atau screenshot publik.

---

## Langkah 4: Login ke Dashboard

1. Pastikan Command Prompt atau Terminal yang menjalankan Streamlit masih terbuka.
2. Buka browser.
3. Ketik salah satu alamat berikut sesuai yang ditampilkan terminal:

   ```text
   http://localhost:8501
   ```

   atau:

   ```text
   http://localhost:8502
   ```

4. Tekan `Enter`.
5. Tunggu halaman login muncul.
6. Pada kolom **Username**, ketik:

   ```text
   admin
   ```

7. Pada kolom **Password**, ketik:

   ```text
   admin123
   ```

8. Periksa kembali agar tidak ada spasi tambahan.
9. Klik tombol **Login** atau **Masuk** sesuai teks yang tampil pada versi proyek.
10. Tunggu proses autentikasi.
11. Jika berhasil, halaman utama dashboard akan terbuka.

### Konfirmasi login berhasil

Login dinyatakan berhasil apabila:

- halaman login tidak lagi tampil;
- sidebar dashboard muncul;
- nama atau profil akun tampil;
- menu sesuai role **Data Analis** dapat dibuka.

> ⚠️ Password `admin123` adalah password awal. Ganti password setelah instalasi, terutama sebelum dashboard dipublikasikan atau digunakan banyak orang.

### Jika akun admin tidak dapat digunakan

1. Hentikan dashboard dengan `Ctrl + C`.
2. Pastikan Anda berada di folder proyek.
3. Aktifkan `venv`.
4. Windows:

   ```bat
   venv\Scripts\activate
   ```

5. macOS/Linux:

   ```bash
   source venv/bin/activate
   ```

6. Inisialisasi database:

   ```bash
   python -c "from auth.auth_utils import init_db; init_db(); print('Database siap')"
   ```

7. Pastikan muncul:

   ```text
   Database siap
   ```

8. Jalankan dashboard kembali.
9. Coba login dengan `admin` dan `admin123`.

---

## Pemeriksaan Awal Setelah Login

Setelah login pertama, lakukan pemeriksaan berikut:

1. Buka halaman **Beranda**.
2. Pastikan card dan grafik tampil tanpa area putih kosong yang tidak semestinya.
3. Buka halaman **Dataset**.
4. Pastikan data atau fallback dummy dapat dimuat.
5. Buka halaman **Analisis Sentimen**.
6. Tunggu jika model sedang dimuat untuk pertama kali.
7. Buka halaman **Analisis Topik**.
8. Periksa layanan IndiHome, IndiBiz, dan Telkomsel.
9. Buka halaman **SNA**.
10. Pastikan grafik jaringan dapat tampil.
11. Buka halaman **Rekomendasi**.
12. Pastikan halaman tidak berhenti pada loading tanpa akhir.
13. Buka halaman **Tentang** atau halaman informasi proyek.
14. Pastikan tidak ada error merah yang tidak dipahami.
15. Jangan menutup terminal selama pengujian.

---

## Troubleshooting — Solusi Error Umum

Bagian ini menjelaskan arti error dan langkah penyelesaiannya.

---

### ❌ Error: `python is not recognized as an internal or external command`

**Artinya:** Windows tidak menemukan perintah Python melalui PATH.

**Solusi:**

1. Tutup Command Prompt.
2. Buka Command Prompt baru.
3. Coba:

   ```bat
   py -3.10 --version
   ```

4. Jika berhasil, gunakan `py -3.10` untuk membuat `venv`.
5. Jika gagal, ulangi instalasi Python 3.10.11.
6. Saat installer dibuka, centang **Add Python 3.10 to PATH**.
7. Selesaikan instalasi.
8. Restart komputer jika perlu.
9. Buka Command Prompt baru.
10. Jalankan lagi:

    ```bat
    py -3.10 --version
    ```

---

### ❌ Error: `[GAGAL] Python 3.10 tidak ditemukan di komputer ini`

**Artinya:** `run.bat` tidak menemukan Python 3.10. Launcher Windows proyek memang dikunci ke versi tersebut.

**Solusi:**

1. Jangan mengganti isi `run.bat`.
2. Install Python 3.10.11 64-bit.
3. Pastikan Python Launcher ikut terpasang.
4. Buka Command Prompt baru.
5. Jalankan:

   ```bat
   py -3.10 --version
   ```

6. Jika muncul Python 3.10.x, buka folder proyek.
7. Jalankan kembali `run.bat`.

---

### ❌ Error: `Venv lama bukan dibuat dengan Python 3.10`

**Artinya:** folder `venv` dibuat menggunakan versi Python lain.

**Solusi aman tanpa menghapus langsung:**

1. Tutup dashboard.
2. Tutup semua Command Prompt yang memakai proyek.
3. Buka folder proyek.
4. Cari folder `venv`.
5. Klik kanan folder tersebut.
6. Klik **Rename**.
7. Ubah nama menjadi:

   ```text
   venv_backup
   ```

8. Tekan `Enter`.
9. Jalankan kembali `run.bat`.
10. Launcher akan membuat `venv` baru dengan Python 3.10.
11. Setelah dashboard dipastikan normal, folder `venv_backup` boleh dihapus untuk menghemat ruang.

---

### ❌ Error: `Port 8501 already in use`

**Artinya:** port 8501 sedang dipakai dashboard lain atau proses lain.

**Solusi:**

1. Coba buka:

   ```text
   http://localhost:8501
   ```

2. Dashboard mungkin sebenarnya sudah berjalan.
3. Jika menggunakan `run.bat` atau `run.sh`, periksa terminal karena launcher dapat otomatis memilih port 8502.
4. Coba buka:

   ```text
   http://localhost:8502
   ```

5. Untuk menjalankan manual pada port 8502:

   ```bat
   python -m streamlit run app.py --server.port 8502
   ```

6. Jika ingin menghentikan proses lama, tutup terminal lama atau tekan `Ctrl + C` pada terminal tersebut.

---

### ❌ Error: `ModuleNotFoundError: No module named 'streamlit'`

**Artinya:** library Streamlit belum terpasang pada Python yang sedang digunakan.

**Solusi Windows:**

1. Buka Command Prompt pada folder proyek.
2. Aktifkan `venv`:

   ```bat
   venv\Scripts\activate
   ```

3. Pastikan `(venv)` tampil.
4. Jalankan:

   ```bat
   python -m pip install -r requirements.txt
   ```

5. Tunggu selesai.
6. Jalankan:

   ```bat
   python -m streamlit run app.py
   ```

**Solusi macOS/Linux:**

```bash
source venv/bin/activate
```

```bash
python -m pip install -r requirements.txt
```

```bash
python -m streamlit run app.py
```

---

### ❌ Error: instalasi `torch` atau PyTorch gagal

**Artinya:** PyTorch tidak berhasil diunduh atau versi Python tidak cocok.

**Solusi:**

1. Pastikan menggunakan Python 3.10 64-bit.
2. Pastikan internet stabil.
3. Matikan VPN sementara.
4. Aktifkan `venv`.
5. Perbarui pip:

   ```bat
   python -m pip install --upgrade pip
   ```

6. Jalankan kembali:

   ```bat
   python -m pip install -r requirements.txt
   ```

7. Jangan memasang versi PyTorch lain secara acak karena `requirements.txt` sudah menentukan versi CPU yang digunakan proyek.
8. Jika masih gagal, salin bagian error mulai dari tulisan `ERROR` atau `FAILED` untuk proses debug.

---

### ❌ Error: model IndoBERT gagal download atau `Connection Error`

**Artinya:** komputer gagal mengambil model dari Hugging Face, koneksi terputus, atau cache belum lengkap.

**Solusi:**

1. Pastikan internet aktif.
2. Coba membuka situs lain untuk memeriksa koneksi.
3. Matikan VPN atau proxy sementara.
4. Jangan gunakan jaringan kantor/kampus yang memblokir Hugging Face.
5. Aktifkan `venv`.
6. Jalankan perintah berikut pada Command Prompt atau Terminal:

   ```bash
   python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; nama='mdhugol/indonesia-bert-sentiment-classification'; AutoTokenizer.from_pretrained(nama); AutoModelForSequenceClassification.from_pretrained(nama); print('Model IndoBERT berhasil disiapkan')"
   ```

7. Tunggu sampai selesai.
8. Jika muncul `Model IndoBERT berhasil disiapkan`, jalankan dashboard kembali.
9. Jika download terputus, ulangi perintah setelah koneksi stabil.

---

### ❌ Error: `FileNotFoundError: database/users.db`

**Artinya:** database belum tersedia, folder tidak dapat ditulis, atau aplikasi dijalankan dari lokasi yang salah.

**Catatan:** kode proyek dapat membuat folder database dan seed admin secara otomatis saat startup.

**Solusi:**

1. Pastikan Command Prompt berada di folder yang berisi `app.py`.
2. Periksa dengan:

   ```bat
   dir
   ```

3. Pastikan folder `auth` terlihat.
4. Aktifkan `venv`.
5. Jalankan:

   ```bash
   python -c "from auth.auth_utils import init_db; init_db(); print('Database siap')"
   ```

6. Periksa folder:

   ```text
   database
   ```

7. Pastikan file `users.db` terbentuk.
8. Jalankan dashboard kembali.

---

### ❌ Error: `Permission denied` saat menjalankan `run.sh`

**Artinya:** macOS/Linux belum memberikan izin eksekusi pada file.

**Solusi:**

1. Buka Terminal pada folder proyek.
2. Jalankan:

   ```bash
   chmod +x run.sh
   ```

3. Tekan `Return`.
4. Jalankan:

   ```bash
   ./run.sh
   ```

---

### ❌ Error: `No such file or directory` untuk `app.py` atau `requirements.txt`

**Artinya:** terminal berada pada folder yang salah.

**Solusi Windows:**

1. Buka folder yang benar di File Explorer.
2. Pastikan `app.py` terlihat.
3. Klik address bar.
4. Ketik `cmd`.
5. Tekan `Enter`.
6. Jalankan kembali perintah instalasi.

**Solusi macOS:**

1. Buka Finder.
2. Temukan folder yang berisi `app.py`.
3. Di Terminal, ketik `cd ` dengan satu spasi setelah `cd`.
4. Tarik folder proyek dari Finder ke Terminal.
5. Tekan `Return`.
6. Jalankan:

   ```bash
   ls
   ```

7. Pastikan `app.py` terlihat.

---

### ❌ Dashboard sangat lambat saat pertama dibuka

**Artinya:** library, data, model, atau cache sedang dipersiapkan.

**Solusi:**

1. Ini dapat menjadi kondisi normal pada penggunaan pertama.
2. Jangan menutup terminal.
3. Perhatikan apakah masih ada aktivitas download.
4. Tunggu sampai proses selesai.
5. Tutup aplikasi lain yang berat seperti game, editor video, atau banyak tab browser.
6. Pastikan RAM minimal 8 GB.
7. Pastikan ruang penyimpanan masih cukup.
8. Penggunaan berikutnya biasanya lebih cepat karena dependency dan model sudah tersimpan.

---

### ❌ Browser menampilkan `This site can't be reached`

**Artinya:** Streamlit belum berjalan, alamat salah, atau terminal sudah ditutup.

**Solusi:**

1. Periksa terminal.
2. Pastikan terminal belum ditutup.
3. Cari tulisan `Local URL` atau `Alamat dashboard`.
4. Salin alamat tersebut.
5. Tempel ke browser.
6. Coba port 8501 dan 8502.
7. Jika terminal sudah berhenti, jalankan kembali `run.bat`, `run.sh`, atau `python -m streamlit run app.py`.

---

### ❌ Instalasi berhenti dengan `Read timed out`, `Connection reset`, atau error jaringan

**Artinya:** download dependency terputus.

**Solusi:**

1. Pastikan koneksi stabil.
2. Matikan VPN sementara.
3. Jangan hapus folder `venv` terlebih dahulu.
4. Jalankan `run.bat` kembali.
5. Launcher akan memeriksa dependency dan mencoba memasang yang belum lengkap.
6. Untuk cara manual, aktifkan `venv`, lalu jalankan ulang:

   ```bat
   python -m pip install -r requirements.txt
   ```

---

### ❌ Login admin gagal meskipun username dan password benar

**Artinya:** database berbeda, password sudah pernah diubah, atau file database bermasalah.

**Solusi:**

1. Pastikan username ditulis huruf kecil:

   ```text
   admin
   ```

2. Pastikan password tanpa spasi:

   ```text
   admin123
   ```

3. Jika proyek pernah dipakai sebelumnya, password mungkin sudah diubah.
4. Jangan langsung menghapus database karena data akun lain dapat hilang.
5. Buat backup file `database/users.db` terlebih dahulu.
6. Hubungi pengelola proyek untuk reset password secara aman.
7. Untuk instalasi baru yang benar-benar belum memiliki data penting, database dapat diinisialisasi ulang setelah file lama dibackup.

---

### ❌ Fitur Gemini tidak bekerja

**Artinya:** API key belum diisi, tidak valid, kuota habis, atau internet bermasalah.

**Solusi:**

1. Pastikan file `.env` ada pada folder yang sama dengan `app.py`.
2. Pastikan nama variabel mengikuti `.env.template`.
3. Pastikan tidak ada tanda kutip atau spasi yang tidak diperlukan.
4. Simpan file.
5. Hentikan dashboard.
6. Jalankan kembali dashboard agar `.env` dibaca ulang.
7. Jangan tampilkan API key di screenshot atau pesan publik.

---

## Cara Menghentikan Dashboard

### Windows

1. Cari jendela Command Prompt yang menjalankan dashboard.
2. Klik jendela tersebut agar aktif.
3. Tekan `Ctrl + C`.
4. Tunggu server berhenti.
5. Jika launcher menampilkan pilihan:

   ```text
   [R] Jalankan dashboard lagi
   [C] Tutup launcher
   ```

6. Tekan `C` untuk menutup launcher.
7. Jika menggunakan cara manual dan muncul pertanyaan `Terminate batch job (Y/N)?`, ketik `Y`, lalu tekan `Enter`.

### macOS/Linux

1. Klik jendela Terminal yang menjalankan dashboard.
2. Tekan `Control + C`.
3. Tunggu kursor Terminal kembali muncul.
4. Tutup Terminal jika tidak digunakan lagi.

### Konfirmasi dashboard sudah berhenti

1. Kembali ke browser.
2. Refresh halaman dashboard.
3. Jika browser tidak lagi dapat terhubung, server sudah berhenti.

---

## Menjalankan Dashboard Kembali

### Windows

1. Buka folder proyek.
2. Klik dua kali `run.bat`.
3. Launcher akan memakai ulang `venv` yang sudah ada.
4. Dependency tidak dipasang ulang jika sudah lengkap dan `requirements.txt` tidak berubah.

### macOS/Linux

1. Buka Terminal.
2. Masuk ke folder proyek.
3. Jalankan:

   ```bash
   ./run.sh
   ```

---

## Uninstall / Hapus Bersih

Lakukan bagian ini hanya jika benar-benar ingin menghapus aplikasi dari komputer.

### A. Hapus folder proyek

#### Windows

1. Hentikan dashboard.
2. Tutup Command Prompt, Cursor, Visual Studio Code, dan File Explorer yang sedang membuka file proyek.
3. Buka lokasi folder proyek.
4. Klik kanan folder `dashboard-sna`.
5. Klik **Delete**.
6. Buka Recycle Bin.
7. Hapus permanen hanya jika yakin tidak memerlukan backup.

#### macOS

1. Hentikan dashboard.
2. Buka Finder.
3. Cari folder proyek.
4. Klik kanan folder.
5. Klik **Move to Bin**.
6. Kosongkan Bin hanya jika yakin.

### B. Hapus cache Hugging Face

Cache menyimpan model yang pernah diunduh.

#### Windows

Lokasi umum:

```text
C:\Users\NAMA_PENGGUNA\.cache\huggingface
```

Langkah:

1. Tekan `Windows + R`.
2. Ketik:

   ```text
   %USERPROFILE%\.cache
   ```

3. Tekan `Enter`.
4. Cari folder `huggingface`.
5. Klik kanan.
6. Klik **Delete**.

Jika folder tidak ada, tidak ada cache yang perlu dihapus pada lokasi tersebut.

#### macOS/Linux

Lokasi umum:

```text
~/.cache/huggingface
```

Untuk menghapus melalui Terminal:

```bash
rm -rf ~/.cache/huggingface
```

> ⚠️ Perintah `rm -rf` menghapus tanpa Recycle Bin. Pastikan path diketik persis.

### C. Uninstall Python — opsional

Python tidak perlu dihapus hanya karena proyek dihapus. Hapus Python hanya jika tidak digunakan aplikasi lain.

#### Windows

1. Tekan tombol Windows.
2. Ketik **Add or remove programs**.
3. Buka menu tersebut.
4. Cari **Python 3.10.11**.
5. Klik item Python.
6. Klik **Uninstall**.
7. Ikuti instruksi sampai selesai.

#### macOS

Untuk instalasi dari python.org, penghapusan manual dapat memengaruhi symlink dan aplikasi lain. Pengguna pemula disarankan tidak menghapus Python tanpa bantuan orang yang memahami macOS.

### D. Hapus Git — opsional

Git tidak perlu dihapus karena kecil dan berguna untuk pembaruan proyek. Jika ingin menghapusnya di Windows:

1. Buka **Add or remove programs**.
2. Cari **Git**.
3. Klik **Uninstall**.

---

# Panduan Pengecekan Manual Setelah File Selesai Dibuat

Bagian berikut digunakan untuk memastikan file dokumentasi benar-benar berada di lokasi yang tepat dan isinya lengkap.

---

## BAGIAN 1 — Cara Membuat File `docs/PANDUAN_INSTALASI.md`

### A. Memeriksa apakah folder `docs` sudah ada

1. Buka File Explorer dengan `Windows + E`.
2. Masuk ke folder proyek.
3. Pastikan file `app.py` terlihat.
4. Cari folder bernama:

   ```text
   docs
   ```

5. Jika folder `docs` terlihat, klik dua kali untuk membukanya.
6. Jika tidak terlihat, ikuti bagian membuat folder di bawah.

### B. Membuat folder `docs` di Windows jika belum ada

1. Pastikan File Explorer berada di folder proyek, yaitu folder yang berisi `app.py`.
2. Klik kanan area kosong di dalam folder.
3. Pilih **New** atau **Baru**.
4. Pilih **Folder**.
5. Ketik:

   ```text
   docs
   ```

6. Tekan `Enter`.
7. Pastikan folder baru bernama tepat `docs`, seluruhnya huruf kecil.

### C. Menampilkan ekstensi file di Windows

Langkah ini penting agar file tidak tersimpan sebagai `PANDUAN_INSTALASI.md.txt`.

#### Windows 11

1. Buka File Explorer.
2. Klik menu **View**.
3. Klik **Show**.
4. Centang **File name extensions**.

#### Windows 10

1. Buka File Explorer.
2. Klik tab **View**.
3. Centang **File name extensions**.

### D. Membuat file menggunakan Notepad

1. Buka folder `docs`.
2. Klik kanan area kosong.
3. Pilih **New**.
4. Pilih **Text Document**.
5. Ubah nama file menjadi:

   ```text
   PANDUAN_INSTALASI.md
   ```

6. Tekan `Enter`.
7. Jika Windows memberi peringatan perubahan ekstensi, klik **Yes**.
8. Klik kanan file tersebut.
9. Pilih **Open with**.
10. Pilih **Notepad**.
11. Tempel seluruh isi dokumen dengan `Ctrl + V`.
12. Tekan `Ctrl + S` untuk menyimpan.
13. Tutup Notepad.

### E. Membuat file menggunakan Visual Studio Code

1. Install Visual Studio Code dari situs resmi jika belum ada.
2. Buka Visual Studio Code.
3. Klik **File**.
4. Klik **Open Folder...**.
5. Pilih folder proyek.
6. Klik **Select Folder**.
7. Pada panel Explorer di sebelah kiri, cari folder `docs`.
8. Klik kanan folder `docs`.
9. Klik **New File**.
10. Ketik:

    ```text
    PANDUAN_INSTALASI.md
    ```

11. Tekan `Enter`.
12. Tempel isi dokumen.
13. Tekan `Ctrl + S` pada Windows atau `Command + S` pada macOS.

### F. Memastikan file tersimpan di lokasi yang benar

Lokasi yang benar adalah:

```text
project/docs/PANDUAN_INSTALASI.md
```

Pada repository ini, contoh lengkapnya:

```text
dashboard-sna/docs/PANDUAN_INSTALASI.md
```

Struktur yang benar:

```text
dashboard-sna/
├── app.py
├── requirements.txt
├── run.bat
├── run.sh
└── docs/
    ├── PANDUAN_INSTALASI.md
    └── PANDUAN_PENGGUNAAN.md
```

Struktur yang salah:

```text
dashboard-sna/PANDUAN_INSTALASI.md
```

atau:

```text
dashboard-sna/docs/PANDUAN_INSTALASI.md.txt
```

---

## BAGIAN 2 — Cara Memverifikasi File Benar

### A. Membuka file `.md` dengan Notepad

1. Buka folder `docs`.
2. Klik kanan `PANDUAN_INSTALASI.md`.
3. Klik **Open with**.
4. Pilih **Notepad**.
5. Pastikan isi dimulai dengan:

   ```text
   # Panduan Instalasi Dashboard Analisis Sentimen & SNA
   ```

6. Gulir sampai bagian akhir.
7. Pastikan isi tidak terpotong.

### B. Preview Markdown menggunakan Visual Studio Code

Visual Studio Code memiliki preview Markdown bawaan dan tidak membutuhkan extension tambahan.

1. Buka file `PANDUAN_INSTALASI.md` di Visual Studio Code.
2. Tekan:

   ```text
   Ctrl + Shift + V
   ```

3. Preview Markdown akan terbuka.
4. Untuk preview di samping editor, tekan:

   ```text
   Ctrl + K
   ```

5. Lepaskan tombol, lalu tekan:

   ```text
   V
   ```

6. Periksa judul, tabel, daftar, dan blok perintah.
7. Pastikan tidak ada paragraf yang berubah menjadi satu baris panjang tanpa format.

### C. Memeriksa path melalui Command Prompt

1. Buka Command Prompt pada folder proyek.
2. Ketik:

   ```bat
   dir docs
   ```

3. Tekan `Enter`.
4. Pastikan `PANDUAN_INSTALASI.md` tampil.
5. Pemeriksaan lebih spesifik:

   ```bat
   if exist "docs\PANDUAN_INSTALASI.md" (echo FILE ADA) else (echo FILE TIDAK ADA)
   ```

6. Hasil yang benar:

   ```text
   FILE ADA
   ```

### D. Memeriksa path melalui Terminal macOS/Linux

1. Buka Terminal pada folder proyek.
2. Jalankan:

   ```bash
   ls -l docs/PANDUAN_INSTALASI.md
   ```

3. Jika file ada, Terminal akan menampilkan informasi file.
4. Pemeriksaan sederhana:

   ```bash
   test -f docs/PANDUAN_INSTALASI.md && echo "FILE ADA" || echo "FILE TIDAK ADA"
   ```

### E. Memastikan Git mengenali perubahan

Jika proyek di-clone dengan Git:

```bash
git status
```

Hasil seharusnya menampilkan salah satu kondisi:

```text
modified: docs/PANDUAN_INSTALASI.md
```

atau jika file benar-benar baru:

```text
untracked files: docs/PANDUAN_INSTALASI.md
```

---

## BAGIAN 3 — Checklist Kelengkapan Dokumen

Beri tanda centang setelah setiap poin diperiksa.

- [ ] Ada judul **Panduan Instalasi Dashboard Analisis Sentimen & SNA**.
- [ ] Ada subjudul **Telkom Group — Skripsi ULBI Bandung 2026**.
- [ ] Ada bagian **Prasyarat Sistem**.
- [ ] Sistem operasi Windows 10/11 dan macOS 11+ disebutkan.
- [ ] RAM minimal 8 GB dan rekomendasi 16 GB disebutkan.
- [ ] Penyimpanan kosong minimal 5 GB disebutkan.
- [ ] Kebutuhan internet untuk download model pertama disebutkan.
- [ ] Ada instruksi install Python untuk Windows.
- [ ] Instruksi Windows menjelaskan `Add Python 3.10 to PATH`.
- [ ] Ada cara memverifikasi Python menggunakan Command Prompt.
- [ ] Ada solusi untuk `python is not recognized`.
- [ ] Ada instruksi install Python untuk macOS.
- [ ] Ada cara memverifikasi Python melalui Terminal macOS.
- [ ] Ada dua opsi download proyek: Git dan ZIP.
- [ ] Ada tutorial install Git.
- [ ] Ada perintah clone repository yang benar.
- [ ] Ada cara extract ZIP di Windows.
- [ ] Ada cara extract ZIP di macOS.
- [ ] Ada cara menjalankan `run.bat` di Windows.
- [ ] Dijelaskan bahwa `run.bat` memakai Python 3.10.
- [ ] Dijelaskan bahwa launcher membuat `venv`.
- [ ] Ada cara menjalankan manual melalui Command Prompt.
- [ ] Ada cara memasang dependency dari `requirements.txt`.
- [ ] Ada cara menjalankan dengan `python -m streamlit run app.py`.
- [ ] Ada cara menjalankan `run.sh` di macOS/Linux.
- [ ] Ada instruksi `chmod +x run.sh`.
- [ ] Ada alamat `http://localhost:8501`.
- [ ] Ada penjelasan alternatif port 8502.
- [ ] Ada instruksi login dengan username `admin`.
- [ ] Ada instruksi login dengan password `admin123`.
- [ ] Ada peringatan untuk mengganti password awal.
- [ ] Ada minimal lima solusi troubleshooting.
- [ ] Setiap error memiliki penjelasan arti error.
- [ ] Setiap error memiliki langkah solusi bernomor.
- [ ] Ada solusi error model IndoBERT.
- [ ] Ada solusi error Streamlit belum terpasang.
- [ ] Ada solusi error database.
- [ ] Ada solusi port 8501 digunakan.
- [ ] Ada cara menghentikan dashboard.
- [ ] Ada cara menjalankan dashboard kembali.
- [ ] Ada cara uninstall atau hapus bersih.
- [ ] Ada cara menghapus cache Hugging Face.
- [ ] Ada cara membuat folder `docs`.
- [ ] Ada cara membuat file `.md`.
- [ ] Ada cara menyimpan file dengan `Ctrl + S`.
- [ ] Ada cara memeriksa path file.
- [ ] Ada rekomendasi Visual Studio Code untuk preview Markdown.
- [ ] Semua langkah menggunakan Bahasa Indonesia yang mudah dipahami.
- [ ] Istilah teknis dijelaskan ketika pertama digunakan.
- [ ] Tidak ada API key asli di dalam dokumen.
- [ ] Tidak ada bagian yang masih kosong atau belum dilengkapi.

---

## BAGIAN 4 — Cara Mengenali Masalah Saat Testing Panduan

### A. Minta pengguna nonteknis mencoba

1. Pilih seseorang yang belum pernah menjalankan Python atau Streamlit.
2. Jangan langsung memberi bantuan lisan.
3. Berikan hanya file panduan ini.
4. Minta orang tersebut memulai dari bagian Prasyarat.
5. Amati langkah yang membuat mereka berhenti.
6. Catat kata atau istilah yang mereka tidak pahami.
7. Catat nomor langkah yang dilewati tanpa sengaja.
8. Catat pesan error secara utuh.
9. Jangan hanya mencatat “tidak bisa”; salin teks error yang tampil.
10. Minta mereka menjelaskan dengan kalimat sendiri apa yang mereka pikir harus dilakukan.

### B. Format catatan testing

Gunakan tabel berikut:

| Nomor | Bagian panduan | Apa yang dilakukan | Masalah yang muncul | Teks error lengkap | Solusi yang berhasil | Perlu revisi panduan? |
|---:|---|---|---|---|---|---|
| 1 | Contoh: Install Python | Lupa centang PATH | Python tidak dikenali | `python is not recognized...` | Install ulang dan centang PATH | Ya |
| 2 |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |

### C. Bagian yang biasanya membingungkan

1. Memilih installer Python yang benar.
2. Lupa mencentang **Add Python to PATH**.
3. Menjalankan perintah pada folder yang salah.
4. Membuka folder luar hasil ZIP, bukan folder yang berisi `app.py`.
5. Menyimpan file sebagai `.md.txt`.
6. Menutup terminal ketika dashboard masih dipakai.
7. Mengira proses download model yang lama sebagai aplikasi hang.
8. Menggunakan Python selain 3.10 pada Windows.
9. Menggunakan port 8501 ketika launcher sudah memilih 8502.
10. Menyalin perintah bersama tanda prompt atau nomor langkah.

### D. Jika langkah tidak bekerja pada komputer lain

1. Jangan langsung mengubah kode proyek.
2. Catat sistem operasi dan versinya.
3. Catat versi Python:

   ```bash
   python --version
   ```

   dan pada Windows:

   ```bat
   py -3.10 --version
   ```

4. Catat versi Git:

   ```bash
   git --version
   ```

5. Catat versi Streamlit setelah `venv` aktif:

   ```bash
   python -m streamlit --version
   ```

6. Salin teks error lengkap dari terminal.
7. Ambil screenshot yang mencakup seluruh jendela terminal.
8. Catat perintah terakhir yang dijalankan.
9. Periksa apakah internet, antivirus, VPN, atau jaringan kantor memblokir download.
10. Bandingkan dengan komputer yang berhasil.
11. Lakukan perbaikan paling kecil dan terarah.
12. Jangan mengubah UI/UX dashboard untuk menyelesaikan masalah instalasi.

---

## Regression Test Dokumentasi dan Proyek

Karena fase ini hanya mengubah dokumentasi, file aplikasi tidak boleh ikut berubah.

### A. Periksa file yang berubah

Jalankan:

```bash
git status --short
```

Hasil yang diharapkan untuk patch ini:

```text
M docs/PANDUAN_INSTALASI.md
```

Tidak boleh ada perubahan tidak sengaja pada:

```text
app.py
pages/
auth/
utils/
.streamlit/config.toml
requirements.txt
run.bat
run.sh
```

### B. Pemeriksaan sintaks Python

Perubahan dokumentasi tidak mengubah Python, tetapi smoke test dapat dijalankan:

#### Windows

```bat
venv\Scripts\python.exe -m compileall app.py auth pages utils
```

#### macOS/Linux

```bash
venv/bin/python -m compileall app.py auth pages utils
```

Hasil tidak boleh menampilkan `SyntaxError`.

### C. Smoke test aplikasi

1. Jalankan dashboard.
2. Login.
3. Buka setiap menu utama satu kali.
4. Pastikan tidak ada tampilan yang berubah akibat patch dokumentasi.
5. Pastikan terminal tidak menampilkan import error baru.
6. Hentikan dashboard dengan benar.

---

## Mengunggah Dokumentasi ke GitHub

Bagian ini digunakan setelah file sudah diverifikasi.

### A. Buka Command Prompt pada folder proyek

1. Buka folder proyek di File Explorer.
2. Klik address bar.
3. Ketik `cmd`.
4. Tekan `Enter`.

### B. Periksa perubahan

```bat
git status
```

Pastikan yang berubah hanya:

```text
docs/PANDUAN_INSTALASI.md
```

### C. Tambahkan file ke commit

```bat
git add docs/PANDUAN_INSTALASI.md
```

### D. Buat commit

```bat
git commit -m "docs: lengkapi panduan instalasi lokal final fase 16"
```

### E. Push ke GitHub

```bat
git push origin main
```

Jika branch aktif bukan `main`, periksa dengan:

```bat
git branch --show-current
```

Kemudian ganti `main` dengan nama branch yang tampil.

### F. Verifikasi di GitHub

1. Buka repository GitHub.
2. Buka folder `docs`.
3. Klik `PANDUAN_INSTALASI.md`.
4. Pastikan GitHub menampilkan Markdown dengan rapi.
5. Pastikan commit terbaru terlihat.
6. Pastikan tidak ada file `.env`, API key, atau folder `venv` yang ikut terunggah.

---

## Ringkasan Perintah Penting

### Windows — launcher otomatis

```text
Double-click run.bat
```

### Windows — manual

```bat
py -3.10 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### macOS/Linux

```bash
cd ~/Desktop/dashboard-sna
chmod +x run.sh
./run.sh
```

### Login awal

```text
Username: admin
Password: admin123
```

### Menghentikan server

```text
Ctrl + C
```

---

## Konfirmasi Akhir

Instalasi dinyatakan berhasil apabila seluruh kondisi berikut terpenuhi:

- [ ] Python versi yang sesuai dapat dijalankan.
- [ ] Folder proyek berisi `app.py`.
- [ ] `run.bat` atau `run.sh` berhasil dijalankan.
- [ ] Dependency terpasang tanpa error fatal.
- [ ] Browser membuka localhost.
- [ ] Halaman login tampil.
- [ ] Akun admin dapat login.
- [ ] Halaman utama dashboard dapat dibuka.
- [ ] Terminal tetap berjalan selama dashboard digunakan.
- [ ] Dashboard dapat dihentikan dengan `Ctrl + C`.

---

**Dokumen:** Panduan Instalasi Dashboard Analisis Sentimen & SNA Telkom Group  
**Konteks:** Skripsi S1 Sains Data — ULBI Bandung 2026  
**Repository:** `github.com/SaefudinZuhri1/dashboard-sna`  
**Perintah utama:** `streamlit run app.py`
