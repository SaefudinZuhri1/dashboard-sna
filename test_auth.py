"""Tes sederhana modul auth_utils — jalankan: python test_auth.py"""

from auth.auth_utils import (
    create_user,
    delete_user,
    get_user,
    get_user_stats,
    init_db,
    verify_login,
    verify_password,
)

print("=" * 50)
print("TES AUTH UTILS")
print("=" * 50)

print("\n[1] Inisialisasi database...")
init_db()
print("    OK — database siap")

print("\n[2] Login admin...")
admin = verify_login("admin", "admin123")
if admin:
    print(f"    OK — login admin: {admin['fullname']} (role={admin['role']})")
else:
    print("    GAGAL — admin tidak bisa login")

print("\n[3] Login password salah...")
bad = verify_login("admin", "salah")
print(f"    OK — ditolak" if bad is None else "    GAGAL — seharusnya ditolak")

print("\n[4] Buat user test...")
ok, msg = create_user("User Test", "usertest", "test@mail.com", "password123")
print(f"    {'OK' if ok else 'GAGAL'} — {msg}")

print("\n[5] Duplikat username...")
ok2, msg2 = create_user("User Lain", "usertest", "lain@mail.com", "password123")
print(f"    OK — ditolak: {msg2}" if not ok2 else "    GAGAL — seharusnya ditolak")

print("\n[6] Statistik user...")
stats = get_user_stats()
print(f"    Total: {stats['total_users']} | Admin: {stats['total_admin']} | User: {stats['total_regular']}")
print(f"    Terbaru: {stats['latest_user']}")

print("\n[7] Verifikasi password...")
user = get_user("usertest")
if user and verify_password("password123", user["password_hash"]):
    print("    OK — password cocok")
else:
    print("    GAGAL — password tidak cocok")

print("\n[8] Hapus user test...")
if user:
    ok3, msg3 = delete_user(user["user_id"])
    print(f"    {'OK' if ok3 else 'GAGAL'} — {msg3}")

print("\n[9] Coba hapus admin utama...")
ok4, msg4 = delete_user(1)
print(f"    OK — ditolak: {msg4}" if not ok4 else "    GAGAL — admin tidak boleh dihapus")

print("\n" + "=" * 50)
print("SELESAI")
print("=" * 50)
