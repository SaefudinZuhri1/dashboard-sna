# utils/topic_classifier.py
# Klasifikasi topik berbasis keyword untuk komentar Telkom Group
# Mendukung layanan: IndiHome, IndiBiz, Telkomsel
# Sentimen: Positif, Netral, Negatif — minimal 15 topik per sentimen

"""Klasifikasi topik berbasis keyword untuk komentar layanan Telkom Group."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import Any, Iterable

import pandas as pd

TOPICS = {'Positif': {'Kecepatan Stabil': ['cepat',
                                  'cepet',
                                  'kencang',
                                  'ngebut',
                                  'stabil',
                                  'lancar',
                                  'mulus',
                                  'speed bagus',
                                  'koneksi cepat',
                                  'internet lancar',
                                  'wifi stabil',
                                  'sinyal kencang'],
             'Promo Menarik': ['promo',
                               'diskon',
                               'cashback',
                               'potongan harga',
                               'harga promo',
                               'voucher',
                               'bonus kuota',
                               'gratis',
                               'hemat',
                               'murah banget',
                               'deal bagus',
                               'promo mantap'],
             'Instalasi Cepat': ['cepat pasang',
                                 'pemasangan cepat',
                                 'instalasi cepat',
                                 'langsung aktif',
                                 'teknisi cepat datang',
                                 'proses cepat',
                                 'sat set',
                                 'gercep pasang',
                                 'hari ini pasang',
                                 'besok aktif',
                                 'pemasangan lancar'],
             'CS Ramah & Responsif': ['cs ramah',
                                      'admin ramah',
                                      'pelayanannya ramah',
                                      'terima kasih',
                                      'terimakasih',
                                      'cepat balas',
                                      'responsif',
                                      'fast response',
                                      'helpful',
                                      'solutif',
                                      'ditanggapi cepat',
                                      'gercep jawab',
                                      'pelayanan ramah',
                                      'cs mantap'],
             'Coverage Luas': ['coverage luas',
                               'jangkauan luas',
                               'jaringan luas',
                               'sampai pelosok',
                               'ada di mana mana',
                               'sinyal sampai desa',
                               'tersedia luas',
                               'coverage mantap',
                               'jangkauan nasional',
                               'area terjangkau',
                               'koneksi di mana saja'],
             'Harga Terjangkau': ['harga terjangkau',
                                  'murah',
                                  'ramah kantong',
                                  'worth it',
                                  'sesuai harga',
                                  'biaya wajar',
                                  'tidak mahal',
                                  'hemat biaya',
                                  'value for money',
                                  'cocok di kantong',
                                  'harga bersahabat'],
             'Paket Lengkap': ['paket lengkap',
                               'paket komplit',
                               'bundling lengkap',
                               'all in one',
                               'internet dan tv',
                               'telepon dan internet',
                               'banyak pilihan paket',
                               'paket sesuai kebutuhan',
                               'benefit lengkap',
                               'layanan lengkap',
                               'kuota lengkap'],
             'Streaming Lancar': ['streaming lancar',
                                  'netflix lancar',
                                  'youtube lancar',
                                  'nonton tanpa buffering',
                                  'video mulus',
                                  'disney plus lancar',
                                  'vidio lancar',
                                  'streaming stabil',
                                  'nonton 4k lancar',
                                  'tidak buffering',
                                  'live streaming lancar'],
             'Gaming Tanpa Lag': ['gaming lancar',
                                  'main game lancar',
                                  'tanpa lag',
                                  'ping rendah',
                                  'low ping',
                                  'anti lag',
                                  'game stabil',
                                  'mabar lancar',
                                  'fps lancar',
                                  'latency rendah',
                                  'tidak ngelag'],
             'Respons Cepat Gangguan': ['cepat ditangani',
                                        'langsung beres',
                                        'gangguan cepat selesai',
                                        'teknisi cepat datang',
                                        'laporan cepat diproses',
                                        'problem solved',
                                        'cepat normal',
                                        'langsung diperbaiki',
                                        'respons gangguan cepat',
                                        'keluhan cepat beres'],
             'Pelayanan Profesional': ['profesional',
                                       'pelayanan profesional',
                                       'kerja rapi',
                                       'petugas sopan',
                                       'teknisi profesional',
                                       'memuaskan',
                                       'pelayanan bagus',
                                       'layanan prima',
                                       'proses jelas',
                                       'kompeten',
                                       'service excellent'],
             'Sinyal Merata': ['sinyal merata',
                               'stabil di mana mana',
                               'sinyal konsisten',
                               'jaringan merata',
                               'sinyal kuat',
                               'full bar',
                               'sinyal bagus',
                               'koneksi merata',
                               'stabil di berbagai daerah',
                               'jaringan konsisten'],
             'Koneksi WFH Andal': ['wfh lancar',
                                   'kerja dari rumah lancar',
                                   'zoom lancar',
                                   'meeting lancar',
                                   'video conference lancar',
                                   'kerja online stabil',
                                   'upload kerja cepat',
                                   'vpn lancar',
                                   'kelas online lancar',
                                   'koneksi andal',
                                   'remote work lancar'],
             'Upgrade Mudah': ['mudah upgrade',
                               'gampang upgrade',
                               'upgrade cepat',
                               'ganti paket mudah',
                               'naik paket mudah',
                               'proses upgrade lancar',
                               'upgrade tanpa ribet',
                               'pindah paket gampang',
                               'tambah kecepatan mudah',
                               'upgrade langsung aktif'],
             'Fitur Tambahan Bagus': ['fitur bagus',
                                      'bonus menarik',
                                      'fitur tambahan',
                                      'value lebih',
                                      'add on berguna',
                                      'parental control bagus',
                                      'benefit ekstra',
                                      'bonus channel',
                                      'layanan tambahan bagus',
                                      'fitur lengkap',
                                      'ekstra kuota'],
             'Aplikasi Mudah Digunakan': ['aplikasi mudah',
                                          'app mudah',
                                          'mytelkomsel mudah',
                                          'aplikasi lancar',
                                          'ui mudah',
                                          'gampang dipakai',
                                          'navigasi jelas',
                                          'transaksi mudah',
                                          'bayar lewat aplikasi mudah',
                                          'aplikasi praktis',
                                          'user friendly']},
 'Netral': {'Pertanyaan Paket': ['tanya paket',
                                 'paket apa',
                                 'ada paket',
                                 'info paket',
                                 'paket internet apa',
                                 'pilihan paket',
                                 'rekomendasi paket',
                                 'paket tersedia',
                                 'paket bulanan',
                                 'paket harian',
                                 'min paket'],
            'Cek Tagihan': ['cek tagihan',
                            'tagihan bulan ini',
                            'bayar berapa',
                            'jumlah tagihan',
                            'invoice bulan ini',
                            'tagihan saya',
                            'cek billing',
                            'rincian tagihan',
                            'jatuh tempo kapan',
                            'nominal tagihan',
                            'tagihan terbaru'],
            'Laporan Gangguan': ['mau lapor',
                                 'lapor gangguan',
                                 'ada gangguan',
                                 'laporan jaringan',
                                 'lapor internet',
                                 'koneksi bermasalah',
                                 'gangguan di area',
                                 'laporan wifi',
                                 'saya melapor',
                                 'tiket gangguan',
                                 'gangguan hari ini'],
            'Permintaan Bantuan': ['tolong bantu',
                                   'minta bantuan',
                                   'bantu dong',
                                   'mohon bantuan',
                                   'butuh bantuan',
                                   'admin bantu',
                                   'cs bantu',
                                   'help me',
                                   'perlu dibantu',
                                   'bisa bantu',
                                   'tolong cek'],
            'Info Promo': ['ada promo',
                           'promo apa',
                           'info promo',
                           'diskon gak',
                           'promo terbaru',
                           'promo bulan ini',
                           'cek promo',
                           'promo masih ada',
                           'cashback apa',
                           'bonus apa',
                           'penawaran terbaru'],
            'Pengumuman Maintenance': ['maintenance',
                                       'pemeliharaan',
                                       'jadwal maintenance',
                                       'perbaikan jaringan',
                                       'maintenance terjadwal',
                                       'sedang pemeliharaan',
                                       'jadwal perbaikan',
                                       'network maintenance',
                                       'downtime terjadwal',
                                       'pemberitahuan gangguan',
                                       'upgrade jaringan'],
            'Tanya Cara Daftar': ['cara daftar',
                                  'gimana daftar',
                                  'mau daftar',
                                  'pendaftaran',
                                  'daftar indihome',
                                  'daftar indibiz',
                                  'daftar telkomsel',
                                  'registrasi layanan',
                                  'syarat daftar',
                                  'daftar online',
                                  'prosedur daftar'],
            'Tanya Lokasi Bayar': ['bayar di mana',
                                   'tempat bayar',
                                   'lokasi pembayaran',
                                   'kantor pembayaran',
                                   'bayar lewat apa',
                                   'channel pembayaran',
                                   'gerai terdekat',
                                   'plasa telkom',
                                   'bayar via bank',
                                   'bayar via aplikasi',
                                   'metode pembayaran'],
            'Cek Status Pengaduan': ['status pengaduan',
                                     'sudah diproses',
                                     'cek laporan',
                                     'nomor tiket',
                                     'status tiket',
                                     'laporan saya',
                                     'progres pengaduan',
                                     'tindak lanjut laporan',
                                     'sudah ditangani belum',
                                     'cek keluhan',
                                     'update tiket'],
            'Tanya Kecepatan Paket': ['kecepatan berapa',
                                      'speed berapa',
                                      'berapa mbps',
                                      'paket 20 mbps',
                                      'paket 50 mbps',
                                      'upload berapa',
                                      'download berapa',
                                      'kecepatan paket',
                                      'speed paket',
                                      'bandwidth berapa',
                                      'ping berapa'],
            'Perbandingan Paket': ['bandingkan paket',
                                   'lebih baik mana',
                                   'pilih yang mana',
                                   'beda paket',
                                   'perbedaan paket',
                                   'paket a atau b',
                                   'paket terbaik mana',
                                   'compare paket',
                                   'cocok mana',
                                   'mending paket',
                                   'opsi paket'],
            'Tanya Coverage Area': ['cek coverage',
                                    'daerah saya',
                                    'tersedia gak',
                                    'ada jaringan di',
                                    'coverage area',
                                    'jangkauan daerah',
                                    'lokasi saya terjangkau',
                                    'cek ketersediaan',
                                    'bisa pasang di',
                                    'sinyal di daerah',
                                    'area layanan'],
            'Request Upgrade': ['mau upgrade',
                                'request upgrade',
                                'ganti paket',
                                'pindah ke paket',
                                'tambah kecepatan',
                                'naik paket',
                                'upgrade layanan',
                                'upgrade internet',
                                'ubah paket',
                                'migrasi paket',
                                'tambah mbps'],
            'Feedback Netral': ['biasa aja',
                                'lumayan',
                                'standar',
                                'oke sih',
                                'cukup',
                                'normal',
                                'so so',
                                'tidak buruk',
                                'masih oke',
                                'sesuai standar',
                                'ya begitu'],
            'Konfirmasi Pembayaran': ['sudah bayar',
                                      'konfirmasi pembayaran',
                                      'bukti bayar',
                                      'pembayaran berhasil',
                                      'sudah transfer',
                                      'cek pembayaran',
                                      'lunas',
                                      'pembayaran masuk',
                                      'kirim bukti',
                                      'bayar tadi',
                                      'status pembayaran'],
            'Tanya Instalasi': ['kapan dipasang',
                                'jadwal pasang',
                                'proses instalasi',
                                'berapa lama pasang',
                                'teknisi kapan datang',
                                'cek jadwal teknisi',
                                'pemasangan kapan',
                                'survey kapan',
                                'status instalasi',
                                'pasang baru',
                                'waktu pemasangan'],
            'Tanya Router dan Perangkat': ['router apa',
                                           'modem apa',
                                           'tipe router',
                                           'cara restart router',
                                           'lampu modem',
                                           'ganti modem',
                                           'perangkat bawaan',
                                           'stb apa',
                                           'setting wifi',
                                           'password wifi',
                                           'router tersedia'],
            'Tanya Kuota dan Masa Aktif': ['sisa kuota',
                                           'cek kuota',
                                           'masa aktif',
                                           'kuota berapa',
                                           'kuota utama',
                                           'kuota lokal',
                                           'masa berlaku',
                                           'cek pulsa',
                                           'kuota belum masuk',
                                           'perpanjang masa aktif',
                                           'detail kuota']},
 'Negatif': {'Gangguan Jaringan': ['gangguan',
                                   'sinyal jelek',
                                   'sinyal bermasalah',
                                   'tidak bisa nelpon',
                                   'tidak bisa telepon',
                                   'jaringan putus',
                                   'internet putus',
                                   'sering putus',
                                   'koneksi terputus',
                                   'jaringan error',
                                   'internet error',
                                   'jaringan down',
                                   'tidak bisa internet',
                                   'koneksi bermasalah',
                                   'gangguan terus',
                                   'putus nyambung'],
             'Kecepatan Lambat': ['lemot',
                                  'lambat',
                                  'buffering',
                                  'loading lama',
                                  'lelet',
                                  'ngelag',
                                  'speed turun',
                                  'internet pelan',
                                  'koneksi lamban',
                                  'download lama',
                                  'upload lama',
                                  'ping tinggi'],
             'Tagihan Salah/Bengkak': ['tagihan bengkak',
                                       'tagihan salah',
                                       'tagihan lebih',
                                       'overcharge',
                                       'billing salah',
                                       'biaya membengkak',
                                       'nominal tidak sesuai',
                                       'tagihan dobel',
                                       'kena biaya tambahan',
                                       'invoice salah',
                                       'bayar lebih'],
             'CS Lambat/Tidak Responsif': ['cs lambat',
                                           'tidak responsif',
                                           'lama respons',
                                           'tidak ditanggapi',
                                           'admin diam',
                                           'cs tidak jawab',
                                           'slow response',
                                           'susah dihubungi',
                                           'keluhan diabaikan',
                                           'balas lama',
                                           'customer service buruk'],
             'Pemadaman Berulang': ['mati lagi',
                                    'padam lagi',
                                    'berulang',
                                    'sering down',
                                    'mati terus',
                                    'gangguan berulang',
                                    'internet mati lagi',
                                    'jaringan padam',
                                    'tiap hari mati',
                                    'putus terus',
                                    'down berkali kali'],
             'Harga Mahal': ['mahal',
                             'kemahalan',
                             'terlalu mahal',
                             'harga tinggi',
                             'tidak sebanding',
                             'bayar banyak',
                             'tarif mahal',
                             'biaya mahal',
                             'harga tidak masuk akal',
                             'boros biaya',
                             'mencekik'],
             'Instalasi Lama': ['pasang lama',
                                'instalasi lama',
                                'tunggu teknisi',
                                'teknisi tidak datang',
                                'janji tidak ditepati',
                                'pemasangan molor',
                                'survey lama',
                                'aktivasi lama',
                                'belum dipasang',
                                'jadwal mundur',
                                'proses berhari hari'],
             'Paket Tidak Sesuai': ['tidak sesuai iklan',
                                    'paket tidak sesuai',
                                    'beda iklan',
                                    'benefit tidak masuk',
                                    'kecepatan tidak sesuai paket',
                                    'paket mengecewakan',
                                    'layanan tidak sesuai',
                                    'janji paket palsu',
                                    'kuota tidak sesuai',
                                    'spesifikasi beda',
                                    'paket zonk'],
             'Sinyal Hilang': ['sinyal hilang',
                               'no signal',
                               'blank',
                               'tidak ada jaringan',
                               'sinyal kosong',
                               'hilang sinyal',
                               'emergency calls only',
                               'bar sinyal hilang',
                               'sinyal mati',
                               'jaringan tidak muncul',
                               'searching terus'],
             'Router Bermasalah': ['router rusak',
                                   'modem rusak',
                                   'router error',
                                   'modem mati',
                                   'restart terus',
                                   'mati sendiri',
                                   'lampu los merah',
                                   'wifi tidak muncul',
                                   'router panas',
                                   'perangkat bermasalah',
                                   'ont error'],
             'Pemblokiran Layanan': ['diblokir',
                                     'terblokir',
                                     'suspend',
                                     'suspended',
                                     'blocked',
                                     'layanan diputus',
                                     'internet diisolir',
                                     'nomor diblokir',
                                     'akun terkunci',
                                     'akses ditutup',
                                     'pemutusan sepihak'],
             'Migrasi Rumit': ['migrasi rumit',
                               'pindah paket susah',
                               'upgrade susah',
                               'downgrade susah',
                               'proses migrasi lama',
                               'ganti paket ribet',
                               'dilempar lempar',
                               'syarat rumit',
                               'migrasi gagal',
                               'upgrade gagal',
                               'pindah layanan susah'],
             'Refund Tidak Jelas': ['refund',
                                    'uang kembali',
                                    'tidak dikembalikan',
                                    'pengembalian dana',
                                    'refund lama',
                                    'refund belum masuk',
                                    'kompensasi tidak jelas',
                                    'uang nyangkut',
                                    'refund ditolak',
                                    'proses refund',
                                    'dana belum kembali'],
             'Kuota Cepat Habis': ['cepat habis',
                                   'kuota boros',
                                   'kuota hilang',
                                   'kuota tersedot',
                                   'kuota berkurang sendiri',
                                   'paket data cepat habis',
                                   'pemakaian tidak wajar',
                                   'kuota lenyap',
                                   'baru beli sudah habis',
                                   'sedot kuota',
                                   'kuota bocor'],
             'Tidak Ada Sinyal Daerah': ['blank spot',
                                         'pelosok tidak ada sinyal',
                                         'daerah tidak terjangkau',
                                         'pinggiran tidak ada jaringan',
                                         'sinyal di desa hilang',
                                         'coverage buruk',
                                         'area tanpa sinyal',
                                         'jaringan tidak masuk',
                                         'susah sinyal di daerah',
                                         'lokasi tidak tercover'],
             'Aplikasi Bermasalah': ['aplikasi error',
                                     'app error',
                                     'mytelkomsel error',
                                     'aplikasi crash',
                                     'tidak bisa login',
                                     'otp tidak masuk',
                                     'transaksi gagal',
                                     'aplikasi lemot',
                                     'aplikasi blank',
                                     'server error',
                                     'fitur tidak jalan'],
             'Streaming dan Gaming Terganggu': ['streaming buffering',
                                                'netflix buffering',
                                                'youtube putus',
                                                'game lag',
                                                'ping merah',
                                                'gaming terganggu',
                                                'mabar putus',
                                                'video macet',
                                                'live streaming patah',
                                                'latency tinggi',
                                                'packet loss'],
             'Teknisi Tidak Tuntas': ['teknisi tidak beres',
                                      'perbaikan tidak tuntas',
                                      'teknisi asal',
                                      'selesai tapi rusak lagi',
                                      'petugas tidak profesional',
                                      'teknisi tidak datang',
                                      'masalah belum selesai',
                                      'perbaikan gagal',
                                      'kabel berantakan',
                                      'teknisi tidak membantu',
                                      'kunjungan sia sia']}}


SENTIMENT_KEYS = {
    "positive": "positive",
    "positif": "positive",
    "label_0": "positive",
    "neutral": "neutral",
    "netral": "neutral",
    "label_1": "neutral",
    "negative": "negative",
    "negatif": "negative",
    "label_2": "negative",
}

SENTIMENT_LABELS_ID = {
    "positive": "Positif",
    "neutral": "Netral",
    "negative": "Negatif",
}

DEFAULT_TOPIC = "Lainnya"

# Alias ini dipertahankan agar halaman lama yang memakai TOPIC_KEYWORDS tetap berjalan.
TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    topic_name: tuple(keywords)
    for sentiment_topics in TOPICS.values()
    for topic_name, keywords in sentiment_topics.items()
}


# Khusus IndiHome, Top 5 Topik memakai keluarga isu lintas sentimen.
# Topik ditentukan dari isi komentar terlebih dahulu, sedangkan label sentimen
# tetap berasal dari predicted_sentiment IndoBERT. Dengan demikian satu isu
# dapat berisi komentar positif, netral, dan negatif secara alami.
INDIHOME_TOPIC_FAMILIES: dict[str, tuple[str, ...]] = {
    "Kecepatan Internet": (
        "Kecepatan Stabil",
        "Streaming Lancar",
        "Gaming Tanpa Lag",
        "Koneksi WFH Andal",
        "Tanya Kecepatan Paket",
        "Kecepatan Lambat",
        "Streaming dan Gaming Terganggu",
    ),
    "Gangguan Jaringan": (
        "Respons Cepat Gangguan",
        "Laporan Gangguan",
        "Pengumuman Maintenance",
        "Gangguan Jaringan",
        "Pemadaman Berulang",
        "Sinyal Hilang",
    ),
    "Bantuan & Layanan Pelanggan": (
        "CS Ramah & Responsif",
        "Pelayanan Profesional",
        "Permintaan Bantuan",
        "Cek Status Pengaduan",
        "CS Lambat/Tidak Responsif",
        "Teknisi Tidak Tuntas",
    ),
    "Harga, Tagihan & Paket": (
        "Promo Menarik",
        "Harga Terjangkau",
        "Paket Lengkap",
        "Pertanyaan Paket",
        "Cek Tagihan",
        "Info Promo",
        "Perbandingan Paket",
        "Tagihan Salah/Bengkak",
        "Harga Mahal",
        "Paket Tidak Sesuai",
        "Kuota Cepat Habis",
    ),
    "Instalasi & Upgrade": (
        "Instalasi Cepat",
        "Upgrade Mudah",
        "Tanya Cara Daftar",
        "Request Upgrade",
        "Tanya Instalasi",
        "Instalasi Lama",
        "Migrasi Rumit",
    ),
    "Coverage & Sinyal": (
        "Coverage Luas",
        "Sinyal Merata",
        "Tanya Coverage Area",
        "Tidak Ada Sinyal Daerah",
    ),
    "Aplikasi & Perangkat": (
        "Fitur Tambahan Bagus",
        "Aplikasi Mudah Digunakan",
        "Tanya Router dan Perangkat",
        "Router Bermasalah",
        "Aplikasi Bermasalah",
    ),
    "Pembayaran & Refund": (
        "Tanya Lokasi Bayar",
        "Konfirmasi Pembayaran",
        "Pemblokiran Layanan",
        "Refund Tidak Jelas",
    ),
}

# Keyword tambahan ini hanya memperkuat variasi bahasa yang umum dipakai pada
# komentar IndiHome. Tidak ada jumlah sentimen yang di-hardcode di sini.
INDIHOME_TOPIC_EXTRA_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Kecepatan Internet": (
        "lemot",
        "lambat",
        "lelet",
        "buffering",
        "loading lama",
        "ngelag",
        "lag",
        "ping",
        "latency",
        "speedtest",
        "mbps",
        "cepat",
        "kencang",
        "lancar",
        "stabil",
    ),
    "Gangguan Jaringan": (
        "gangguan",
        "internet mati",
        "wifi mati",
        "jaringan mati",
        "jaringan putus",
        "koneksi putus",
        "koneksi bermasalah",
        "down",
        "maintenance",
        "pemeliharaan",
        "perbaikan jaringan",
        "normal kembali",
        "sudah normal",
    ),
    "Bantuan & Layanan Pelanggan": (
        "tolong bantu",
        "minta bantuan",
        "mohon bantuan",
        "customer service",
        "cs",
        "admin",
        "pengaduan",
        "laporan",
        "tiket",
        "teknisi",
        "pelayanan",
        "respons",
        "respon",
    ),
    "Harga, Tagihan & Paket": (
        "harga",
        "mahal",
        "murah",
        "paket",
        "promo",
        "diskon",
        "tagihan",
        "billing",
        "biaya",
        "kuota",
        "bundling",
    ),
    "Instalasi & Upgrade": (
        "pasang",
        "pemasangan",
        "instalasi",
        "daftar",
        "upgrade",
        "downgrade",
        "migrasi",
        "ganti paket",
        "naik paket",
    ),
    "Coverage & Sinyal": (
        "coverage",
        "jangkauan",
        "blank spot",
        "tidak ada sinyal",
        "sinyal hilang",
        "sinyal bagus",
        "sinyal kuat",
        "area terjangkau",
    ),
    "Aplikasi & Perangkat": (
        "aplikasi",
        "myindihome",
        "router",
        "modem",
        "perangkat",
        "restart router",
        "lampu modem",
        "login aplikasi",
    ),
    "Pembayaran & Refund": (
        "pembayaran",
        "sudah bayar",
        "bayar di mana",
        "refund",
        "pengembalian dana",
        "terblokir",
        "suspend",
        "diisolir",
    ),
}



# Khusus Telkomsel, Top 5 Topik juga harus dihitung lintas sentimen agar
# kartu Negatif, Netral, dan Positif berasal dari predicted_sentiment asli,
# bukan dari kamus topik yang lebih dulu dikunci oleh sentimen.
TELKOMSEL_TOPIC_FAMILIES: dict[str, tuple[str, ...]] = {
    "Harga Mahal": (
        "Promo Menarik",
        "Harga Terjangkau",
        "Pertanyaan Paket",
        "Info Promo",
        "Perbandingan Paket",
        "Harga Mahal",
        "Paket Tidak Sesuai",
        "Tagihan Salah/Bengkak",
    ),
    "Kecepatan Lambat": (
        "Kecepatan Stabil",
        "Streaming Lancar",
        "Gaming Tanpa Lag",
        "Koneksi WFH Andal",
        "Tanya Kecepatan Paket",
        "Kecepatan Lambat",
        "Streaming dan Gaming Terganggu",
    ),
    "Permintaan Bantuan": (
        "CS Ramah & Responsif",
        "Pelayanan Profesional",
        "Permintaan Bantuan",
        "Cek Status Pengaduan",
        "CS Lambat/Tidak Responsif",
        "Teknisi Tidak Tuntas",
    ),
    "Gangguan Jaringan": (
        "Respons Cepat Gangguan",
        "Laporan Gangguan",
        "Pengumuman Maintenance",
        "Gangguan Jaringan",
        "Pemadaman Berulang",
        "Sinyal Hilang",
        "Tidak Ada Sinyal Daerah",
    ),
    "Tanya Kuota dan Masa Aktif": (
        "Paket Lengkap",
        "Pertanyaan Paket",
        "Tanya Kuota dan Masa Aktif",
        "Konfirmasi Pembayaran",
        "Kuota Cepat Habis",
    ),
    "Aplikasi & Perangkat": (
        "Aplikasi Mudah Digunakan",
        "Fitur Tambahan Bagus",
        "Tanya Router dan Perangkat",
        "Router Bermasalah",
        "Aplikasi Bermasalah",
    ),
    "Pembayaran & Refund": (
        "Tanya Lokasi Bayar",
        "Konfirmasi Pembayaran",
        "Cek Tagihan",
        "Pemblokiran Layanan",
        "Refund Tidak Jelas",
        "Tagihan Salah/Bengkak",
    ),
}

TELKOMSEL_TOPIC_EXTRA_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Harga Mahal": (
        "mahal",
        "kemahalan",
        "terlalu mahal",
        "harga tinggi",
        "boros",
        "nguras",
        "tidak worth it",
        "tarif",
        "biaya",
        "promo",
        "diskon",
        "murah",
        "paket",
        "harga",
    ),
    "Kecepatan Lambat": (
        "lemot",
        "lambat",
        "lelet",
        "buffering",
        "loading lama",
        "ngelag",
        "lag",
        "ping",
        "latency",
        "speed",
        "cepat",
        "kencang",
        "lancar",
        "stabil",
        "internet lambat",
        "jaringan lambat",
    ),
    "Permintaan Bantuan": (
        "tolong",
        "bantu",
        "tolong bantu",
        "minta bantuan",
        "mohon bantuan",
        "admin",
        "cs",
        "customer service",
        "cek dm",
        "dibantu",
        "bantu dong",
        "respon",
        "respons",
        "pelayanan",
        "pengaduan",
        "laporan",
    ),
    "Gangguan Jaringan": (
        "gangguan",
        "sinyal jelek",
        "sinyal bermasalah",
        "tidak bisa nelpon",
        "internet mati",
        "jaringan bermasalah",
        "sinyal hilang",
        "tidak ada sinyal",
        "down",
        "maintenance",
        "pemeliharaan",
        "normal kembali",
        "sudah normal",
        "putus putus",
        "jaringan putus",
    ),
    "Tanya Kuota dan Masa Aktif": (
        "kuota",
        "paket data",
        "masa aktif",
        "sisa kuota",
        "cek kuota",
        "kuota habis",
        "pulsa",
        "perpanjang",
        "aktif sampai",
        "bonus kuota",
        "internet",
    ),
    "Aplikasi & Perangkat": (
        "mytelkomsel",
        "aplikasi",
        "app",
        "otp",
        "login",
        "error",
        "bug",
        "router",
        "modem",
        "perangkat",
    ),
    "Pembayaran & Refund": (
        "pembayaran",
        "bayar",
        "sudah bayar",
        "refund",
        "pengembalian dana",
        "tagihan",
        "invoice",
        "billing",
        "diblokir",
        "terblokir",
        "suspend",
    ),
}

_URL_MENTION_PATTERN = re.compile(r"https?://\S+|www\.\S+|@\w+", re.IGNORECASE)
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\s]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_sentiment(value: Any) -> str:
    """Normalisasi label sentimen menjadi positive, neutral, atau negative."""
    try:
        key = str(value or "").strip().lower().lstrip("'")
        return SENTIMENT_KEYS.get(key, "neutral")
    except Exception:
        return "neutral"


def _resolve_sentiment_dictionary_key(value: Any) -> str | None:
    """Ubah label sentimen menjadi nama kategori pada dictionary TOPICS."""
    try:
        raw_value = str(value or "").strip()
        if not raw_value:
            return None
        normalized = normalize_sentiment(raw_value)
        return SENTIMENT_LABELS_ID.get(normalized)
    except Exception:
        return None


def _normalize_text(value: Any) -> str:
    """Bersihkan teks agar pencocokan keyword konsisten dan aman."""
    try:
        text = str(value or "").lower()
        text = _URL_MENTION_PATTERN.sub(" ", text)
        text = _NON_ALNUM_PATTERN.sub(" ", text)
        return _WHITESPACE_PATTERN.sub(" ", text).strip()
    except Exception:
        return ""


@lru_cache(maxsize=4)
def _normalized_topics(sentiment_key: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Siapkan keyword ternormalisasi untuk satu kategori sentimen."""
    try:
        sentiment_topics = TOPICS.get(sentiment_key, {})
        result: list[tuple[str, tuple[str, ...]]] = []
        for topic_name, keywords in sentiment_topics.items():
            normalized_keywords = tuple(
                keyword
                for keyword in (_normalize_text(item) for item in keywords)
                if keyword
            )
            result.append((topic_name, normalized_keywords))
        return tuple(result)
    except Exception:
        return tuple()


def _iter_candidate_topics(sentiment: Any) -> Iterable[tuple[str, tuple[str, ...]]]:
    """Ambil kandidat topik sesuai sentimen atau seluruh sentimen jika kosong."""
    try:
        sentiment_key = _resolve_sentiment_dictionary_key(sentiment)
        if sentiment_key:
            return _normalized_topics(sentiment_key)

        combined: list[tuple[str, tuple[str, ...]]] = []
        for key in ("Positif", "Netral", "Negatif"):
            combined.extend(_normalized_topics(key))
        return tuple(combined)
    except Exception:
        return tuple()


def _score_topic_prepared(
    token_counts: Counter,
    padded_text: str,
    keywords: tuple[str, ...],
) -> tuple[int, int]:
    """Hitung skor dari token yang sudah disiapkan satu kali per komentar."""
    try:
        if not keywords:
            return 0, 0

        total_score = 0
        matched_keywords = 0
        for keyword in keywords:
            if " " in keyword:
                occurrence = padded_text.count(f" {keyword} ")
                if occurrence:
                    word_count = len(keyword.split())
                    total_score += occurrence * (word_count * 3 + 2)
                    matched_keywords += 1
            else:
                occurrence = int(token_counts.get(keyword, 0))
                if occurrence:
                    total_score += occurrence
                    matched_keywords += 1
        return total_score, matched_keywords
    except Exception:
        return 0, 0


def _score_topic(normalized_text: str, keywords: tuple[str, ...]) -> tuple[int, int]:
    """Hitung skor topik berdasarkan keyword tunggal dan frasa yang cocok."""
    try:
        if not normalized_text or not keywords:
            return 0, 0
        token_counts = Counter(normalized_text.split())
        padded_text = f" {normalized_text} "
        return _score_topic_prepared(token_counts, padded_text, keywords)
    except Exception:
        return 0, 0


@lru_cache(maxsize=50_000)
def _classify_cached(text: str, sentiment: str) -> str:
    """Klasifikasikan teks yang sama tanpa menghitung ulang pada rerun Streamlit."""
    try:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return DEFAULT_TOPIC

        best_topic = DEFAULT_TOPIC
        best_score = 0
        best_matches = 0
        token_counts = Counter(normalized_text.split())
        padded_text = f" {normalized_text} "

        for topic_name, keywords in _iter_candidate_topics(sentiment):
            score, matches = _score_topic_prepared(token_counts, padded_text, keywords)
            if score > best_score or (score == best_score and matches > best_matches):
                best_topic = topic_name
                best_score = score
                best_matches = matches

        return best_topic if best_score > 0 else DEFAULT_TOPIC
    except Exception:
        return DEFAULT_TOPIC


def classify_topic(text: str, sentiment: str) -> str:
    """Tentukan nama topik paling cocok berdasarkan teks dan sentimennya."""
    try:
        return _classify_cached(str(text or ""), str(sentiment or ""))
    except Exception:
        return DEFAULT_TOPIC


def _normalize_topic_family_groups(
    families: dict[str, tuple[str, ...]],
    extra_keywords: dict[str, tuple[str, ...]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Gabungkan keyword keluarga topik lintas sentimen secara deduplikatif."""
    try:
        normalized_groups: list[tuple[str, tuple[str, ...]]] = []
        for family_name, source_topics in families.items():
            keywords: list[str] = []
            seen: set[str] = set()

            for category in ("Positif", "Netral", "Negatif"):
                category_topics = TOPICS.get(category, {})
                for source_topic in source_topics:
                    for keyword in category_topics.get(source_topic, []):
                        normalized = _normalize_text(keyword)
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            keywords.append(normalized)

            for keyword in extra_keywords.get(family_name, ()):
                normalized = _normalize_text(keyword)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    keywords.append(normalized)

            normalized_groups.append((family_name, tuple(keywords)))

        return tuple(normalized_groups)
    except Exception:
        return tuple()


@lru_cache(maxsize=2)
def _normalized_indihome_topics() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Gabungkan keyword topik IndiHome tanpa membatasi kandidat oleh sentimen."""
    try:
        return _normalize_topic_family_groups(
            INDIHOME_TOPIC_FAMILIES,
            INDIHOME_TOPIC_EXTRA_KEYWORDS,
        )
    except Exception:
        return tuple()


@lru_cache(maxsize=2)
def _normalized_telkomsel_topics() -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Gabungkan keyword topik Telkomsel tanpa membatasi kandidat oleh sentimen."""
    try:
        return _normalize_topic_family_groups(
            TELKOMSEL_TOPIC_FAMILIES,
            TELKOMSEL_TOPIC_EXTRA_KEYWORDS,
        )
    except Exception:
        return tuple()


@lru_cache(maxsize=50_000)
def _classify_indihome_cached(text: str) -> str:
    """Klasifikasikan topik IndiHome dari isi teks, independen dari sentimen."""
    try:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return DEFAULT_TOPIC

        best_topic = DEFAULT_TOPIC
        best_score = 0
        best_matches = 0
        token_counts = Counter(normalized_text.split())
        padded_text = f" {normalized_text} "

        for topic_name, keywords in _normalized_indihome_topics():
            score, matches = _score_topic_prepared(token_counts, padded_text, keywords)
            if score > best_score or (score == best_score and matches > best_matches):
                best_topic = topic_name
                best_score = score
                best_matches = matches

        return best_topic if best_score > 0 else DEFAULT_TOPIC
    except Exception:
        return DEFAULT_TOPIC


def classify_indihome_topic(text: str) -> str:
    """Tentukan keluarga isu IndiHome tanpa memakai predicted_sentiment."""
    try:
        return _classify_indihome_cached(str(text or ""))
    except Exception:
        return DEFAULT_TOPIC


def get_indihome_topic_keywords(topic_name: str, limit: int | None = None) -> list[str]:
    """Ambil keyword keluarga isu IndiHome untuk ringkasan Top 5."""
    try:
        target = str(topic_name or "").strip()
        for family_name, keywords in _normalized_indihome_topics():
            if family_name == target:
                values = list(keywords)
                if limit is None:
                    return values
                return values[: max(0, int(limit))]
        return []
    except Exception:
        return []


@lru_cache(maxsize=50_000)
def _classify_telkomsel_cached(text: str) -> str:
    """Klasifikasikan topik Telkomsel dari isi teks, independen dari sentimen."""
    try:
        normalized_text = _normalize_text(text)
        if not normalized_text:
            return DEFAULT_TOPIC

        best_topic = DEFAULT_TOPIC
        best_score = 0
        best_matches = 0
        token_counts = Counter(normalized_text.split())
        padded_text = f" {normalized_text} "

        for topic_name, keywords in _normalized_telkomsel_topics():
            score, matches = _score_topic_prepared(token_counts, padded_text, keywords)
            if score > best_score or (score == best_score and matches > best_matches):
                best_topic = topic_name
                best_score = score
                best_matches = matches

        return best_topic if best_score > 0 else DEFAULT_TOPIC
    except Exception:
        return DEFAULT_TOPIC


def classify_telkomsel_topic(text: str) -> str:
    """Tentukan keluarga isu Telkomsel tanpa memakai predicted_sentiment."""
    try:
        return _classify_telkomsel_cached(str(text or ""))
    except Exception:
        return DEFAULT_TOPIC


def get_telkomsel_topic_keywords(topic_name: str, limit: int | None = None) -> list[str]:
    """Ambil keyword keluarga isu Telkomsel untuk ringkasan Top 5."""
    try:
        target = str(topic_name or "").strip()
        for family_name, keywords in _normalized_telkomsel_topics():
            if family_name == target:
                values = list(keywords)
                if limit is None:
                    return values
                return values[: max(0, int(limit))]
        return []
    except Exception:
        return []


def classify_telkomsel_topics_fast(texts: list[Any]) -> list[str]:
    """Klasifikasikan banyak komentar Telkomsel dengan cache internal."""
    try:
        return [_classify_telkomsel_cached(str(text or "")) for text in list(texts or [])]
    except Exception:
        return [DEFAULT_TOPIC] * len(texts or [])


def apply_telkomsel_topics(
    df: pd.DataFrame,
    text_col: str | None = None,
) -> pd.DataFrame:
    """Tambahkan topik Telkomsel tanpa mengubah label sentimen dari sumber."""
    try:
        if df is None:
            return pd.DataFrame()
        if df.empty:
            return df.copy()

        result = df.copy()
        selected_text_col = text_col or (
            "content_clean" if "content_clean" in result.columns else "content"
        )
        if selected_text_col not in result.columns:
            result["topic"] = DEFAULT_TOPIC
            result["_topic_scope"] = "telkomsel"
            return result

        texts = result[selected_text_col].fillna("").astype(str).tolist()
        result["topic"] = classify_telkomsel_topics_fast(texts)
        result["_topic_scope"] = "telkomsel"
        return result
    except Exception:
        fallback = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        fallback["topic"] = DEFAULT_TOPIC
        fallback["_topic_scope"] = "telkomsel"
        return fallback


def classify_indihome_topics_fast(texts: list[Any]) -> list[str]:
    """Klasifikasikan banyak komentar IndiHome dengan cache internal."""
    try:
        return [_classify_indihome_cached(str(text or "")) for text in list(texts or [])]
    except Exception:
        return [DEFAULT_TOPIC] * len(texts or [])


def apply_indihome_topics(
    df: pd.DataFrame,
    text_col: str | None = None,
) -> pd.DataFrame:
    """Tambahkan topik IndiHome tanpa mengubah label sentimen dari sumber."""
    try:
        if df is None:
            return pd.DataFrame()
        if df.empty:
            return df.copy()

        result = df.copy()
        selected_text_col = text_col or (
            "content_clean" if "content_clean" in result.columns else "content"
        )
        if selected_text_col not in result.columns:
            result["topic"] = DEFAULT_TOPIC
            result["_topic_scope"] = "indihome"
            return result

        texts = result[selected_text_col].fillna("").astype(str).tolist()
        result["topic"] = classify_indihome_topics_fast(texts)
        result["_topic_scope"] = "indihome"
        return result
    except Exception:
        fallback = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        fallback["topic"] = DEFAULT_TOPIC
        fallback["_topic_scope"] = "indihome"
        return fallback


def get_all_topics(sentiment: str) -> list[str]:
    """Ambil semua nama topik yang tersedia untuk satu kategori sentimen."""
    try:
        sentiment_key = _resolve_sentiment_dictionary_key(sentiment)
        if not sentiment_key:
            return []
        return list(TOPICS.get(sentiment_key, {}).keys())
    except Exception:
        return []


def get_topic_keywords(
    topic_name: str,
    sentiment: str | int | None = None,
    limit: int | None = None,
) -> list[str]:
    """Ambil daftar keyword sebuah topik untuk pengecekan dan debugging."""
    try:
        # Kompatibilitas dengan pemanggilan lama get_topic_keywords(topik, 5).
        if isinstance(sentiment, int) and limit is None:
            limit = sentiment
            sentiment = None

        sentiment_key = _resolve_sentiment_dictionary_key(sentiment)
        if sentiment_key:
            keywords = list(TOPICS.get(sentiment_key, {}).get(str(topic_name), []))
        else:
            keywords = []
            for category in ("Positif", "Netral", "Negatif"):
                if str(topic_name) in TOPICS.get(category, {}):
                    keywords = list(TOPICS[category][str(topic_name)])
                    break

        if limit is None:
            return keywords
        return keywords[: max(0, int(limit))]
    except Exception:
        return []


def classify_topics_fast(
    texts: list[Any],
    sentiments: list[Any] | None = None,
) -> list[str]:
    """Klasifikasikan banyak komentar dengan tetap memakai cache internal."""
    try:
        safe_texts = list(texts or [])
        if sentiments is None:
            safe_sentiments = [""] * len(safe_texts)
        else:
            safe_sentiments = list(sentiments)
            if len(safe_sentiments) < len(safe_texts):
                safe_sentiments.extend([""] * (len(safe_texts) - len(safe_sentiments)))

        return [
            _classify_cached(str(text or ""), str(safe_sentiments[index] or ""))
            for index, text in enumerate(safe_texts)
        ]
    except Exception:
        return [DEFAULT_TOPIC] * len(texts or [])


def apply_topics(
    df: pd.DataFrame,
    text_col: str | None = None,
    sentiment_col: str = "predicted_sentiment",
) -> pd.DataFrame:
    """Tambahkan kolom topic pada DataFrame tanpa membuat dashboard crash."""
    try:
        if df is None:
            return pd.DataFrame()
        if df.empty:
            return df.copy()

        result = df.copy()
        selected_text_col = text_col or (
            "content_clean" if "content_clean" in result.columns else "content"
        )
        if selected_text_col not in result.columns:
            result["topic"] = DEFAULT_TOPIC
            return result

        if sentiment_col not in result.columns:
            result[sentiment_col] = ""

        texts = result[selected_text_col].fillna("").astype(str).tolist()
        sentiments = result[sentiment_col].fillna("").astype(str).tolist()
        result["topic"] = classify_topics_fast(texts, sentiments)
        return result
    except Exception:
        fallback = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        fallback["topic"] = DEFAULT_TOPIC
        return fallback


def get_dominant_keywords(
    df: pd.DataFrame,
    topic: str,
    sentimen: str | None = None,
    limit: int = 5,
) -> list[str]:
    """Ambil keyword referensi topik untuk kartu ringkasan dashboard."""
    try:
        del df
        return get_topic_keywords(topic, sentimen, limit=limit)
    except Exception:
        return []


def _dominant_sentiment(series: pd.Series) -> str:
    """Tentukan sentimen dominan dengan urutan tie-break yang konsisten."""
    try:
        normalized = series.map(normalize_sentiment)
        counts = normalized.value_counts()
        if counts.empty:
            return "neutral"
        priority = {"negative": 2, "positive": 1, "neutral": 0}
        return max(
            counts.index,
            key=lambda item: (int(counts[item]), priority.get(item, -1)),
        )
    except Exception:
        return "neutral"


def summarize_topics(df: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    """Ringkas jumlah komentar, persentase, dan contoh komentar per topik."""
    columns = [
        "topik",
        "jumlah_komentar",
        "persentase",
        "sentimen_dominan",
        "contoh_komentar",
        "kata_kunci",
    ]
    try:
        if df is None or df.empty:
            return pd.DataFrame(columns=columns)

        work = df if "topic" in df.columns else apply_topics(df)
        content_col = "content" if "content" in work.columns else "content_clean"
        if content_col not in work.columns:
            work = work.copy()
            work["content"] = ""
            content_col = "content"
        if "predicted_sentiment" not in work.columns:
            work = work.copy()
            work["predicted_sentiment"] = "neutral"

        total = max(len(work), 1)
        rows: list[dict[str, Any]] = []

        for topic_name, group in work.groupby("topic", sort=False, dropna=False):
            topic_label = str(topic_name or DEFAULT_TOPIC)
            count = int(len(group))
            dominant = _dominant_sentiment(group["predicted_sentiment"])

            non_empty = group[content_col].fillna("").astype(str)
            non_empty = non_empty[non_empty.str.strip().ne("")]
            if non_empty.empty:
                example = "—"
            else:
                example = str(non_empty.loc[non_empty.str.len().idxmax()]).strip()
                if len(example) > 220:
                    example = example[:217].rstrip() + "..."

            topic_scope = ""
            if "_topic_scope" in group.columns:
                try:
                    topic_scope = str(group["_topic_scope"].dropna().astype(str).iloc[0]).casefold()
                except Exception:
                    topic_scope = ""

            if topic_scope == "indihome":
                keywords = get_indihome_topic_keywords(topic_label, limit=4)
            elif topic_scope == "telkomsel":
                keywords = get_telkomsel_topic_keywords(topic_label, limit=4)
            else:
                keywords = get_topic_keywords(
                    topic_label,
                    SENTIMENT_LABELS_ID.get(dominant),
                    limit=4,
                )
            rows.append(
                {
                    "topik": topic_label,
                    "jumlah_komentar": count,
                    "persentase": round(count / total * 100, 1),
                    "sentimen_dominan": dominant,
                    "contoh_komentar": example,
                    "kata_kunci": ", ".join(keywords) if keywords else "—",
                }
            )

        return (
            pd.DataFrame(rows, columns=columns)
            .sort_values(["jumlah_komentar", "topik"], ascending=[False, True])
            .head(max(1, int(top_n)))
            .reset_index(drop=True)
        )
    except Exception:
        return pd.DataFrame(columns=columns)


def get_top_topics(
    df: pd.DataFrame,
    sentimen: str = "Semua",
    top_n: int = 5,
) -> pd.DataFrame:
    """Pertahankan API lama untuk mengambil topik teratas pada dashboard."""
    try:
        work = df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        if not work.empty and str(sentimen).lower() not in {"semua", "all", ""}:
            target = normalize_sentiment(sentimen)
            if "predicted_sentiment" in work.columns:
                work = work[
                    work["predicted_sentiment"].map(normalize_sentiment) == target
                ]

        result = summarize_topics(work, top_n=top_n)
        if result.empty:
            return pd.DataFrame(
                columns=["topik", "jumlah_komentar", "pct", "contoh_komentar"]
            )
        return result.rename(columns={"persentase": "pct"})
    except Exception:
        return pd.DataFrame(
            columns=["topik", "jumlah_komentar", "pct", "contoh_komentar"]
        )


def build_topic_platform_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Buat matriks jumlah komentar per platform dan topik untuk heatmap."""
    try:
        if df is None or df.empty:
            return pd.DataFrame()

        work = df if "topic" in df.columns else apply_topics(df)
        if "platform" not in work.columns:
            return pd.DataFrame()

        matrix = pd.crosstab(work["platform"], work["topic"])
        platform_order = [
            item for item in ["twitter", "instagram", "tiktok"] if item in matrix.index
        ]
        remaining = [item for item in matrix.index if item not in platform_order]
        return matrix.reindex(platform_order + remaining).fillna(0).astype(int)
    except Exception:
        return pd.DataFrame()
