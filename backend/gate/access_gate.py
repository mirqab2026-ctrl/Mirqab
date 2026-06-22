"""
AccessGate — البوابة التي تدمج نتائج نقاط التحقق وتصدر القرار النهائي
====================================================================
البوابة تملك قائمة نقاط تحقق (AccessPoint) وتتعامل معها بشكل متعدّد
الأشكال. process_entry:
  1. يشغّل verify() لكل نقطة
  2. يستخرج المركبة (من نقطة اللوحة) والشخص (من نقطة الوجه)
  3. يحسب مطابقة الصلاحية (هل الشخص مصرّح لهذه المركبة؟)
  4. يدمج حسب الوضع (require_both = AND صارم، وإلا OR للعرض)

السلوك مطابق تماماً لـ decision.make_decision السابق — أُعيد تنظيمه
داخل بنية نظيفة قابلة للتوسّع والاختبار، بلا أي تغيير في المخرجات.
"""
from typing import List, Optional, Dict

from backend import database as db
from .access_point import AccessPoint
from .plate_ap import PlateAccessPoint
from .face_ap import FaceAccessPoint


class AccessGate:
    """بوابة دخول تحتوي نقاط تحقق وتُصدر قراراً موحّداً."""

    def __init__(self, gate_id: int = 1, name: str = "Main Gate",
                 access_points: Optional[List[AccessPoint]] = None):
        self.gate_id = gate_id
        self.name = name
        self.access_points: List[AccessPoint] = list(access_points or [])

    def add_access_point(self, ap: AccessPoint) -> "AccessGate":
        """يضيف نقطة تحقق (يدعم التسلسل)."""
        self.access_points.append(ap)
        return self

    def process_entry(self, data: Dict, mode) -> Dict:
        """يشغّل كل نقاط التحقق ويُصدر القرار النهائي.

        يُعيد نفس بنية decision.make_decision:
        {decision, reason, plate_ok, face_ok, vehicle, person,
         match_match, auth_relationship, mode}
        """
        results = {ap.ap_type: ap.verify(data, mode) for ap in self.access_points}

        plate_r = results.get("plate")
        face_r = results.get("face")
        plate_ok = plate_r.ok if plate_r else False
        face_ok = face_r.ok if face_r else False
        vehicle = plate_r.entity if plate_r else None
        person = face_r.entity if face_r else None

        # هل اللوحة والشخص متطابقان؟ (المالك المباشر أو ضمن المعتمدين)
        match_match = False
        auth_relationship = None
        if vehicle and person:
            if vehicle.get("owner_id") == person.get("id"):
                match_match = True
                auth_relationship = "owner"
            else:
                authorized, rel = db.is_person_authorized_for_vehicle(
                    person["id"], vehicle["id"]
                )
                if authorized:
                    match_match = True
                    auth_relationship = rel

        # الدمج النهائي (مطابق للمنطق السابق حرفياً)
        if mode.require_both:
            if plate_ok and face_ok and match_match:
                decision, reason = "GRANTED", "Both plate and face verified"
            elif plate_ok and face_ok and not match_match:
                decision, reason = "PENDING", "Plate and face don't belong to same person"
            elif not plate_ok:
                decision, reason = "DENIED", "Plate not recognized or vehicle suspended"
            elif not face_ok:
                decision, reason = "PENDING", "Face not recognized with sufficient confidence"
            else:
                decision, reason = "DENIED", "Verification failed"
        else:
            if plate_ok or face_ok:
                decision, reason = "GRANTED", "At least one verification passed (demo)"
            else:
                decision, reason = "DENIED", "No verification passed"

        return {
            "decision": decision,
            "reason": reason,
            "plate_ok": plate_ok,
            "face_ok": face_ok,
            "vehicle": vehicle,
            "person": person,
            "match_match": match_match,
            "auth_relationship": auth_relationship,
            "mode": mode.name,
        }


def build_default_gate() -> AccessGate:
    """يبني البوابة القياسية لمرقاب: تحقّق اللوحة ثم الوجه."""
    return AccessGate(
        gate_id=1,
        name="Mirqab Main Gate",
        access_points=[PlateAccessPoint(), FaceAccessPoint()],
    )
