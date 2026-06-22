"""
AccessPoint — التجريد الأب لكل نقاط التحقق في البوابة
=====================================================
يجسّد فكرة «نقطة تحقق» القابلة للتوسّع: كل نوع تحقق (لوحة، وجه،
بصمة، RFID مستقبلاً) يرث AccessPoint ويُنفّذ verify().

البوابة (AccessGate) تتعامل مع كل النقاط بشكل متعدّد الأشكال
(polymorphism) دون أن تعرف تفاصيل كل نوع — وهذا يحقّق مبدأ
Open/Closed: إضافة نوع تحقق جديد = صنف جديد فقط، بلا لمس قلب القرار.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class VerifyResult:
    """نتيجة تحقّق نقطة واحدة.

    ap_type     نوع النقطة ("plate" | "face" | ...)
    ok          هل اجتازت النقطة عتباتها بنجاح؟
    confidence  درجة الثقة (0..1)
    entity      السجل المرتبط من قاعدة البيانات (مركبة / شخص) أو None
    reason      سبب اختياري (للتشخيص)
    """
    ap_type: str
    ok: bool
    confidence: float = 0.0
    entity: Optional[dict] = None
    reason: str = ""


class AccessPoint(ABC):
    """الكلاس الأب لكل نقاط التحقق."""

    #: معرّف نوع النقطة — تُعيد تعريفه الأصناف المشتقّة
    ap_type: str = "generic"

    @abstractmethod
    def verify(self, data: dict, mode) -> VerifyResult:
        """يتحقّق من بيانات الدخول لهذه النقطة فقط.

        data: قاموس الدخول الكامل (مثلاً {"plate": {...}, "face": {...}})
        mode: كائن وضع التشغيل (يوفّر العتبات: plate_conf_threshold,
              face_conf_threshold, require_both, name)

        يُعيد VerifyResult يصف نتيجة هذه النقطة وحدها — أما الدمج
        النهائي (AND + مطابقة الصلاحية) فمسؤولية AccessGate.
        """
        raise NotImplementedError
