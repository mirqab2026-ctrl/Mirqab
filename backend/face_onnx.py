"""
محرك الوجه ONNX — InsightFace buffalo_s (خفيف للابتوب)
========================================================
يشغّل نموذجي buffalo_s عبر onnxruntime مباشرة (بدون حزمة insightface
الثقيلة وتبعياتها) — مناسب للبيئة المعزولة Air-gapped:

- det_500m.onnx  : SCRFD-500MF — كشف الوجه + 5 معالم (عينان، أنف، زاويتا فم)
- w600k_mbf.onnx : MobileFaceNet (ArcFace) — تشفير 512-d

لماذا هذا المحرك بدل dlib؟
- أدق بوضوح (خاصة الزوايا الجانبية والإضاءة الضعيفة واللحية/الشماغ).
- أسرع على CPU (~40-70ms) ولا يحتاج ترجمة C++ عند التثبيت.
- التطابق عبر cosine similarity بعتبة موحّدة مستقرة.

التحميل الأول للنماذج: شغّل scripts/setup_face_models.py مرة واحدة.
"""
import logging
import os
from typing import List, Optional

import cv2
import numpy as np

from backend.config import (
    FACE_DET_MODEL, FACE_REC_MODEL, FACE_DET_SIZE, FACE_DET_THRESHOLD,
)

logger = logging.getLogger(__name__)

# قالب ArcFace القياسي لمحاذاة 5 معالم إلى 112×112
_ARCFACE_DST = np.array(
    [[38.2946, 51.6963],
     [73.5318, 51.5014],
     [56.0252, 71.7366],
     [41.5493, 92.3655],
     [70.7299, 92.2041]], dtype=np.float32)

_NMS_THRESHOLD = 0.4


def models_available() -> bool:
    """هل ملفا النموذجين موجودان؟"""
    return FACE_DET_MODEL.exists() and FACE_REC_MODEL.exists()


def _distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    """يحوّل مسافات SCRFD (يسار/أعلى/يمين/أسفل) إلى صناديق x1y1x2y2."""
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    """يحوّل إزاحات المعالم الخمسة إلى إحداثيات (N, 5, 2)."""
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, 0] + distance[:, i]
        py = points[:, 1] + distance[:, i + 1]
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1).reshape(-1, 5, 2)


def _nms(dets: np.ndarray, thresh: float = _NMS_THRESHOLD) -> List[int]:
    """Non-Maximum Suppression قياسي. dets = [x1,y1,x2,y2,score]."""
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][ovr <= thresh]
    return keep


class OnnxFaceEngine:
    """كشف SCRFD + تشفير MobileFaceNet عبر onnxruntime (CPU)."""

    def __init__(self,
                 det_size=FACE_DET_SIZE,
                 det_thresh: float = FACE_DET_THRESHOLD):
        import onnxruntime as ort

        so = ort.SessionOptions()
        # نترك خيطاً للواجهة كي لا يتجمد Streamlit أثناء العرض المباشر
        so.intra_op_num_threads = max(1, (os.cpu_count() or 2) - 1)
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # أخطاء فقط — يكتم تحذير "shape mismatch" المتوقع (النموذج معلن 640
        # ونغذيه 320 للسرعة؛ الحساب ديناميكي وصحيح، التحذير شكلي ومزعج)
        so.log_severity_level = 3
        providers = ["CPUExecutionProvider"]

        self.det_size = tuple(det_size)
        self.det_thresh = float(det_thresh)
        self._det = ort.InferenceSession(str(FACE_DET_MODEL), so, providers=providers)
        self._rec = ort.InferenceSession(str(FACE_REC_MODEL), so, providers=providers)
        self._det_input = self._det.get_inputs()[0].name
        self._rec_input = self._rec.get_inputs()[0].name
        logger.info("OnnxFaceEngine جاهز (det=%s, rec=%s, det_size=%s)",
                    FACE_DET_MODEL.name, FACE_REC_MODEL.name, self.det_size)

    # ---------------- الكشف ----------------
    def detect(self, img_bgr: np.ndarray) -> List[dict]:
        """يكشف الوجوه. يعيد قائمة dicts:
        { "bbox": (x1,y1,x2,y2) float, "kps": (5,2) float, "score": float }
        بإحداثيات الصورة الأصلية.
        """
        if img_bgr is None or img_bgr.size == 0:
            return []

        in_w, in_h = self.det_size
        h, w = img_bgr.shape[:2]

        # تغيير الحجم مع الحفاظ على النسبة + حشو أسود
        scale = min(in_w / w, in_h / h)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        det_img = np.zeros((in_h, in_w, 3), dtype=np.uint8)
        det_img[:nh, :nw] = resized

        blob = cv2.dnn.blobFromImage(
            det_img, 1.0 / 128.0, (in_w, in_h),
            (127.5, 127.5, 127.5), swapRB=True)
        outs = self._det.run(None, {self._det_input: blob})
        # بعض التصديرات تتضمن بُعد الدفعة (1, N, C)
        outs = [o[0] if o.ndim == 3 else o for o in outs]

        fmc = 3                      # عدد مستويات FPN
        strides = [8, 16, 32]
        num_anchors = 2

        all_scores, all_bboxes, all_kpss = [], [], []
        for idx, stride in enumerate(strides):
            scores = outs[idx].reshape(-1)
            bbox_preds = outs[idx + fmc].reshape(-1, 4) * stride
            kps_preds = outs[idx + fmc * 2].reshape(-1, 10) * stride

            gh, gw = in_h // stride, in_w // stride
            centers = np.stack(
                np.mgrid[:gh, :gw][::-1], axis=-1).astype(np.float32)
            centers = (centers * stride).reshape(-1, 2)
            centers = np.repeat(centers, num_anchors, axis=0)

            pos = np.where(scores >= self.det_thresh)[0]
            if pos.size == 0:
                continue
            bboxes = _distance2bbox(centers[pos], bbox_preds[pos])
            kpss = _distance2kps(centers[pos], kps_preds[pos])
            all_scores.append(scores[pos])
            all_bboxes.append(bboxes)
            all_kpss.append(kpss)

        if not all_scores:
            return []

        scores = np.concatenate(all_scores)
        bboxes = np.concatenate(all_bboxes) / scale   # عودة لإحداثيات الأصل
        kpss = np.concatenate(all_kpss) / scale

        dets = np.hstack([bboxes, scores[:, None]]).astype(np.float32)
        keep = _nms(dets)

        faces = []
        for i in keep:
            x1, y1, x2, y2, s = dets[i]
            faces.append({
                "bbox": (max(0.0, x1), max(0.0, y1),
                         min(float(w), x2), min(float(h), y2)),
                "kps": kpss[i].astype(np.float32),
                "score": float(s),
            })
        # الأكبر أولاً (وجه السائق هو الأقرب/الأكبر عادة)
        faces.sort(key=lambda f: (f["bbox"][2] - f["bbox"][0])
                                 * (f["bbox"][3] - f["bbox"][1]),
                   reverse=True)
        return faces

    # ---------------- المحاذاة والتشفير ----------------
    @staticmethod
    def _align(img_bgr: np.ndarray, kps: np.ndarray) -> np.ndarray:
        """محاذاة الوجه إلى 112×112 عبر تحويل تشابهي من المعالم الخمسة."""
        M, _ = cv2.estimateAffinePartial2D(
            kps.astype(np.float32), _ARCFACE_DST, method=cv2.LMEDS)
        if M is None:
            # fallback: قص مركزي بسيط
            return cv2.resize(img_bgr, (112, 112), interpolation=cv2.INTER_LINEAR)
        return cv2.warpAffine(img_bgr, M, (112, 112), borderValue=0)

    def embed(self, img_bgr: np.ndarray,
              kps: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
        """يشفّر وجهاً إلى متجه 512-d مُطَبَّع (L2-normalized).

        إذا توفرت المعالم kps تتم المحاذاة (الأدق)؛ وإلا تُستخدم الصورة
        كما هي بعد تحجيمها 112×112 (أقل دقة، للحالات الاستثنائية).
        """
        if img_bgr is None or img_bgr.size == 0:
            return None
        if kps is not None:
            aligned = self._align(img_bgr, kps)
        else:
            aligned = cv2.resize(img_bgr, (112, 112),
                                 interpolation=cv2.INTER_LINEAR)

        blob = cv2.dnn.blobFromImage(
            aligned, 1.0 / 127.5, (112, 112),
            (127.5, 127.5, 127.5), swapRB=True)
        out = self._rec.run(None, {self._rec_input: blob})[0].flatten()
        norm = float(np.linalg.norm(out))
        if norm < 1e-8:
            return None
        return (out / norm).astype(np.float32)
