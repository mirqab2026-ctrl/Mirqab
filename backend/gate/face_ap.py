"""
FaceAccessPoint — نقطة التحقق من وجه السائق
============================================
تغلّف منطق التحقق من الوجه (نفس منطق decision.make_decision السابق):
- إذا كانت الثقة ≥ عتبة الوضع، تجلب الشخص وتتحقّق أنه مفعّل (active)
- وإلا تُعدّ النقطة فاشلة دون جلب الشخص

ملاحظة: كشف/ترميز الوجه (ONNX buffalo_s) يتم في
backend.face_module؛ هذه النقطة تستقبل نتيجة التعرّف الجاهزة فقط.
"""
from backend import database as db
from .access_point import AccessPoint, VerifyResult


class FaceAccessPoint(AccessPoint):
    ap_type = "face"

    def __init__(self, db_module=db):
        self._db = db_module

    def verify(self, data: dict, mode) -> VerifyResult:
        face_result = data.get("face")
        if not face_result or not face_result.get("person_id"):
            return VerifyResult("face", ok=False, confidence=0.0, entity=None)

        conf = face_result.get("confidence", 0)
        person = None
        ok = False
        # نطابق السلوك السابق: لا نجلب الشخص إلا عند تجاوز العتبة
        if conf >= mode.face_conf_threshold:
            person = self._db.get_person(face_result["person_id"])
            ok = person is not None and person.get("active", 1) == 1
        return VerifyResult("face", ok=ok, confidence=conf, entity=person)
