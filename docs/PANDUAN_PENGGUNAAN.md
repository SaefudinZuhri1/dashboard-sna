# Panduan Penggunaan Dashboard Telkom Group

Panduan ini menjelaskan cara menggunakan dashboard setelah aplikasi berhasil dibuka. Nama dan jumlah menu yang terlihat dapat berbeda karena dashboard menerapkan hak akses berdasarkan role.

## Login ke Dashboard

### Login menggunakan akun awal

1. Jalankan dashboard.
2. Tunggu sampai halaman login terbuka.
3. Klik kolom **Username**.
4. Ketik:

```text
admin
```

5. Klik kolom **Password**.
6. Ketik:

```text
admin123
```

7. Klik tombol **Masuk**.
8. Tunggu sampai Beranda tampil.
9. Segera buka **Profil → Ubah Password Akun** dan ganti password awal.

### Perbedaan akun utama dan akun biasa

Akun `admin` adalah akun utama dengan `user_id=1` dan role **Data Analis**. Akun ini dapat membuka seluruh halaman, termasuk Admin Panel, serta tidak dapat dihapus melalui dashboard.

Akun yang dibuat melalui registrasi memperoleh role **Manajemen**. Data Analis dapat mengubah role akun lain melalui Admin Panel.

| Role | Akses utama |
|---|---|
| Manajemen | Beranda dan Rekomendasi |
| Sosmed Officer | Beranda, Social Network Analysis, Rekomendasi, Profil, dan Tentang |
| Data Analis | Seluruh halaman dan Admin Panel |

Jika sebuah menu tidak muncul, itu belum tentu error. Kemungkinan role akun memang tidak memiliki akses ke halaman tersebut.

## Navigasi Halaman

Sidebar berada di sisi kiri. Sidebar berisi identitas pengguna, menu sesuai role, Mode Demo, pengaturan tampilan, dan tombol logout.

Contoh tampilan sederhana:

```text
┌──────────────────────────────┐
│  LOGO TELKOM GROUP           │
│                              │
│  [Avatar] Nama Pengguna      │
│           Data Analis        │
│                              │
│  🏠 Beranda                  │
│  📊 Dataset                  │
│  🙂 Analisis Sentimen        │
│  💬 Analisis Topik           │
│  🔗 Social Network Analysis  │
│  💡 Rekomendasi              │
│  👤 Profil                   │
│  🛡 Admin Panel              │
│  📖 Tentang                  │
│                              │
│  🎯 Mode Demo (Sidang)       │
│  ◐ Mode Gelap                │
│  🚪 Logout                   │
└──────────────────────────────┘
```

Cara berpindah halaman:

1. Arahkan kursor ke sidebar.
2. Klik nama halaman yang ingin dibuka.
3. Tunggu custom loading selesai.
4. Pastikan judul halaman berubah.
5. Gunakan tombol browser **Back** hanya jika diperlukan; navigasi utama sebaiknya melalui sidebar.

## Mode Gelap dan Mode Terang

1. Buka sidebar.
2. Cari toggle **Mode Gelap**.
3. Aktifkan untuk tema gelap.
4. Nonaktifkan untuk tema terang.
5. Tunggu dashboard melakukan rerun.

Perubahan tema tidak mengubah data atau hasil analisis.

## Halaman Beranda

Beranda menampilkan gambaran cepat mengenai IndiHome, IndiBiz, dan Telkomsel.

### Cara membaca ringkasan statistik

1. Periksa badge status layanan dan sumber data.
2. Baca kartu KPI seperti total data, jumlah platform, distribusi sentimen, atau statistik jaringan.
3. Arahkan kursor ke grafik untuk melihat nilai detail.
4. Klik legenda grafik untuk menyembunyikan atau menampilkan kategori.
5. Baca bagian insight untuk memahami makna ringkasan, bukan hanya angkanya.

### Arti status sumber data

- **Data Real/Data Nyata** berarti data berasal dari file penelitian yang berhasil dikenali.
- **Data Dummy** berarti dashboard memakai data simulasi agar halaman tetap dapat dibuka.
- **Mode Demo** berarti data sample terkurasi dipakai untuk demonstrasi.

Jangan menggunakan angka dari Data Dummy sebagai kesimpulan penelitian final.

## Halaman Dataset

Halaman Dataset digunakan untuk melihat, memfilter, mencari, mengunggah, dan mengekspor data.

### Cara memilih layanan

1. Buka **Dataset**.
2. Cari kontrol **Layanan**.
3. Pilih salah satu:
   - IndiHome
   - IndiBiz
   - Telkomsel
4. Atur platform, sentimen, atau pencarian bila diperlukan.
5. Klik **Terapkan Filter**.

### Cara membaca tabel

Kolom yang umum ditampilkan:

| Kolom | Arti |
|---|---|
| tanggal | Waktu publikasi komentar atau postingan |
| layanan | IndiHome, IndiBiz, atau Telkomsel |
| platform | Twitter, Instagram, atau TikTok |
| username | Akun sumber percakapan |
| followers | Jumlah pengikut akun |
| komentar | Isi teks yang dianalisis |
| sentimen | Positif, netral, atau negatif |
| confidence | Tingkat keyakinan prediksi model |

Gunakan pagination untuk berpindah halaman tabel. Perubahan pagination tidak mengubah data sumber.

### Cara mencari komentar

1. Ketik kata pada kolom **Cari komentar**.
2. Klik **Terapkan Filter**.
3. Tabel dan ringkasan akan menampilkan data yang sesuai.
4. Klik **Reset Filter** untuk kembali ke kondisi awal.

### Cara upload data baru

1. Buka expander **Upload Dataset Sendiri**.
2. Klik area upload.
3. Pilih satu file dengan format:
   - `.csv`
   - `.xlsx`
4. Ukuran maksimum mengikuti konfigurasi proyek, yaitu 50 MB per file.
5. Klik **Analisis File Ini**.
6. Tunggu proses deteksi dan preview selesai.
7. Periksa status relevansi, jumlah baris, jumlah kolom, dan sepuluh baris pertama.

Untuk hasil paling baik, file sebaiknya memiliki kolom berikut atau nama aliasnya:

| Kebutuhan | Nama kolom yang dikenali |
|---|---|
| Teks | `content`, `komentar`, `text`, `full_text`, `comment`, `tweet_text`, atau `caption` |
| Platform | `platform`, `specific_resource_type`, `source_platform`, atau `resource_type` |
| Username | `from_username`, `username`, `user`, `screen_name`, `author`, atau `account` |

Kolom tambahan yang didukung antara lain:

- `tanggal`, `date`, `created_at`, atau `timestamp`
- `layanan` atau `service`
- `followers` atau `followers_count`
- `sentimen`, `predicted_sentiment`, atau `label`
- `confidence`, `score`, atau `probability`

Contoh CSV sederhana:

```csv
content,platform,from_username,followers,layanan
"Internet rumah stabil dan cepat",instagram,pengguna_a,1250,IndiHome
"Jaringan lambat sejak pagi",twitter,pengguna_b,430,Telkomsel
"Butuh paket bisnis yang lebih fleksibel",tiktok,pengguna_c,890,IndiBiz
```

Upload tidak mengganti dataset penelitian bawaan. Data upload disimpan sementara selama sesi dashboard aktif.

### Cara mengekspor data

1. Terapkan filter yang diinginkan.
2. Cari tombol download atau ekspor.
3. Pilih CSV atau Excel jika tersedia.
4. Simpan file ke folder komputer.
5. Buka file hasil ekspor untuk memastikan jumlah baris sesuai filter.

## Halaman Analisis Sentimen

Halaman ini digunakan untuk membaca kecenderungan opini publik.

### Arti sentimen

- **Positif**: komentar berisi apresiasi, kepuasan, dukungan, atau pengalaman baik.
- **Netral**: komentar berupa informasi, pertanyaan, permintaan bantuan, atau opini yang tidak kuat ke arah positif/negatif.
- **Negatif**: komentar berisi keluhan, kekecewaan, masalah layanan, atau kritik.

### Cara membaca pie chart

1. Perhatikan ukuran setiap irisan.
2. Irisan terbesar menunjukkan proporsi sentimen dominan.
3. Arahkan kursor ke irisan untuk melihat jumlah dan persentase.
4. Klik legenda untuk menyembunyikan kategori sementara.
5. Jangan menarik kesimpulan hanya dari warna; baca label dan jumlahnya.

### Cara membaca bar chart

1. Perhatikan panjang atau tinggi bar.
2. Bar yang lebih panjang menunjukkan jumlah lebih besar.
3. Gunakan tooltip saat kursor diarahkan ke bar.
4. Bandingkan kategori pada platform yang sama.
5. Periksa jumlah data sebelum membandingkan dua platform.

### Cara filter platform

1. Pilih layanan.
2. Buka tab atau selector platform.
3. Pilih Twitter/X, Instagram, atau TikTok.
4. Tunggu grafik melakukan pembaruan.
5. Bandingkan distribusi positif, netral, dan negatif.

### Confidence model

Confidence menunjukkan tingkat keyakinan model terhadap label yang dipilih. Nilai tinggi tidak selalu berarti prediksi pasti benar. Sarkasme, singkatan, bahasa daerah, atau konteks yang sangat pendek tetap dapat menyebabkan salah klasifikasi.

### Prediksi manual

1. Pilih layanan yang modelnya tersedia.
2. Buka bagian prediksi manual.
3. Ketik satu komentar.
4. Klik tombol prediksi.
5. Baca label sentimen dan confidence.
6. Jangan memasukkan data pribadi atau rahasia.

## Halaman Analisis Topik

Halaman ini membantu memahami isu dan kata dominan.

### Cara membaca WordCloud

- Kata yang lebih besar muncul lebih sering atau memiliki bobot lebih tinggi.
- WordCloud adalah alat eksplorasi, bukan bukti statistik tunggal.
- Nama brand dapat terlihat besar karena hampir semua komentar membahas brand tersebut.
- Periksa tabel frekuensi dan contoh komentar sebelum menyimpulkan topik.

### Cara menggunakan filter

1. Pilih layanan.
2. Pilih platform jika tersedia.
3. Pilih sentimen.
4. Atur pilihan tampilan brand bila diperlukan.
5. Terapkan filter.
6. Baca WordCloud, chart frekuensi, dan contoh komentar bersama-sama.

### Cara membaca chart frekuensi topik

1. Topik dengan bar paling panjang paling sering muncul pada data terfilter.
2. Arahkan kursor ke bar untuk melihat nilai.
3. Periksa apakah topik berasal dari sentimen positif, netral, atau negatif.
4. Baca komentar contoh untuk memastikan nama topik sesuai isi percakapan.

## Halaman Social Network Analysis (SNA)

SNA digunakan untuk melihat hubungan antar akun.

### Istilah dasar

- **Node**: akun atau aktor dalam jaringan.
- **Edge**: hubungan atau interaksi antar akun.
- **In-degree**: jumlah interaksi yang masuk ke suatu akun.
- **Out-degree**: jumlah interaksi yang keluar dari suatu akun.
- **Degree centrality**: ukuran keterhubungan langsung suatu node dalam jaringan.
- **PageRank**: ukuran kepentingan node dengan mempertimbangkan kualitas koneksinya pada analisis yang menggunakannya.

### Cara membaca graf jaringan

1. Pilih layanan.
2. Pilih platform.
3. Atur batas node bila tersedia.
4. Tunggu graf selesai dimuat.
5. Arahkan kursor ke node untuk membaca detail akun.
6. Gunakan zoom dan drag untuk menelusuri jaringan.
7. Perhatikan node yang memiliki banyak koneksi.

### Arti ukuran dan warna node

- Node lebih besar biasanya menandakan nilai metrik atau tingkat kepentingan lebih tinggi.
- Warna membedakan kategori, platform, brand, atau kelompok sesuai legenda halaman.
- Selalu baca legenda dan tooltip karena arti warna dapat berbeda berdasarkan konteks analisis.

### Cara mengidentifikasi influencer

Jangan hanya melihat followers. Periksa beberapa indikator:

1. Degree centrality atau degree yang tinggi.
2. In-degree tinggi, yang menunjukkan banyak interaksi masuk.
3. Out-degree tinggi, yang menunjukkan aktivitas menghubungkan atau merespons akun lain.
4. PageRank apabila ditampilkan.
5. Followers sebagai indikator tambahan potensi jangkauan.
6. Status akun brand atau non-brand.

Akun resmi biasanya berada di pusat jaringan, tetapi tidak selalu dianggap influencer non-brand.

### Cara menggunakan tabel influencer

1. Pilih platform atau batas baris.
2. Urutkan berdasarkan metrik yang relevan.
3. Aktifkan detail akun jika diperlukan.
4. Klik username untuk melihat metrik detail bila tersedia.
5. Download tabel setelah filter sesuai kebutuhan.

## Halaman Rekomendasi

Halaman ini menggabungkan hasil topik, sentimen, dan influencer.

### Cara membaca kartu influencer

1. Perhatikan username dan platform.
2. Baca kategori atau status validasi.
3. Bandingkan followers dengan metrik jaringan.
4. Baca alasan rekomendasi.
5. Jangan menilai kredibilitas seseorang hanya dari jumlah followers.

### Cara membaca matriks kesesuaian

Matriks menunjukkan hubungan antara kandidat influencer dan topik atau kebutuhan komunikasi.

1. Pilih layanan.
2. Pilih topik.
3. Perhatikan sel dengan nilai lebih tinggi.
4. Cocokkan hasil dengan platform dan karakter audiens.
5. Baca catatan metodologis sebelum memilih kandidat.

Matriks adalah alat bantu prioritas, bukan keputusan otomatis.

### Cara membaca strategi per topik

1. Pilih topik dominan.
2. Baca masalah utama yang diringkas.
3. Periksa tujuan komunikasi.
4. Baca contoh pendekatan konten.
5. Sesuaikan dengan platform.
6. Validasi rekomendasi dengan data dan kebijakan organisasi.

### Cara menggunakan Generator Ide Konten Gemini

1. Pastikan API key Gemini sudah aktif.
2. Pilih layanan.
3. Pilih platform.
4. Pilih topik.
5. Pilih konteks influencer atau sasaran komunikasi.
6. Klik tombol generate.
7. Tunggu hasil tampil.
8. Periksa kembali fakta, tone, nama akun, dan klaim sebelum digunakan.
9. Gunakan fallback lokal jika Gemini tidak tersedia.

Konten AI harus ditinjau manusia sebelum dipublikasikan.

## Halaman Profil

1. Buka **Profil**.
2. Periksa nama, username, email, dan role.
3. Gunakan bagian avatar untuk mengunggah JPG atau PNG sesuai batas ukuran yang ditampilkan.
4. Gunakan **Edit Profil Akun** untuk memperbarui nama atau email.
5. Gunakan **Ubah Password Akun** untuk mengganti password.
6. Simpan perubahan.
7. Login ulang apabila sistem memintanya.

Akun utama `user_id=1` tidak dapat dihapus.

## Admin Panel

Admin Panel hanya tersedia bagi role Data Analis.

Fungsi utamanya:

- melihat daftar pengguna;
- menambah pengguna;
- mengubah role;
- menghapus pengguna nonutama;
- melihat statistik akun;
- memeriksa kesiapan data;
- membaca audit aktivitas.

Jangan mengubah role atau menghapus akun tanpa memastikan identitas pengguna.

## Halaman Tentang

Halaman Tentang berisi:

- judul penelitian;
- identitas peneliti;
- pembimbing dan penguji;
- metodologi SNA dan IndoBERT;
- teknologi yang digunakan;
- penjelasan akademik dalam Bahasa Indonesia dan Inggris.

Gunakan halaman ini saat menjelaskan konteks dashboard kepada dosen, penguji, atau pengguna nonteknis.

## Mode Demo (Tanpa Data Nyata)

Mode Demo membantu dashboard tetap dapat diperagakan ketika file data atau model belum tersedia.

### Cara mengaktifkan

1. Login.
2. Buka sidebar.
3. Cari toggle **Mode Demo (Sidang)**.
4. Aktifkan toggle.
5. Tunggu dashboard melakukan rerun.
6. Pastikan muncul penanda bahwa Mode Demo aktif.

### Yang terjadi saat Mode Demo aktif

- halaman analitik memakai data sample terkurasi;
- data penelitian asli tidak diubah;
- Gemini dapat menggunakan fallback lokal untuk menghindari ketergantungan internet;
- hasil ditujukan untuk demonstrasi antarmuka;
- banner atau badge membedakan data demo dari data nyata.

### Kapan Mode Demo digunakan

- saat presentasi tanpa koneksi internet stabil;
- saat file CSV belum dipindahkan;
- saat model belum tersedia;
- saat ingin menguji alur halaman tanpa memengaruhi data penelitian.

Jangan mengutip angka Mode Demo sebagai hasil penelitian aktual.

## Logout

1. Buka sidebar.
2. Klik **Logout**.
3. Tunggu transisi selesai.
4. Pastikan halaman login kembali tampil.
5. Pada komputer bersama, tutup browser setelah logout.

## Pemeriksaan Cepat Jika Halaman Bermasalah

1. Baca badge Data Real, Data Dummy, atau Mode Demo.
2. Tunggu custom loading selesai.
3. Tekan `Ctrl + Shift + R` untuk hard refresh.
4. Periksa CMD yang menjalankan Streamlit.
5. Jangan mengubah CSS atau source code hanya karena data kosong.
6. Aktifkan Mode Demo untuk memastikan halaman dapat dirender.
7. Laporkan nama halaman dan pesan error lengkap tanpa menyertakan API key atau password.

## Checklist Penggunaan

- [ ] Login berhasil.
- [ ] Menu yang terlihat sesuai role.
- [ ] Sumber data telah dibaca sebelum menginterpretasi grafik.
- [ ] Filter layanan dan platform sudah benar.
- [ ] Label serta nilai grafik dibaca bersama-sama.
- [ ] WordCloud diverifikasi dengan frekuensi dan komentar contoh.
- [ ] Influencer dinilai dari metrik jaringan dan followers, bukan satu indikator saja.
- [ ] Rekomendasi AI ditinjau manusia sebelum dipakai.
- [ ] Mode Demo tidak dianggap sebagai hasil aktual.
- [ ] Logout dilakukan setelah penggunaan pada komputer bersama.
