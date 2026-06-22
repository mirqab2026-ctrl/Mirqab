"""
live_capture.py — إدارة كاميرات الجهاز الحيّة (USB / مدمجة) عبر OpenCV
=====================================================================
يُستخدم في صفحة «البوابة التلقائية» للبثّ المستمر بلا ضغط زر.

- سجلّ كاميرات module-level يبقى عبر إعادة تشغيل سكربت Streamlit في نفس
  العملية، فلا نُعيد فتح الكاميرا كل إطار (الفتح بطيء).
- get_cap(index) يفتح الكاميرا مرة ويُعيدها لاحقاً.
- release_all() يحرّر كل الكاميرات عند الإيقاف.

ملاحظة: الكاميرا تُقرأ على جهاز الخادم (= جهاز الكشك). هذا مناسب لنشر
البوابة محلياً حيث الكاميرات موصولة بالجهاز نفسه.
"""
import cv2

# سجلّ الكاميرات المفتوحة: {index: VideoCapture}
_CAPS = {}

# الدقة المطلوبة (قد تتجاهلها بعض الكاميرات وتعيد أقرب مدعوم)
_REQ_W, _REQ_H = 1280, 720


def get_cap(index: int):
    """يفتح الكاميرا مرة واحدة فقط لكل فهرس ويخزّنها.

    مهم: لا نُعيد محاولة الفتح كل استدعاء — فتح فهرس خاطئ بـ DSHOW قد يتعطّل
    لثوانٍ، وإعادة المحاولة كل إطار تُجمّد الواجهة. نفتح مرة، ونتذكّر النتيجة
    (حتى لو فشلت)؛ release()/release_all() يمسحان السجلّ لإتاحة محاولة جديدة.
    """
    if index in _CAPS:
        return _CAPS[index]
    # CAP_DSHOW أسرع وأكثر استقراراً على ويندوز
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if cap.isOpened():
        # MJPG: ضغط داخل الكاميرا → يحرر نطاق USB ويسمح بـ 720p بسلاسة
        # (الصيغة الخام YUY2 عند 720p تُشبع المنفذ وتُبطئ كل شيء)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, _REQ_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, _REQ_H)
        cap.set(cv2.CAP_PROP_FPS, 15)
        # مخزن إطار واحد فقط = لا تراكم → لا تأخير بين الواقع والشاشة
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    _CAPS[index] = cap  # نخزّنها حتى لو لم تُفتح (تجنّب إعادة فتح متعطّلة)
    return cap


def read_frame(index: int):
    """يقرأ أحدث إطار. يُعيد (ok, frame) — frame بصيغة BGR أو None.

    نُسقط إطاراً متراكماً قبل القراءة (grab) لأننا نقرأ أبطأ من معدل
    الكاميرا — بدون هذا تظهر صورة متأخرة عدة ثوانٍ عن الواقع.
    """
    cap = get_cap(index)
    if not cap or not cap.isOpened():
        return False, None
    cap.grab()  # تجاهل الإطار القديم العالق في المخزن
    ok, frame = cap.read()
    return bool(ok and frame is not None), frame


def release(index: int):
    """يحرّر كاميرا واحدة."""
    cap = _CAPS.pop(index, None)
    if cap is not None:
        try:
            cap.release()
        except Exception:
            pass


def release_all():
    """يحرّر كل الكاميرات المفتوحة."""
    for idx in list(_CAPS.keys()):
        release(idx)
