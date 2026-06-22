# -*- coding: utf-8 -*-
"""
ترحيل ترميزات الوجه إلى محرك ONNX الجديد (128-d → 512-d)
==========================================================
يعيد تشفير وجوه كل الأشخاص من صورهم المخزنة باستخدام المحرك الجديد
(buffalo_s)، ويستبدل الترميزات القديمة في قاعدة البيانات.

مصادر الصور لكل شخص:
  1) حقل photo_path في جدول people
  2) كل الصور في data/faces/<person_id>/

الاستخدام:
    python scripts/migrate_face_encodings.py            # تنفيذ فعلي
    python scripts/migrate_face_encodings.py --dry-run  # عرض فقط دون تعديل
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend import database as db                      # noqa: E402
from backend.face_module import get_face_module         # noqa: E402
from backend.config import EMBEDDING_DIM_ONNX           # noqa: E402

FACES_DIR = ROOT / "data" / "faces"
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def person_image_paths(person: dict) -> list:
    """يجمع كل مسارات الصور المعروفة لهذا الشخص."""
    paths = []
    photo = (person.get("photo_path") or "").strip()
    if photo:
        p = Path(photo)
        if not p.is_absolute():
            p = ROOT / p
        if p.exists():
            paths.append(p)
    pid_dir = FACES_DIR / str(person["id"])
    if pid_dir.exists():
        paths.extend(sorted(
            f for f in pid_dir.iterdir() if f.suffix.lower() in IMG_EXTS))
    # إزالة التكرار مع حفظ الترتيب
    seen, unique = set(), []
    for p in paths:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def main():
    dry_run = "--dry-run" in sys.argv

    fm = get_face_module()
    if fm.backend != "onnx":
        print(f"خطأ: المحرك النشط هو '{fm.backend}' وليس onnx.")
        print("تأكد من: pip install onnxruntime ثم python scripts/setup_face_models.py")
        return 1

    db.init_db()
    people = db.get_people()
    print(f"المحرك: onnx (512-d) | عدد الأشخاص: {len(people)}"
          f"{' | وضع المعاينة (dry-run)' if dry_run else ''}")
    print("-" * 60)

    ok_people = no_images = no_face = 0
    total_encodings = 0

    for person in people:
        pid = person["id"]
        name = person.get("name", f"#{pid}")
        images = person_image_paths(person)
        if not images:
            no_images += 1
            print(f"  ⚠ {name}: لا توجد صور — تُحذف ترميزاته القديمة فقط")
            if not dry_run:
                db.delete_person_faces(pid)
            continue

        encodings = []
        for img_path in images:
            enc = fm.encode_image_path(img_path)
            if enc is not None and len(enc) == EMBEDDING_DIM_ONNX:
                encodings.append(enc)

        if not encodings:
            no_face += 1
            print(f"  ✗ {name}: {len(images)} صورة لكن لم يُكشف وجه في أي منها")
            continue

        if not dry_run:
            db.delete_person_faces(pid)
            for enc in encodings:
                db.add_face_encoding(pid, enc)
        ok_people += 1
        total_encodings += len(encodings)
        print(f"  ✓ {name}: {len(encodings)}/{len(images)} ترميز جديد")

    print("-" * 60)
    print(f"اكتمل الترحيل: {ok_people} شخص ({total_encodings} ترميز) | "
          f"بلا صور: {no_images} | بلا وجه مكتشف: {no_face}")
    if dry_run:
        print("لم يُعدَّل شيء (dry-run). أعد التشغيل بدون --dry-run للتنفيذ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
