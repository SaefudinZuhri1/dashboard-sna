# UI/UX LOCK DASHBOARD TELKOM GROUP

## Baseline Resmi

Baseline antarmuka yang disetujui adalah kondisi proyek setelah:

- Tahap 4 Fase 15 selesai.
- Patch v1.5 Hotfix Blank Putih IndiBiz terpasang.
- Halaman Analisis Topik IndiHome dan IndiBiz tampil normal.
- UI/UX telah disetujui pengguna.

Backup baseline:

skripsi_FASE15_FINAL_UI_LOCK_v1.0.zip

## Aturan Penguncian UI/UX

1. Jangan menulis ulang halaman secara penuh.
2. Jangan mengganti struktur layout yang sudah ada.
3. Jangan mengganti CSS global maupun CSS halaman.
4. Jangan mengubah font, warna, spacing, padding, margin, border, radius, shadow, animasi, hover, atau ukuran komponen.
5. Jangan memindahkan urutan section.
6. Jangan menghapus komponen visual yang sudah ada.
7. Jangan mengganti hero, card, selector, tombol, grafik, tabel, heatmap, WordCloud, custom loading, atau expander.
8. Jangan mengganti desain IndiHome, IndiBiz, atau Telkomsel tanpa perintah eksplisit pengguna.
9. Perbaikan fungsional harus dilakukan melalui patch kecil dan terarah.
10. Jangan mengganti seluruh file hanya untuk memperbaiki satu fungsi.
11. Jangan melakukan refactor visual tanpa persetujuan pengguna.
12. Jangan mengubah UI/UX berdasarkan master prompt lama jika berbeda dari kondisi proyek terbaru.
13. Kondisi proyek terbaru selalu menjadi sumber utama tampilan.
14. Perubahan UI/UX hanya boleh dilakukan ketika pengguna secara eksplisit meminta perubahan visual.
15. Setiap patch harus menjelaskan bagian kode yang diubah dan memastikan komponen visual lain tidak terpengaruh.

## Metode Pengerjaan Wajib

Untuk perbaikan fungsional:

1. Audit akar masalah terlebih dahulu.
2. Temukan fungsi atau blok kode yang bermasalah.
3. Ubah hanya bagian tersebut.
4. Jangan menyentuh CSS atau HTML visual.
5. Buat backup otomatis sebelum pemasangan.
6. Jalankan pemeriksaan sintaks.
7. Lakukan regression test pada seluruh halaman.
8. Bandingkan tampilan sebelum dan sesudah patch.
9. Batalkan patch jika terdapat perubahan visual yang tidak diminta.

## Larangan

Dilarang:

- Full rewrite halaman.
- Mengganti file menggunakan template generik.
- Mengembalikan desain dari prompt lama.
- Menambahkan section visual baru tanpa persetujuan.
- Mengubah ukuran card agar seragam secara otomatis.
- Mengubah tata letak hanya karena dianggap lebih modern.
- Mengubah font ke Syne atau DM Sans.
- Menghapus Plus Jakarta Sans atau Inter.
- Menggunakan desain dummy yang berbeda dari halaman lain.
- Mengubah notebook Google Colab untuk masalah dashboard.

## Prinsip Utama

UI/UX DIKUNCI.

Perubahan hanya diperbolehkan pada logika dan fungsi, kecuali pengguna secara eksplisit meminta perubahan visual.