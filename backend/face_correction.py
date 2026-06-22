"""
Face Correction & Active Learning
==================================
دوال لتأكيد/تصحيح/تحسين التعرف على الوجه:

1. confirm_face_match: المستخدم يؤكّد أن الوجه يطابق الشخص المقترح
   → نضيف encoding جديد لتقوية تعرّف النموذج على هذا الشخص

2. correct_face_match: المستخدم يصحّح ويختار شخصاً مختلفاً
   → نضيف encoding للشخص الصحيح + نسجّل الـ correction

3. register_new_face: تسجيل شخص جديد كلياً من هذا الوجه
   → ينشئ شخصاً جديداً + يضيف encoding

4. link_person_to_vehicle: يربط شخصاً (سائق معتمد) بمركبة
   → يضيف entry في vehicle_authorizations
"""
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from . import database as db
from . import training_queue as tq


FACES_DIR = Path(__file__).parent.parent / "data" / "faces"
FACES_DIR.mkdir(parents=True, exist_ok=True)


def _save_face_image(person_id: int, face_img: np.ndarray) -> str:
    """يحفظ صورة وجه ويعيد المسار."""
    # يجب أن يكون person_id عدداً صحيحاً موجباً لمنع المسارات الخبيثة (path traversal)
    try:
        pid = int(person_id)
    except (TypeError, ValueError):
        raise ValueError(f"person_id غير صالح: {person_id!r}")
    if pid <= 0:
        raise ValueError(f"person_id يجب أن يكون موجباً: {pid}")

    person_dir = FACES_DIR / str(pid)
    person_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"face_{timestamp}.jpg"
    full_path = person_dir / filename
    if not cv2.imwrite(str(full_path), face_img):
        raise IOError(f"تعذّر حفظ صورة الوجه إلى: {full_path}")
    return str(full_path.relative_to(Path(__file__).parent.parent))


def confirm_face_match(person_id: int,
                       face_img: np.ndarray,
                       encoding: np.ndarray) -> Dict:
    """
    تأكيد أن الوجه يطابق الشخص.
    يضيف encoding للشخص لتحسين تعرّفه مستقبلاً.
    """
    person = db.get_person(person_id)
    if person is None:
        return {"success": False, "error": f"لا يوجد شخص بالمعرّف {person_id}"}

    if encoding is not None:
        db.add_face_encoding(person_id, encoding)

    if face_img is not None and face_img.size > 0:
        _save_face_image(person_id, face_img)

    n_total = db.get_face_count(person_id)

    return {
        "success": True,
        "person": person,
        "total_encodings": n_total,
        "message": f"تم تأكيد التعرّف على {person['name']} وإضافة encoding جديد",
    }


def correct_face_match(correct_person_id: int,
                       wrong_person_id: Optional[int],
                       face_img: np.ndarray,
                       encoding: np.ndarray,
                       wrong_confidence: float = 0.0) -> Dict:
    """
    تصحيح: الوجه يطابق شخصاً مختلفاً.
    - يضيف encoding للشخص الصحيح
    - يحفظ سجل التصحيح في training_queue للتحليل
    """
    correct_person = db.get_person(correct_person_id)
    if correct_person is None:
        return {"success": False, "error": f"لا يوجد شخص بالمعرّف {correct_person_id}"}

    if encoding is not None:
        db.add_face_encoding(correct_person_id, encoding)

    if face_img is not None and face_img.size > 0:
        _save_face_image(correct_person_id, face_img)

    # سجّل التصحيح
    tq.init_training_queue()
    wrong_person = db.get_person(wrong_person_id) if wrong_person_id else None

    notes = (f"Face correction: was identified as "
             f"{wrong_person['name'] if wrong_person else 'unknown'} "
             f"(conf={wrong_confidence:.2f}), corrected to {correct_person['name']}")

    tq.add_to_queue(
        ocr_text=f"face_{wrong_person_id or 'unknown'}",
        corrected_text=f"face_{correct_person_id}",
        plate_crop_img=face_img,
        avg_confidence=wrong_confidence,
        issues=["Face mismatch corrected by user"],
        user_action="corrected",
        notes=notes
    )

    return {
        "success": True,
        "correct_person": correct_person,
        "wrong_person": wrong_person,
        "message": f"تم تصحيح التعرّف إلى {correct_person['name']}",
    }


def register_new_face(name: str,
                      national_id: str,
                      department: str,
                      access_level: str,
                      face_img: np.ndarray,
                      encoding: np.ndarray,
                      phone: str = "") -> Dict:
    """
    تسجيل شخص جديد من الوجه المكتشف.
    """
    try:
        person_id = db.add_person(name, national_id, department,
                                    access_level, phone)
    except Exception as e:
        return {"success": False, "error": f"خطأ في الإنشاء: {e}"}

    if encoding is not None:
        db.add_face_encoding(person_id, encoding)

    photo_path = ""
    if face_img is not None and face_img.size > 0:
        photo_path = _save_face_image(person_id, face_img)
        db.update_person(person_id, photo_path=photo_path)

    return {
        "success": True,
        "person_id": person_id,
        "message": f"تم تسجيل {name} بنجاح",
    }


def link_person_to_vehicle(vehicle_id: int,
                            person_id: int,
                            relationship: str = "authorized",
                            notes: str = "") -> Dict:
    """
    يربط شخصاً بمركبة (سائق معتمد، فرد عائلة، إلخ).

    relationship:
    - 'family': فرد عائلة (زوج/أبناء/...)
    - 'employee': موظف لدى المالك
    - 'authorized': سائق معتمد عام
    - 'temporary': مؤقت
    """
    person = db.get_person(person_id)
    if person is None:
        return {"success": False, "message": f"لا يوجد شخص بالمعرّف {person_id}"}

    result = db.add_vehicle_authorization(vehicle_id, person_id,
                                            relationship, notes)
    if result is None:
        return {
            "success": False,
            "message": "هذا الشخص مرتبط بهذه المركبة بالفعل",
        }

    return {
        "success": True,
        "auth_id": result,
        "message": (f"تم ربط {person['name']} بالمركبة "
                    f"كـ {relationship}"),
    }
