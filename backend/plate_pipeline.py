"""
Plate Pipeline - يلفّ نماذج المستخدم بدون أي تعديل عليها
========================================================
يستخدم:
- license_plate_detector.pt (كاشف اللوحة)
- ocr_chars_detector.pt (قارئ الأحرف)
- character_map.json (خريطة class_id → حرف)
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Union

import cv2
import numpy as np
from ultralytics import YOLO

MODELS_DIR = Path(__file__).parent.parent / "models"

# الـ class IDs للأرقام (لتمييزها عن الحروف)
DIGIT_CLASS_IDS = {0, 1, 12, 20, 21, 22, 23, 24, 25, 26}

# المعادل العربي لكل حرف لاتيني (وفق المعيار السعودي SASO)
ARABIC_MAP = {
    "A": "ا", "B": "ب", "D": "د", "E": "ع", "G": "ق", "H": "هـ",
    "J": "ح", "K": "ك", "L": "ل", "N": "ن", "R": "ر", "S": "س",
    "T": "ط", "U": "و", "V": "ى", "X": "ص", "Z": "م",
    "0": "٠", "1": "١", "2": "٢", "3": "٣", "4": "٤",
    "5": "٥", "6": "٦", "7": "٧", "8": "٨", "9": "٩",
}


class PlatePipeline:
    """Pipeline كامل: كشف لوحة → قراءة → ترتيب → نص ثنائي اللغة."""

    _instance = None # singleton

    def __init__(self,
                 detector_conf: float = 0.25,
                 ocr_conf: float = 0.30):
        detector_path = MODELS_DIR / "license_plate_detector.pt"
        ocr_path = MODELS_DIR / "ocr_chars_detector.pt"
        charmap_path = MODELS_DIR / "character_map.json"
        # تحقق من وجود ملفات النماذج قبل التحميل لإعطاء رسالة واضحة بدل انهيار غامض
        missing = [p.name for p in (detector_path, ocr_path, charmap_path) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                "ملفات النموذج المفقودة في مجلد models/: "
                + ", ".join(missing)
                + " — تأكد من تنزيل النماذج قبل التشغيل."
            )
        self.detector = YOLO(str(detector_path))
        self.ocr = YOLO(str(ocr_path))
        try:
            with open(charmap_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            raise ValueError(f"تعذّر قراءة character_map.json: {e}")
        self.char_map = {int(k): v for k, v in data.items() if not k.startswith("_")}
        self.detector_conf = detector_conf
        self.ocr_conf = ocr_conf

    @classmethod
    def get_instance(cls) -> "PlatePipeline":
        """Singleton للحفاظ على النماذج محمّلة في الذاكرة."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def to_arabic(text: str) -> str:
        """تحويل النص اللاتيني للعربي."""
        return " ".join(ARABIC_MAP.get(c, c) for c in text.split())

    def detect_plates(self, img: np.ndarray) -> List[Dict]:
        """يكشف اللوحات في الصورة (مع NMS لإزالة المكررات)."""
        results = self.detector.predict(img, conf=self.detector_conf,
                                         iou=0.5, verbose=False)
        if not results:
            return []
        plates = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            plates.append({
                "bbox": (int(x1), int(y1), int(x2), int(y2)),
                "confidence": float(box.conf[0]),
            })
        # إزالة المكررات
        plates.sort(key=lambda p: -p["confidence"])
        kept = []
        for p in plates:
            if not any(self._iou(p["bbox"], k["bbox"]) > 0.3 for k in kept):
                kept.append(p)
        return kept

    @staticmethod
    def _iou(b1, b2):
        x1, y1, x2, y2 = b1
        x1b, y1b, x2b, y2b = b2
        ix1, iy1 = max(x1, x1b), max(y1, y1b)
        ix2, iy2 = min(x2, x2b), min(y2, y2b)
        if ix2 < ix1 or iy2 < iy1:
            return 0.0
        intersection = (ix2 - ix1) * (iy2 - iy1)
        a1 = (x2 - x1) * (y2 - y1)
        a2 = (x2b - x1b) * (y2b - y1b)
        return intersection / (a1 + a2 - intersection)

    def read_plate(self, plate_crop: np.ndarray) -> Dict:
        """يقرأ النص من صورة لوحة مقصوصة."""
        if plate_crop.size == 0:
            return {"text": "", "text_ar": "", "characters": [], "avg_conf": 0.0}

        # تكبير اللوحات الصغيرة
        h, w = plate_crop.shape[:2]
        if w == 0 or h == 0:
            return {"text": "", "text_ar": "", "characters": [], "avg_conf": 0.0}
        if w < 200:
            scale = 200 / w
            plate_crop = cv2.resize(plate_crop, (int(w*scale), int(h*scale)),
                                     interpolation=cv2.INTER_CUBIC)

        results = self.ocr.predict(plate_crop, conf=self.ocr_conf, verbose=False)
        if not results:
            return {"text": "", "text_ar": "", "characters": [], "avg_conf": 0.0}
        chars = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            cls_id = int(box.cls[0])
            chars.append({
                "class_id": cls_id,
                "char": self.char_map.get(cls_id, f"[{cls_id}]"),
                "bbox": (float(x1), float(y1), float(x2), float(y2)),
                "confidence": float(box.conf[0]),
                "center_x": float((x1 + x2) / 2),
            })

        if not chars:
            return {"text": "", "text_ar": "", "characters": [], "avg_conf": 0.0}

        # ترتيب بصري: نتبع ترتيب اللوحة من اليسار لليمين كما تظهر فعلياً
        ordered = sorted(chars, key=lambda c: c["center_x"])

        text = " ".join(c["char"] for c in ordered)
        text_ar = self.to_arabic(text)
        avg_conf = float(np.mean([c["confidence"] for c in ordered]))

        return {
            "text": text,
            "text_ar": text_ar,
            "characters": ordered,
            "avg_conf": avg_conf,
        }

    def process(self, image: Union[str, Path, np.ndarray]) -> Dict:
        """الـ pipeline الكامل."""
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"لا يمكن قراءة الصورة: {image}")
        else:
            img = image.copy()

        # ✨ تحسين تلقائي ذكي قبل الكشف (صامت، سريع، يعمل فقط عند الحاجة)
        try:
            from backend.image_enhancer import maybe_enhance
            img = maybe_enhance(img, mode="plate")
        except Exception:
            pass  # لا نكسر الـ pipeline لو فشل التحسين

        ih, iw = img.shape[:2]
        plates = self.detect_plates(img)
        for plate in plates:
            x1, y1, x2, y2 = plate["bbox"]
            # تقييد الإحداثيات داخل حدود الصورة لتجنّب قصاصات فارغة/سالبة
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(iw, x2), min(ih, y2)
            if x2 <= x1 or y2 <= y1:
                plate.update({"text": "", "text_ar": "", "characters": [], "avg_conf": 0.0})
                continue
            crop = img[y1:y2, x1:x2]
            plate.update(self.read_plate(crop))

        return {
            "image_shape": img.shape[:2],
            "num_plates": len(plates),
            "plates": plates,
            "annotated_image": img,
        }

    def visualize(self, image: Union[str, Path, np.ndarray]) -> np.ndarray:
        """يعيد الصورة مع المربعات والنص."""
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"لا يمكن قراءة الصورة: {image}")
        else:
            img = image.copy()

        result = self.process(img)
        # نرسم على الصورة التي عُولجت فعلياً (قد تكون مُحسّنة) لتطابق الإحداثيات
        img = result.get("annotated_image", img)
        for plate in result["plates"]:
            x1, y1, x2, y2 = plate["bbox"]
            text = plate.get("text", "")
            conf = plate["confidence"]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
            label = f"{text} ({conf:.0%})"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(img, (x1, max(0, y1-th-10)), (x1+tw, y1), (0, 255, 0), -1)
            cv2.putText(img, label, (x1, max(15, y1-5)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        return img


if __name__ == "__main__":
    import sys
    pipeline = PlatePipeline()
    if len(sys.argv) > 1:
        result = pipeline.process(sys.argv[1])
        print(f"عدد اللوحات: {result['num_plates']}")
        for p in result["plates"]:
            print(f" EN: {p.get('text', '')}")
            print(f" AR: {p.get('text_ar', '')}")
            print(f" ثقة: {p['confidence']:.2%}")
