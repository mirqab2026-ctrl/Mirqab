"""
قاعدة بيانات SQLite للنظام
==========================
الجداول:
- people: الأشخاص المسجّلون
- vehicles: المركبات المسجّلة
- face_encodings: ترميزات الوجه (512-d ArcFace، أو 128-d dlib قديمة)
- access_logs: سجل الدخول والمحاولات
- settings: إعدادات النظام
"""
import sqlite3
import json
import os
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
import random

DB_PATH = Path(__file__).parent.parent / "data" / "gate.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _plate_canonical(plate_text: str) -> str:
    """يحوّل نص اللوحة إلى الشكل القياسي (canonical) المستخدم في المطابقة.

    يستعمل backend.plate_normalizer إن توفّر، وإلا fallback بسيط.
    """
    if not plate_text:
        return ""
    try:
        from backend.plate_normalizer import to_canonical
        return to_canonical(plate_text)
    except ImportError:
        return plate_text.replace(" ", "").upper()


@contextmanager
def get_conn():
    """Context manager لاتصال قاعدة البيانات."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    # SQLite يتجاهل قيود FOREIGN KEY (ومنها ON DELETE CASCADE) ما لم تُفعَّل
    # لكل اتصال على حدة. بدونها يبقى حذف شخص دون حذف بصماته/تفويضاته (بيانات يتيمة).
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """إنشاء الجداول إذا لم تكن موجودة."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            national_id TEXT UNIQUE,
            department TEXT,
            access_level TEXT DEFAULT 'Staff', -- Staff, VIP, Visitor, Suspended
            phone TEXT,
            photo_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_text TEXT UNIQUE NOT NULL,
            plate_canonical TEXT, -- الشكل القياسي للمطابقة السريعة (مفهرس)
            plate_arabic TEXT,
            owner_id INTEGER,
            make TEXT,
            model TEXT,
            color TEXT,
            status TEXT DEFAULT 'Active', -- Active, VIP, Suspended, Review
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES people(id)
        );

        CREATE TABLE IF NOT EXISTS face_encodings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            encoding BLOB NOT NULL, -- numpy array as bytes
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            plate_text TEXT,
            plate_confidence REAL,
            person_id INTEGER,
            face_confidence REAL,
            decision TEXT, -- GRANTED, DENIED, PENDING
            reason TEXT,
            mode TEXT,
            processing_ms INTEGER,
            FOREIGN KEY (person_id) REFERENCES people(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS vehicle_authorizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            person_id INTEGER NOT NULL,
            relationship TEXT DEFAULT 'authorized',
                -- 'owner', 'family', 'employee', 'authorized', 'temporary'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE CASCADE,
            FOREIGN KEY (person_id) REFERENCES people(id) ON DELETE CASCADE,
            UNIQUE(vehicle_id, person_id)
        );

        CREATE INDEX IF NOT EXISTS idx_logs_ts ON access_logs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(plate_text);
        CREATE INDEX IF NOT EXISTS idx_auth_vehicle ON vehicle_authorizations(vehicle_id);
        CREATE INDEX IF NOT EXISTS idx_auth_person ON vehicle_authorizations(person_id);
        """)

    # ترحيل: إضافة عمود plate_canonical للقواعد القديمة + إعادة احتساب القيم.
    _migrate_plate_canonical()


def _migrate_plate_canonical():
    """يضمن وجود عمود plate_canonical في جدول vehicles وملأه + فهرسته.

    آمن للاستدعاء المتكرّر (idempotent): يتخطّى ما هو مكتمل أصلاً.
    """
    with get_conn() as conn:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(vehicles)").fetchall()]
        if "plate_canonical" not in cols:
            conn.execute("ALTER TABLE vehicles ADD COLUMN plate_canonical TEXT")
        # املأ أي صف ناقص قيمته (NULL أو فارغ)
        rows = conn.execute(
            "SELECT id, plate_text FROM vehicles "
            "WHERE plate_canonical IS NULL OR plate_canonical = ''"
        ).fetchall()
        for r in rows:
            conn.execute(
                "UPDATE vehicles SET plate_canonical=? WHERE id=?",
                (_plate_canonical(r["plate_text"]), r["id"]),
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vehicles_canonical "
            "ON vehicles(plate_canonical)"
        )


# ============== People ==============
def add_person(name, national_id, department, access_level="Staff",
               phone="", photo_path=""):
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO people (name, national_id, department, access_level, phone, photo_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, national_id, department, access_level, phone, photo_path))
        return cur.lastrowid


def get_people(active_only=True):
    with get_conn() as conn:
        q = "SELECT * FROM people"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY name"
        return [dict(r) for r in conn.execute(q).fetchall()]


def get_person(person_id):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()
        return dict(r) if r else None


_PERSON_UPDATABLE_COLS = {
    "name", "national_id", "department", "access_level",
    "phone", "photo_path", "active",
}


def update_person(person_id, **fields):
    if not fields:
        return
    # قائمة بيضاء لأسماء الأعمدة لمنع حقن SQL عبر اسم العمود
    invalid = set(fields) - _PERSON_UPDATABLE_COLS
    if invalid:
        raise ValueError(f"أعمدة غير مسموح بتحديثها: {', '.join(sorted(invalid))}")
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [person_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE people SET {cols} WHERE id=?", vals)


# ============== Vehicles ==============
def add_vehicle(plate_text, owner_id, make, model, color="",
                status="Active", plate_arabic=""):
    canonical = _plate_canonical(plate_text)
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO vehicles
              (plate_text, plate_canonical, plate_arabic, owner_id, make, model, color, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (plate_text, canonical, plate_arabic, owner_id, make, model, color, status))
        return cur.lastrowid


_VEHICLE_UPDATABLE_COLS = {
    "plate_text", "plate_arabic", "owner_id", "make",
    "model", "color", "status",
}


def update_vehicle(vehicle_id, **fields):
    """تحديث بيانات مركبة مع إبقاء plate_canonical متزامناً مع plate_text."""
    if not fields:
        return
    # قائمة بيضاء لأسماء الأعمدة لمنع حقن SQL عبر اسم العمود
    invalid = set(fields) - _VEHICLE_UPDATABLE_COLS
    if invalid:
        raise ValueError(f"أعمدة غير مسموح بتحديثها: {', '.join(sorted(invalid))}")
    # عند تغيّر نص اللوحة، أعد احتساب الشكل القياسي تلقائياً
    if "plate_text" in fields:
        fields["plate_canonical"] = _plate_canonical(fields["plate_text"])
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [vehicle_id]
    with get_conn() as conn:
        conn.execute(f"UPDATE vehicles SET {cols} WHERE id=?", vals)


def add_or_update_vehicle(plate_text, owner_id=None, make="", model="",
                          color="", status="Active", plate_arabic=""):
    """يضيف المركبة، أو **يحدّثها** إن كانت لوحتها (الشكل القياسي) موجودة.

    يمنع خطأ UNIQUE عند إعادة حفظ لوحة مسجّلة (مفيد للتجارب).
    يُرجع (vehicle_id, created) حيث created=True إن أُنشئت جديدة.
    """
    canonical = _plate_canonical(plate_text)
    existing_id = None
    if canonical:
        with get_conn() as conn:
            r = conn.execute(
                "SELECT id FROM vehicles WHERE plate_canonical=?", (canonical,)
            ).fetchone()
            existing_id = r["id"] if r else None
    if existing_id:
        update_vehicle(existing_id, plate_text=plate_text, plate_arabic=plate_arabic,
                       owner_id=owner_id, make=make, model=model,
                       color=color, status=status)
        return existing_id, False
    return add_vehicle(plate_text, owner_id, make, model, color, status, plate_arabic), True


def get_vehicles_with_owners():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT v.*, p.name as owner_name, p.access_level
            FROM vehicles v
            LEFT JOIN people p ON v.owner_id = p.id
            ORDER BY v.plate_text
        """).fetchall()
        return [dict(r) for r in rows]


def find_vehicle_by_plate(plate_text):
    """يبحث عن مركبة بـ plate text — يستخدم canonical للمطابقة الدقيقة.

    يقبل أي إدخال (EN/AR/مختلط/بمسافات) ويحوّله إلى canonical قبل المقارنة.
    كذلك يحوّل القيم المخزّنة إلى canonical لمعالجة البيانات القديمة.
    """
    query_canonical = _plate_canonical(plate_text)
    if not query_canonical:
        return None

    with get_conn() as conn:
        # مطابقة مفهرسة مباشرة على العمود القياسي بدل مسح كامل الجدول.
        r = conn.execute(
            "SELECT * FROM vehicles WHERE plate_canonical=?",
            (query_canonical,),
        ).fetchone()
        return dict(r) if r else None


# ============== Vehicle Authorizations ==============
def add_vehicle_authorization(vehicle_id, person_id,
                               relationship="authorized", notes=""):
    """يربط شخصاً بمركبة (سائق معتمد)."""
    with get_conn() as conn:
        try:
            cur = conn.execute("""
                INSERT INTO vehicle_authorizations
                  (vehicle_id, person_id, relationship, notes)
                VALUES (?, ?, ?, ?)
            """, (vehicle_id, person_id, relationship, notes))
            return cur.lastrowid
        except sqlite3.IntegrityError:
            # موجود بالفعل
            return None


def get_authorized_persons(vehicle_id):
    """يعيد قائمة الأشخاص المعتمدين لقيادة هذه المركبة (المالك + الآخرون)."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.*, va.relationship as auth_relationship, va.notes as auth_notes
            FROM people p
            JOIN vehicle_authorizations va ON p.id = va.person_id
            WHERE va.vehicle_id = ? AND p.active = 1
            UNION
            SELECT p.*, 'owner' as auth_relationship, '' as auth_notes
            FROM people p
            JOIN vehicles v ON p.id = v.owner_id
            WHERE v.id = ? AND p.active = 1
        """, (vehicle_id, vehicle_id)).fetchall()
        return [dict(r) for r in rows]


def is_person_authorized_for_vehicle(person_id, vehicle_id):
    """يفحص إذا كان الشخص مسموح له قيادة المركبة (مالك أو معتمد)."""
    with get_conn() as conn:
        # تحقق من المالك
        r = conn.execute("SELECT 1 FROM vehicles WHERE id=? AND owner_id=?",
                          (vehicle_id, person_id)).fetchone()
        if r:
            return True, "owner"
        # تحقق من الـ authorizations
        r = conn.execute("""
            SELECT relationship FROM vehicle_authorizations
            WHERE vehicle_id=? AND person_id=?
        """, (vehicle_id, person_id)).fetchone()
        if r:
            return True, r["relationship"]
        return False, None


def remove_authorization(vehicle_id, person_id):
    with get_conn() as conn:
        conn.execute("""
            DELETE FROM vehicle_authorizations
            WHERE vehicle_id=? AND person_id=?
        """, (vehicle_id, person_id))


# ============== Face Encodings ==============
def add_face_encoding(person_id, encoding: np.ndarray):
    blob = encoding.astype(np.float32).tobytes()
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO face_encodings (person_id, encoding) VALUES (?, ?)
        """, (person_id, blob))


def get_all_face_encodings():
    """يعيد قائمة [(person_id, encoding_np_array), ...]"""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT person_id, encoding FROM face_encodings
        """).fetchall()
        result = []
        for r in rows:
            enc = np.frombuffer(r["encoding"], dtype=np.float32)
            result.append((r["person_id"], enc))
        return result


def get_face_count(person_id):
    with get_conn() as conn:
        r = conn.execute("SELECT COUNT(*) as c FROM face_encodings WHERE person_id=?",
                          (person_id,)).fetchone()
        return r["c"]


def delete_person_faces(person_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM face_encodings WHERE person_id=?", (person_id,))


# ============== Access Logs ==============
def add_log(plate_text=None, plate_confidence=None, person_id=None,
            face_confidence=None, decision="DENIED", reason="",
            mode="balanced", processing_ms=0):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO access_logs
              (plate_text, plate_confidence, person_id, face_confidence,
               decision, reason, mode, processing_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (plate_text, plate_confidence, person_id, face_confidence,
              decision, reason, mode, processing_ms))


def get_recent_logs(limit=50):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT l.*, p.name as person_name
            FROM access_logs l
            LEFT JOIN people p ON l.person_id = p.id
            ORDER BY l.timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_stats():
    """إحصائيات سريعة لـ Dashboard."""
    with get_conn() as conn:
        today = datetime.now().strftime("%Y-%m-%d")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp)=?", (today,))
        today_total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp)=? AND decision='GRANTED'", (today,))
        today_granted = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp)=? AND decision='DENIED'", (today,))
        today_denied = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp)=? AND decision='PENDING'", (today,))
        today_pending = c.fetchone()[0]
        accuracy = (today_granted / today_total * 100) if today_total > 0 else 0
        return {
            "today_total": today_total,
            "today_granted": today_granted,
            "today_denied": today_denied,
            "today_pending": today_pending,
            "accuracy": round(accuracy, 1),
        }


def get_logs_by_day(days=30):
    """عدد دخول يومي للـ trend chart."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT DATE(timestamp) as day,
                   COUNT(*) as total,
                   SUM(CASE WHEN decision='GRANTED' THEN 1 ELSE 0 END) as granted,
                   SUM(CASE WHEN decision='DENIED' THEN 1 ELSE 0 END) as denied
            FROM access_logs
            WHERE timestamp >= DATE('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY day
        """, (f"-{days} days",)).fetchall()
        return [dict(r) for r in rows]


# ============== Settings ==============
def get_setting(key, default=None):
    with get_conn() as conn:
        r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if r:
            try:
                return json.loads(r["value"])
            except Exception:
                return r["value"]
        return default


def set_setting(key, value):
    val = json.dumps(value) if not isinstance(value, str) else value
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=?
        """, (key, val, val))


# ============== Seed Data ==============
def seed_db():
    """يملأ القاعدة ببيانات تجريبية واقعية للعرض."""
    init_db()
    with get_conn() as conn:
        # تنظيف
        conn.executescript("""
            DELETE FROM access_logs;
            DELETE FROM face_encodings;
            DELETE FROM vehicles;
            DELETE FROM people;
        """)

    # أشخاص واقعيون من المشروع المرجعي
    people_data = [
        ("Ahmed Al-Saudi", "1023456001", "Engineering", "Staff", "+966501234567"),
        ("Sara Al-Otaibi", "1023456002", "Marketing", "Staff", "+966502345678"),
        ("Faisal Al-Qahtani", "1023456003", "Operations", "Staff", "+966503456789"),
        ("Noura Al-Harbi", "1023456004", "Executive", "VIP", "+966504567890"),
        ("Khalid Al-Mutairi", "1023456005", "IT", "Staff", "+966505678901"),
        ("Reem Al-Anazi", "1023456006", "Marketing", "Visitor", "+966506789012"),
        ("Abdullah Al-Ghamdi", "1023456007", "Security", "Staff", "+966507890123"),
        ("Mohammed Al-Ahmadi", "1023456008", "Engineering", "Staff", "+966508901234"),
        ("Hessa Al-Dosari", "1023456009", "Executive", "VIP", "+966509012345"),
        ("Turki Al-Shahrani", "1023456010", "IT", "Staff", "+966500123456"),
    ]
    person_ids = []
    for name, nid, dept, lvl, phone in people_data:
        pid = add_person(name, nid, dept, lvl, phone)
        person_ids.append(pid)

    # مركبات بلوحات سعودية (وفق المعيار السعودي SASO)
    # ملاحظة: حروف اللوحات الرسمية: A,B,D,E,G,H,J,K,L,N,R,S,T,U,V,X,Z
    # J→ح, U→و, V→ى, X→ص, Z→م, G→ق
    vehicles_data = [
        # plate_text, owner_idx, make, model, color, status, plate_arabic
        ("2040 LBS", 0, "Toyota", "Camry", "Silver", "VIP", "٢٠٤٠ ل ب س"),
        ("9821 KAA", 1, "Hyundai", "Tucson", "White", "Active", "٩٨٢١ ك ا ا"),
        ("3104 EJD", 3, "Lexus", "LX 600", "Black", "VIP", "٣١٠٤ ع ح د"),
        ("5511 BVR", 2, "Ford", "F-150", "Red", "Review", "٥٥١١ ب ى ر"),
        ("4421 DDG", 4, "Honda", "Accord", "Blue", "Suspended", "٤٤٢١ د د ق"),
        ("1879 NHZ", 5, "Nissan", "Patrol", "White", "Active", "١٨٧٩ ن ه م"),
        ("6240 VKJ", 6, "Toyota", "Corolla", "Silver", "Active", "٦٢٤٠ ى ك ح"),
        ("3702 GHD", 7, "Kia", "Sportage", "Gray", "Active", "٣٧٠٢ ق ه د"),
        ("4231 BGD", 8, "BMW", "X5", "Black", "VIP", "٤٢٣١ ب ق د"),
        ("5543 NSA", 9, "Mercedes", "GLC", "White", "Active", "٥٥٤٣ ن س ا"),
    ]
    for plate, oidx, make, model, color, status, plate_ar in vehicles_data:
        add_vehicle(plate, person_ids[oidx], make, model, color, status, plate_ar)

    # سجلات دخول واقعية (30 يوم تاريخ + اليوم)
    random.seed(42)
    statuses = ["GRANTED"] * 18 + ["DENIED"] * 2 + ["PENDING"] * 1 # نسبة 85/10/5
    plates = ["2040 LBS", "9821 KAA", "3104 EJD", "6240 VKJ", "3702 GHD",
              "4231 BGD", "5543 NSA", "1879 NHZ", "5511 BVR"]
    mode_options = ["strict", "balanced", "balanced", "balanced", "demo"]

    with get_conn() as conn:
        # سجلات تاريخية (30 يوم)
        for days_ago in range(30, 0, -1):
            base = datetime.now() - timedelta(days=days_ago)
            n_today = random.randint(100, 220)
            for _ in range(n_today):
                ts = base + timedelta(hours=random.randint(6, 22),
                                       minutes=random.randint(0, 59))
                decision = random.choice(statuses)
                plate = random.choice(plates)
                conn.execute("""
                    INSERT INTO access_logs (timestamp, plate_text, plate_confidence,
                      person_id, face_confidence, decision, reason, mode, processing_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ts.strftime("%Y-%m-%d %H:%M:%S"),
                    plate, round(random.uniform(0.85, 0.98), 3),
                    random.choice(person_ids) if decision == "GRANTED" else None,
                    round(random.uniform(0.75, 0.97), 3) if decision == "GRANTED" else None,
                    decision,
                    "" if decision == "GRANTED" else ("Low confidence" if decision == "PENDING" else "No match"),
                    random.choice(mode_options),
                    random.randint(450, 850)
                ))

        # سجلات اليوم - قليلة لمحاكاة الـ live system
        today_n = random.randint(8, 12)
        for _ in range(today_n):
            ts = datetime.now() - timedelta(minutes=random.randint(0, 600))
            decision = random.choice(statuses)
            plate = random.choice(plates)
            conn.execute("""
                INSERT INTO access_logs (timestamp, plate_text, plate_confidence,
                  person_id, face_confidence, decision, reason, mode, processing_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts.strftime("%Y-%m-%d %H:%M:%S"),
                plate, round(random.uniform(0.85, 0.98), 3),
                random.choice(person_ids) if decision == "GRANTED" else None,
                round(random.uniform(0.75, 0.97), 3) if decision == "GRANTED" else None,
                decision,
                "" if decision == "GRANTED" else ("Low conf" if decision == "PENDING" else "No match"),
                random.choice(["normal","manual","auto"]),
                random.randint(80, 350),
            ))
        conn.commit()
        total_logs = conn.execute("SELECT COUNT(*) FROM access_logs").fetchone()[0]
        print(f"Seeded {total_logs} access logs")
        return total_logs


# ============== ضمان وجود المخطط عند الاستيراد ==============
# يُنشئ الجداول (settings وغيرها) تلقائياً عند أول استيراد للوحدة.
# CREATE TABLE IF NOT EXISTS متكرر الاستدعاء وآمن، فلا يحذف أي بيانات.
try:
    init_db()
except Exception as _init_err:  # pragma: no cover
    import sys as _sys
    print(f"[database] init_db on import failed: {_init_err}", file=_sys.stderr)
