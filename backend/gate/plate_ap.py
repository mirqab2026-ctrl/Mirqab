"""
PlateAccessPoint — نقطة التحقق من لوحة المركبة
==============================================
تغلّف منطق التحقق من اللوحة (نفس منطق decision.make_decision السابق):
- تبحث عن المركبة باللوحة المقروءة
- تتحقّق أنها غير موقوفة (Suspended)
- تتحقّق أن الثقة ≥ عتبة الوضع

ملاحظة: القراءة/الكشف (YOLO + OCR) تتم في backend.plate_pipeline؛
هذه النقطة تستقبل نتيجة القراءة الجاهزة وتُصدر قرار التحقق فقط.
"""
from backend import database as db
from .access_point import AccessPoint, VerifyResult


class PlateAccessPoint(AccessPoint):
    ap_type = "plate"

    def __init__(self, db_module=db):
        # حقن قاعدة البيانات يسهّل الاختبار بمعزل عن SQLite الحقيقية
        self._db = db_module

    def verify(self, data: dict, mode) -> VerifyResult:
        plate_result = data.get("plate")
        if not plate_result or not plate_result.get("text"):
            return VerifyResult("plate", ok=False, confidence=0.0,
                                entity=None, reason="لم تُكتشف لوحة")

        conf = plate_result.get("confidence", 0)
        vehicle = self._db.find_vehicle_by_plate(plate_result["text"])
        ok = (
            vehicle is not None
            and vehicle.get("status") != "Suspended"
            and conf >= mode.plate_conf_threshold
        )
        # نُعيد المركبة دائماً عند إيجادها (حتى لو ok=False) ليستفيد منها
        # الدمج في AccessGate (مطابقة الصلاحية + بناء سبب الرفض).
        return VerifyResult("plate", ok=ok, confidence=conf, entity=vehicle)
