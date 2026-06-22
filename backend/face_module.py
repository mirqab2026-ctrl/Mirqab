"""
Face Recognition Module — محرك مزدوج بعتبة موحّدة
===================================================
الأولوية للمحرك الجديد ONNX (InsightFace buffalo_s — خفيف ودقيق):
    1) ONNX  : SCRFD كشف + MobileFaceNet تشفير 512-d  ← الأساسي
    2) dlib  : face_recognition 128-d                  ← احتياطي قديم
    3) hash  : OpenCV Haar + ترميز بصري بسيط           ← للديمو فقط

العتبة موحّدة وثابتة (backend/config.py → FACE_MATCH_THRESHOLD) ولا
تُعدَّل من الواجهة — أُلغي مفتاح تغيير العتبة من مركز التحكم نهائياً.

لتجهيز نماذج ONNX (مرة واحدة): python scripts/setup_face_models.py
"""
import logging
import numpy as np
from typing import List, Tuple, Optional
import cv2

from backend.config import (
    FACE_MATCH_THRESHOLD, EMBEDDING_DIM_ONNX, EMBEDDING_DIM_DLIB,
)

logger = logging.getLogger(__name__)

# ============== اختيار المحرك المتاح ==============
_ONNX_AVAILABLE = False
try:
    import onnxruntime  # noqa: F401
    from backend import face_onnx
    if face_onnx.models_available():
        _ONNX_AVAILABLE = True
        logger.info("محرك ONNX (buffalo_s) متاح — سيُستخدم كأساسي")
    else:
        logger.warning("onnxruntime مثبت لكن ملفات models/face غير موجودة "
                       "— شغّل scripts/setup_face_models.py")
except ImportError:
    logger.warning("onnxruntime غير مثبت")

_DLIB_AVAILABLE = False
if not _ONNX_AVAILABLE:
    try:
        import face_recognition as fr
        _DLIB_AVAILABLE = True
        logger.info("face_recognition (dlib) متاحة كاحتياطي")
    except ImportError:
        logger.warning("face_recognition غير مثبتة — fallback بصري بسيط")


# ============== أدوات مساعدة ==============
_MAX_DETECTION_WIDTH = 640


def _downscale(img: np.ndarray, max_w: int = _MAX_DETECTION_WIDTH):
    """يصغّر الصورة إن كانت أعرض من max_w. يعيد (img_small, scale_factor)."""
    h, w = img.shape[:2]
    if w <= max_w:
        return img, 1.0
    scale = max_w / float(w)
    small = cv2.resize(img, (max_w, int(h * scale)),
                       interpolation=cv2.INTER_AREA)
    return small, scale


def imread_unicode(path) -> Optional[np.ndarray]:
    """قراءة صورة بمسار يحتوي حروفاً عربية (cv2.imread يفشل معها على ويندوز)."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _maybe_enhance(img: np.ndarray) -> np.ndarray:
    """تحسين تلقائي صامت (يعمل فقط عند الحاجة — ~5-10ms للتحليل)."""
    try:
        from backend.image_enhancer import maybe_enhance
        return maybe_enhance(img, mode="face")
    except Exception:
        return img


class FaceModule:
    """وحدة التعرف على الوجه — واجهة ثابتة فوق ثلاثة محركات."""

    def __init__(self):
        if _ONNX_AVAILABLE:
            self.backend = "onnx"
            self._engine = face_onnx.OnnxFaceEngine()
            self.expected_dim = EMBEDDING_DIM_ONNX
        elif _DLIB_AVAILABLE:
            self.backend = "dlib"
            self._engine = None
            self.expected_dim = EMBEDDING_DIM_DLIB
        else:
            self.backend = "hash"
            self._engine = None
            self.expected_dim = 1024
            cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.face_cascade = cv2.CascadeClassifier(cascade)

        # العتبة الموحّدة (cosine للـ ONNX، 1-المسافة للـ dlib)
        self.match_threshold = FACE_MATCH_THRESHOLD
        # توافقاً مع الكود القديم الذي يقرأ tolerance للعرض فقط
        self.tolerance = 1.0 - FACE_MATCH_THRESHOLD
        self.use_lib = self.backend in ("onnx", "dlib")
        logger.info("FaceModule backend=%s, threshold=%.2f",
                    self.backend, self.match_threshold)

    # ================= الكشف =================
    def detect_faces(self, img: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """يكشف الوجوه ويعيد قائمة (top, right, bottom, left) بإحداثيات الأصل."""
        img = _maybe_enhance(img)

        if self.backend == "onnx":
            faces = self._engine.detect(img)
            return [(int(f["bbox"][1]), int(f["bbox"][2]),
                     int(f["bbox"][3]), int(f["bbox"][0])) for f in faces]

        small, scale = _downscale(img)
        if self.backend == "dlib":
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            locs = fr.face_locations(rgb, model="hog",
                                     number_of_times_to_upsample=0)
        else:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            dets = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            locs = [(y, x + w, y + h, x) for (x, y, w, h) in dets]

        if scale != 1.0:
            inv = 1.0 / scale
            locs = [(int(t * inv), int(r * inv), int(b * inv), int(l * inv))
                    for (t, r, b, l) in locs]
        return locs

    # ================= التشفير =================
    def _crop_with_margin(self, img, location, margin=0.25):
        top, right, bottom, left = location
        h, w = img.shape[:2]
        pad_h = int((bottom - top) * margin)
        pad_w = int((right - left) * margin)
        t = max(0, top - pad_h)
        b = min(h, bottom + pad_h)
        l = max(0, left - pad_w)
        r = min(w, right + pad_w)
        return img[t:b, l:r]

    def encode_face(self, img: np.ndarray,
                    location: Optional[Tuple] = None) -> Optional[np.ndarray]:
        """يحوّل وجهاً واحداً إلى متجه (512-d للمحرك الأساسي)."""
        if img is None or img.size == 0:
            return None

        if self.backend == "onnx":
            if location:
                crop = self._crop_with_margin(img, location)
            else:
                crop = img
            # نكشف داخل القصاصة للحصول على المعالم الخمسة (محاذاة أدق)
            faces = self._engine.detect(crop)
            if faces:
                return self._engine.embed(crop, faces[0]["kps"])
            # لا معالم؟ نشفّر القصاصة كما هي (أقل دقة لكنه لا يفشل)
            return self._engine.embed(crop, None)

        if self.backend == "dlib":
            if location:
                crop = self._crop_with_margin(img, location, margin=0.2)
                crop_small, _ = _downscale(crop, max_w=320)
                rgb = cv2.cvtColor(crop_small, cv2.COLOR_BGR2RGB)
                ch, cw = crop_small.shape[:2]
                encs = fr.face_encodings(rgb, [(0, cw, ch, 0)], num_jitters=1)
            else:
                small, _ = _downscale(img)
                rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                encs = fr.face_encodings(rgb, num_jitters=1)
            return encs[0] if encs else None

        # hash fallback (ديمو فقط)
        if location:
            top, right, bottom, left = location
            crop = img[top:bottom, left:right]
        else:
            faces = self.detect_faces(img)
            if not faces:
                return None
            top, right, bottom, left = faces[0]
            crop = img[top:bottom, left:right]
        crop = cv2.resize(crop, (32, 32))
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        return gray.flatten().astype(np.float32) / 255.0

    def encode_image_path(self, image_path) -> Optional[np.ndarray]:
        img = imread_unicode(image_path)   # يدعم المسارات العربية على ويندوز
        if img is None:
            return None
        return self.encode_face(img)

    # ================= المقارنة =================
    def compare(self, known_encoding: np.ndarray,
                unknown_encoding: np.ndarray) -> float:
        """يعيد similarity من 0 إلى 1 (أعلى = أكثر تطابقاً)."""
        if known_encoding is None or unknown_encoding is None:
            return 0.0
        if len(known_encoding) != len(unknown_encoding):
            return 0.0

        if self.backend == "dlib":
            distance = float(np.linalg.norm(known_encoding - unknown_encoding))
            return max(0.0, 1.0 - distance)

        # onnx + hash: cosine similarity
        a = np.asarray(known_encoding, dtype=np.float32).flatten()
        b = np.asarray(unknown_encoding, dtype=np.float32).flatten()
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
        return float(max(0.0, np.dot(a, b) / denom))

    # ================= التعرّف =================
    def identify(self, img: np.ndarray,
                 known_encodings: List[Tuple[int, np.ndarray]]
                 ) -> List[dict]:
        """يكشف الوجوه ويتعرف على كل وجه (مقارنة vectorized).

        Returns: [{ "bbox", "person_id", "confidence", "encoding" }, ...]
        """
        img = _maybe_enhance(img)

        # تجهيز مصفوفة الترميزات المعروفة
        valid_known = [(pid, np.asarray(enc, dtype=np.float32))
                       for pid, enc in known_encodings
                       if enc is not None and len(enc) == self.expected_dim]
        if valid_known:
            known_ids = np.array([pid for pid, _ in valid_known])
            known_matrix = np.stack([enc for _, enc in valid_known])
            if self.backend == "onnx":
                # نطبّع الصفوف مرة واحدة → cosine = ضرب نقطي
                norms = np.linalg.norm(known_matrix, axis=1, keepdims=True) + 1e-8
                known_matrix = known_matrix / norms
        else:
            known_ids = None
            known_matrix = None

        # كشف + تشفير حسب المحرك
        detected = []   # [(bbox_trbl, encoding), ...]
        if self.backend == "onnx":
            for f in self._engine.detect(img):
                x1, y1, x2, y2 = f["bbox"]
                enc = self._engine.embed(img, f["kps"])
                if enc is not None:
                    detected.append(((int(y1), int(x2), int(y2), int(x1)), enc))
        else:
            for loc in self.detect_faces(img):
                enc = self.encode_face(img, loc)
                if enc is not None:
                    detected.append((loc, enc))

        results = []
        for loc, encoding in detected:
            best_id = None
            best_sim = 0.0
            if known_matrix is not None and len(encoding) == known_matrix.shape[1]:
                if self.backend == "dlib":
                    distances = np.linalg.norm(known_matrix - encoding, axis=1)
                    sims = np.maximum(0.0, 1.0 - distances)
                else:
                    q = encoding / (np.linalg.norm(encoding) + 1e-8)
                    sims = np.maximum(0.0, known_matrix @ q)
                idx = int(np.argmax(sims))
                best_sim = float(sims[idx])
                if best_sim >= self.match_threshold:
                    best_id = int(known_ids[idx])

            results.append({
                "bbox": loc,
                "person_id": best_id,
                "confidence": best_sim,
                "encoding": encoding,
            })
        return results


# ============== Singleton ==============
_instance: Optional[FaceModule] = None


def get_face_module() -> FaceModule:
    global _instance
    if _instance is None:
        _instance = FaceModule()
    return _instance


if __name__ == "__main__":
    fm = get_face_module()
    print(f"Backend: {fm.backend}")
    print(f"Embedding dim: {fm.expected_dim}")
    print(f"Unified threshold: {fm.match_threshold:.2f}")
