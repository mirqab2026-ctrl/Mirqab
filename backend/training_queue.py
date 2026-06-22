"""
Training Queue
==============
يحفظ التصحيحات اليدوية للقراءات المخطئة لاستخدامها لاحقاً في إعادة تدريب النموذج.
كل تصحيح يحفظ:
- النص الذي قرأه النموذج (OCR output)
- النص الصحيح من المستخدم (ground truth)
- صورة اللوحة المقصوصة (للتدريب المستقبلي)
- ملاحظات + معلومات التصحيح
"""
import json
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from . import database as db


QUEUE_IMG_DIR = Path(__file__).parent.parent / "data" / "training_queue_images"
QUEUE_IMG_DIR.mkdir(parents=True, exist_ok=True)


def init_training_queue():
    """ينشئ جدول training_queue إذا لم يكن موجوداً."""
    with db.get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS training_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ocr_text TEXT, -- النص الذي قرأه النموذج
            corrected_text TEXT, -- النص الصحيح من المستخدم
            avg_confidence REAL,
            image_path TEXT, -- مسار صورة اللوحة المقصوصة
            issues TEXT, -- مشاكل التحقق (JSON)
            user_action TEXT, -- 'confirmed', 'corrected', 'rejected'
            status TEXT DEFAULT 'pending', -- 'pending', 'used_in_training', 'archived'
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tq_status ON training_queue(status);
        CREATE INDEX IF NOT EXISTS idx_tq_action ON training_queue(user_action);
        """)


def add_to_queue(
    ocr_text: str,
    corrected_text: str,
    plate_crop_img: np.ndarray,
    avg_confidence: float,
    issues: list,
    user_action: str = "corrected",
    notes: str = "",
) -> int:
    """
    يضيف تصحيحاً للقائمة.

    user_action:
    - "confirmed": المستخدم أكّد أن قراءة النموذج صحيحة
    - "corrected": المستخدم صحّح النص
    - "rejected": المستخدم رفض القراءة (لوحة سيئة)
    """
    init_training_queue()

    # حفظ صورة اللوحة المقصوصة
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    img_filename = f"plate_{timestamp}.jpg"
    img_path = QUEUE_IMG_DIR / img_filename
    rel_path = None
    if plate_crop_img is not None and plate_crop_img.size > 0:
        if cv2.imwrite(str(img_path), plate_crop_img):
            rel_path = str(img_path.relative_to(Path(__file__).parent.parent))

    issues_json = json.dumps(issues, ensure_ascii=False)

    with db.get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO training_queue
              (ocr_text, corrected_text, avg_confidence, image_path,
               issues, user_action, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ocr_text, corrected_text, avg_confidence, rel_path,
              issues_json, user_action, notes))
        return cur.lastrowid


def get_queue(status="pending", limit=200):
    """يجلب التصحيحات المُعلَّقة."""
    init_training_queue()
    # تأمين الـ limit كعدد صحيح موجب لمنع الحقن
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 200
    with db.get_conn() as conn:
        q = "SELECT * FROM training_queue"
        params = []
        if status:
            q += " WHERE status=?"
            params.append(status)
        q += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["issues"] = json.loads(d.get("issues", "[]"))
            except Exception:
                d["issues"] = []
            result.append(d)
        return result


def get_queue_stats():
    init_training_queue()
    with db.get_conn() as conn:
        rows = conn.execute("""
            SELECT user_action, status, COUNT(*) as cnt
            FROM training_queue
            GROUP BY user_action, status
        """).fetchall()
        return [dict(r) for r in rows]


def update_status(item_id: int, status: str):
    with db.get_conn() as conn:
        conn.execute("UPDATE training_queue SET status=? WHERE id=?",
                      (status, item_id))


def delete_item(item_id: int):
    with db.get_conn() as conn:
        # احذف الصورة أيضاً
        r = conn.execute("SELECT image_path FROM training_queue WHERE id=?",
                          (item_id,)).fetchone()
        if r:
            img_path = Path(__file__).parent.parent / r["image_path"]
            if img_path.exists():
                try:
                    img_path.unlink()
                except OSError:
                    pass
        conn.execute("DELETE FROM training_queue WHERE id=?", (item_id,))


def export_for_training(output_dir: Path):
    """
    يصدّر البيانات بصيغة YOLO جاهزة لإعادة التدريب.
    يستخدم corrected_text كـ ground truth.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(exist_ok=True)
    (output_dir / "annotations").mkdir(exist_ok=True)

    items = get_queue(status="pending", limit=10000)
    exported = 0
    for item in items:
        if not item.get("corrected_text"):
            continue
        src_img = Path(__file__).parent.parent / item["image_path"]
        if not src_img.exists():
            continue

        # انسخ الصورة
        import shutil
        dst_img = output_dir / "images" / src_img.name
        shutil.copy(src_img, dst_img)

        # احفظ ground truth كنص
        gt_file = output_dir / "annotations" / (src_img.stem + ".txt")
        with open(gt_file, "w", encoding="utf-8") as f:
            f.write(item["corrected_text"])

        exported += 1

    return exported
