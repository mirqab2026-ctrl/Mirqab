"""
backend.gate — حزمة البوابة ونقاط التحقق (بنية OOP قابلة للتوسّع)
================================================================
- AccessPoint / VerifyResult : التجريد الأب لكل نقطة تحقق
- PlateAccessPoint / FaceAccessPoint : نقطتا التحقق الحاليتان
- AccessGate : البوابة التي تدمج النتائج وتُصدر القرار
- build_default_gate() : مصنع البوابة القياسية لمرقاب
"""
from .access_point import AccessPoint, VerifyResult
from .plate_ap import PlateAccessPoint
from .face_ap import FaceAccessPoint
from .access_gate import AccessGate, build_default_gate

__all__ = [
    "AccessPoint",
    "VerifyResult",
    "PlateAccessPoint",
    "FaceAccessPoint",
    "AccessGate",
    "build_default_gate",
]
