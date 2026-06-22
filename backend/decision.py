"""
Decision Fusion + 4 Recognition Modes
======================================
يدمج نتائج كشف اللوحة + الوجه ويصدر قراراً نهائياً (GRANTED / DENIED / PENDING)
بناءً على الوضع المختار.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from . import database as db
from .config import FACE_MATCH_THRESHOLD


@dataclass
class RecognitionMode:
    """تعريف وضع تشغيل.

    ملاحظة تصميمية: عتبة الوجه **موحّدة** لكل الأوضاع
    (backend/config.py → FACE_MATCH_THRESHOLD) — الأوضاع تختلف في
    منطق الدمج (require_both) وعتبة اللوحة فقط. أُلغي الوضع المخصص
    ومفتاح تغيير العتبة من الواجهة نهائياً (قرار أمني وتبسيطي).
    """
    name: str
    label: str
    description: str
    face_conf_threshold: float
    plate_conf_threshold: float
    require_both: bool # يجب تطابق اللوحة والوجه معاً؟
    use_case: str


MODES = {
    "strict": RecognitionMode(
        name="strict",
        label="Strict",
        description="أقصى صرامة - وزارات وبنوك",
        face_conf_threshold=FACE_MATCH_THRESHOLD,
        plate_conf_threshold=0.85,
        require_both=True,
        use_case="Ministries, banks",
    ),
    "balanced": RecognitionMode(
        name="balanced",
        label="Balanced",
        description="الوضع الافتراضي - استخدام يومي",
        face_conf_threshold=FACE_MATCH_THRESHOLD,
        plate_conf_threshold=0.70,
        require_both=True,
        use_case="Daily use",
    ),
    "demo": RecognitionMode(
        name="demo",
        label="Demo",
        description="عرض ومناقشات - أحد النظامين يكفي",
        face_conf_threshold=FACE_MATCH_THRESHOLD,
        plate_conf_threshold=0.50,
        require_both=False,
        use_case="Trade shows, defenses",
    ),
    "emergency": RecognitionMode(
        name="emergency",
        label="Emergency",
        description="حالة طوارئ - أقصى صرامة",
        face_conf_threshold=FACE_MATCH_THRESHOLD,
        plate_conf_threshold=0.95,
        require_both=True,
        use_case="Lock-down, threat",
    ),
}


def get_active_mode() -> RecognitionMode:
    mode_name = db.get_setting("active_mode", "balanced")
    # "custom" أُلغي — أي قيمة قديمة مخزنة تعود للوضع المتوازن
    return MODES.get(mode_name, MODES["balanced"])


def make_decision(
    plate_result: Optional[Dict],
    face_result: Optional[Dict],
    mode: Optional[RecognitionMode] = None,
) -> Dict:
    """
    يأخذ نتائج اللوحة والوجه ويصدر قراراً نهائياً.

    plate_result = {
        "text": str, "text_ar": str, "confidence": float,
        "matched_vehicle": dict or None # من قاعدة البيانات
    }

    face_result = {
        "person_id": int or None, "confidence": float,
        "matched_person": dict or None
    }

    Returns:
        {
            "decision": "GRANTED" | "DENIED" | "PENDING",
            "reason": str,
            "plate_ok": bool,
            "face_ok": bool,
            "vehicle": dict or None,
            "person": dict or None,
            "match_match": bool # هل اللوحة والشخص متطابقان؟
        }
    """
    if mode is None:
        mode = get_active_mode()

    # غلاف متوافق: المنطق انتقل إلى بنية AccessGate/AccessPoint النظيفة.
    # نبني البوابة القياسية ونمرّر البيانات لها — المخرجات مطابقة تماماً.
    from backend.gate import build_default_gate
    gate = build_default_gate()
    return gate.process_entry({"plate": plate_result, "face": face_result}, mode)


def final_verdict(
    plate_result: Optional[Dict],
    face_result: Optional[Dict],
    mode: Optional[RecognitionMode] = None,
    need_plate: bool = True,
    need_face: bool = True,
) -> Dict:
    """القرار النهائي **الموحّد** لكل البوابات (المباشرة + التلقائية).

    قاعدة مبسّطة بلا اشتراط ربط المركبة بالسائق:
      - اللوحة سليمة = لوحة مسجّلة وغير موقوفة.
      - الوجه سليم   = شخص مسجّل ومفعّل وغير موقوف، بثقة ≥ عتبة الوضع.
      - GRANTED فقط عند سلامة الطرفين المطلوبين معاً.

    الحالات الأربع (عند تفعيل النظامين):
      1) اللوحة + الوجه سليمان        → GRANTED (فتح فوري)
      2) اللوحة سليمة والوجه غير مطابق → DENIED (تحقّق أمني للسائق)
      3) الوجه سليم واللوحة غير مطابقة → DENIED (تسجيل/إعادة فحص المركبة)
      4) كلاهما غير مطابق             → DENIED (إنذار أمني / مسار زوّار)
    """
    if mode is None:
        mode = get_active_mode()
    try:
        from backend.plate_normalizer import to_canonical, validate_canonical
    except ImportError:
        def to_canonical(s):
            return (s or "").replace(" ", "").upper()

        def validate_canonical(s):
            return (bool(s), "")

    # ---- اللوحة ----
    plate_text = (plate_result or {}).get("text", "") if plate_result else ""
    plate_canonical = to_canonical(plate_text) if plate_text else ""
    plate_is_valid = validate_canonical(plate_canonical)[0] if plate_canonical else False
    vehicle = db.find_vehicle_by_plate(plate_canonical) if plate_is_valid else None
    veh_suspended = bool(vehicle and vehicle.get("status") == "Suspended")
    plate_ok = bool(vehicle and not veh_suspended)

    # ---- الوجه ----
    person = None
    if face_result and face_result.get("person_id"):
        if face_result.get("confidence", 0) >= mode.face_conf_threshold:
            person = db.get_person(face_result["person_id"])
    per_suspended = bool(person and (person.get("access_level") == "Suspended"
                                     or person.get("active", 1) != 1))
    face_ok = bool(person and not per_suspended)

    # ---- الدمج (بلا اشتراط ربط) ----
    p_part = (not need_plate) or plate_ok
    f_part = (not need_face) or face_ok
    has_any = (need_plate and plate_ok) or (need_face and face_ok)
    granted = p_part and f_part and has_any

    case = 0
    alert = False
    if granted:
        decision = "GRANTED"
        reason = "تطابق كامل — السماح بالمرور"
        case = 1
    else:
        decision = "DENIED"
        alert = True
        if need_plate and need_face and plate_ok and not face_ok:
            case = 2
            reason = ("اللوحة مصرّح لها لكن الشخص موقوف — تحقّق أمني."
                      if per_suspended else
                      "اللوحة مصرّح لها لكن وجه السائق غير مطابق — تحقّق أمني يدوي من هوية السائق.")
        elif need_plate and need_face and face_ok and not plate_ok:
            case = 3
            if veh_suspended:
                reason = "السائق مخوّل لكن المركبة موقوفة — يلزم تدخّل الأمن."
            elif plate_text and not plate_is_valid:
                reason = "السائق مخوّل لكن اللوحة غير مقروءة — نظّف اللوحة وأعد الفحص."
            else:
                reason = "السائق مخوّل لكن المركبة غير مسجّلة — يلزم تسجيل بيانات المركبة."
        else:
            case = 4
            reason = "لا اللوحة ولا الوجه مطابقان — إنذار أمني / مسار الزوّار."

    return {
        "decision": decision,
        "reason": reason,
        "case": case,
        "alert": alert,
        "vehicle": vehicle,
        "person": person,
        "plate_ok": plate_ok,
        "face_ok": face_ok,
        "veh_suspended": veh_suspended,
        "per_suspended": per_suspended,
        "plate_canonical": plate_canonical,
        "plate_is_valid": plate_is_valid,
        "mode": mode.name,
    }


def set_active_mode(mode_name: str):
    if mode_name in MODES:
        db.set_setting("active_mode", mode_name)
