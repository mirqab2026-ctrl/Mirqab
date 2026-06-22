"""
Pipeline موحد: كشف اللوحة + قراءة محتواها (OCR)
================================================

الاستخدام:
    from inference.plate_ocr import PlateOCR

    ocr = PlateOCR(
        detector_path='../models/license_plate_detector.pt',
        ocr_path='../models/ocr_chars_detector.pt',
        char_map_path='../ocr_training/character_map.json'
    )

    result = ocr.read('car.jpg')
    print(result)
    # → {
    #     'plates': [
    #         {
    #             'bbox': (x1, y1, x2, y2),
    #             'confidence': 0.94,
    #             'text': 'ABC 1234',
    #             'arabic_text': 'ا ب ج ١٢٣٤',
    #             'characters': [...]
    #         }
    #     ]
    # }
"""
import json
from pathlib import Path
from typing import List, Dict, Optional, Union

import cv2
import numpy as np
from ultralytics import YOLO


class PlateOCR:
    """نموذج OCR كامل: كشف اللوحة → قص → قراءة الأحرف → ترتيب → نص."""

    def __init__(
        self,
        detector_path: Union[str, Path],
        ocr_path: Union[str, Path],
        char_map_path: Optional[Union[str, Path]] = None,
        detector_conf: float = 0.25,
        ocr_conf: float = 0.30,
    ):
        self.detector = YOLO(str(detector_path))
        self.ocr = YOLO(str(ocr_path))
        self.detector_conf = detector_conf
        self.ocr_conf = ocr_conf

        # تحميل خريطة الأحرف
        self.char_map = {}
        if char_map_path and Path(char_map_path).exists():
            with open(char_map_path, encoding="utf-8") as f:
                data = json.load(f)
            # تنظيف من المفاتيح التي تبدأ بـ _
            self.char_map = {int(k): v for k, v in data.items() if not k.startswith("_")}

    def detect_plates(self, img: np.ndarray) -> List[Dict]:
        """يعيد قائمة باللوحات المكتشفة في الصورة (مع إزالة المكررة)."""
        results = self.detector.predict(img, conf=self.detector_conf,
                                         iou=0.5, verbose=False)
        plates = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0])
            plates.append({
                "bbox": (int(x1), int(y1), int(x2), int(y2)),
                "confidence": conf,
            })

        # إزالة اللوحات المتداخلة (نحتفظ بالأعلى ثقة)
        plates.sort(key=lambda p: -p["confidence"])
        filtered = []
        for p in plates:
            is_duplicate = False
            for kept in filtered:
                if self._iou(p["bbox"], kept["bbox"]) > 0.3:
                    is_duplicate = True
                    break
            if not is_duplicate:
                filtered.append(p)
        return filtered

    @staticmethod
    def _iou(box1, box2):
        """حساب IoU بين مربعين."""
        x1, y1, x2, y2 = box1
        x1b, y1b, x2b, y2b = box2
        ix1, iy1 = max(x1, x1b), max(y1, y1b)
        ix2, iy2 = min(x2, x2b), min(y2, y2b)
        if ix2 < ix1 or iy2 < iy1:
            return 0.0
        intersection = (ix2 - ix1) * (iy2 - iy1)
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (x2b - x1b) * (y2b - y1b)
        union = area1 + area2 - intersection
        return intersection / union if union > 0 else 0.0

    def read_plate_text(self, plate_crop: np.ndarray) -> Dict:
        """يقرأ النص من صورة لوحة مقصوصة."""
        if plate_crop.size == 0:
            return {"text": "", "arabic_text": "", "characters": []}

        # تكبير اللوحات الصغيرة جداً للحصول على دقة أفضل في OCR
        h, w = plate_crop.shape[:2]
        if w < 200:
            scale = 200 / w
            new_w = int(w * scale)
            new_h = int(h * scale)
            plate_crop = cv2.resize(plate_crop, (new_w, new_h),
                                     interpolation=cv2.INTER_CUBIC)

        results = self.ocr.predict(plate_crop, conf=self.ocr_conf, verbose=False)
        boxes = results[0].boxes

        # استخراج كل الأحرف مع موقعها
        chars = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            chars.append({
                "class_id": cls_id,
                "char": self.char_map.get(cls_id, f"[{cls_id}]"),
                "bbox": (float(x1), float(y1), float(x2), float(y2)),
                "confidence": conf,
                "center_x": float((x1 + x2) / 2),
                "center_y": float((y1 + y2) / 2),
            })

        # ترتيب الأحرف: نحدد إذا كانت اللوحة من سطرين
        if not chars:
            return {"text": "", "arabic_text": "", "characters": []}

        sorted_chars = self._sort_characters(chars, plate_crop.shape[:2])

        # تكوين النص
        text_parts = [c["char"] for c in sorted_chars if c["char"]]
        full_text = " ".join(text_parts)

        return {
            "text": full_text,
            "characters": sorted_chars,
        }

    # IDs الأرقام (0, 1, 2, 3, 4, 5, 6, 7, 8, 9) في خريطة فئات OCR
    DIGIT_CLASS_IDS = {0, 1, 12, 20, 21, 22, 23, 24, 25, 26}

    @classmethod
    def _is_digit(cls, char_info: Dict) -> bool:
        return char_info["class_id"] in cls.DIGIT_CLASS_IDS

    @classmethod
    def _sort_characters(cls, chars: List[Dict], plate_shape) -> List[Dict]:
        """
        ترتيب الأحرف للوحات السعودية:
        - الحروف على اليمين في اللوحة، الأرقام على اليسار
        - الترتيب السعودي القياسي: LETTERS NUMBERS (مثل "VKJ 6240")
        - لذا نُخرج الحروف أولاً (من اليسار لليمين داخل قسم الحروف)،
          ثم الأرقام (من اليسار لليمين داخل قسم الأرقام).
        """
        if not chars:
            return chars

        # فصل الحروف عن الأرقام
        letters = [c for c in chars if not cls._is_digit(c)]
        digits = [c for c in chars if cls._is_digit(c)]

        # ترتيب كل قسم من اليسار لليمين (داخلياً)
        letters.sort(key=lambda c: c["center_x"])
        digits.sort(key=lambda c: c["center_x"])

        # الترتيب النهائي: حروف ثم أرقام
        return letters + digits

    def read(self, image: Union[str, Path, np.ndarray]) -> Dict:
        """الـ pipeline الكامل: صورة → لوحات + نصوصها."""
        if isinstance(image, (str, Path)):
            img = cv2.imread(str(image))
            if img is None:
                raise ValueError(f"لا يمكن قراءة الصورة: {image}")
        else:
            img = image.copy()

        # كشف اللوحات
        plates = self.detect_plates(img)

        # قراءة كل لوحة
        for plate in plates:
            x1, y1, x2, y2 = plate["bbox"]
            crop = img[y1:y2, x1:x2]
            ocr_result = self.read_plate_text(crop)
            plate.update(ocr_result)

        return {
            "image_shape": img.shape[:2],
            "num_plates": len(plates),
            "plates": plates,
        }

    def visualize(self, image_path: Union[str, Path], output_path: Optional[str] = None) -> np.ndarray:
        """يرسم النتائج على الصورة (مربع لوحة + النص المقروء)."""
        img = cv2.imread(str(image_path))
        result = self.read(img)

        for plate in result["plates"]:
            x1, y1, x2, y2 = plate["bbox"]
            text = plate.get("text", "")
            conf = plate["confidence"]

            # مربع اللوحة
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)

            # النص المقروء
            label = f"{text} ({conf:.0%})"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
            cv2.rectangle(img, (x1, y1 - th - 10), (x1 + tw, y1), (0, 255, 0), -1)
            cv2.putText(img, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        if output_path:
            cv2.imwrite(str(output_path), img)
            print(f"حُفظت في: {output_path}")
        return img


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("الاستخدام: python plate_ocr.py <image_path>")
        sys.exit(1)

    project = Path(__file__).parent.parent
    ocr = PlateOCR(
        detector_path=project / "models" / "license_plate_detector.pt",
        ocr_path=project / "models" / "ocr_chars_detector.pt",
        char_map_path=project / "ocr_training" / "character_map.json",
    )

    result = ocr.read(sys.argv[1])
    print(f"\nعدد اللوحات المكتشفة: {result['num_plates']}")
    for i, plate in enumerate(result["plates"]):
        print(f"\n  لوحة {i+1}:")
        print(f"    bbox: {plate['bbox']}")
        print(f"    ثقة الكشف: {plate['confidence']:.2%}")
        print(f"    النص المقروء: {plate.get('text', '(لم يُحدد)')}")

    # حفظ نتيجة بصرية
    out = Path(sys.argv[1]).stem + "_annotated.jpg"
    ocr.visualize(sys.argv[1], out)
