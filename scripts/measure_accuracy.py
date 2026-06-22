"""
measure_accuracy.py
====================
سكربت قياس دقة نماذج النظام الفعلية (لا أرقام placeholder).

يقيس:
1. **كاشف اللوحات** (license_plate_detector.pt):
   - معدل الكشف الناجح
   - متوسط ثقة الكشف
   - عدد اللوحات لكل صورة

2. **قارئ الأحرف** (ocr_chars_detector.pt):
   - معدل الكشف الناجح للأحرف
   - متوسط ثقة كل حرف
   - عدد الأحرف المكتشفة (هل يكتمل 7 خانات؟)

3. **النظام الكامل (end-to-end)**:
   - كم من اللوحات تُكتشف ويُقرأ نصّها كاملاً (7 خانات)
   - متوسط ثقة كل النظام

الاستخدام:
    python scripts/measure_accuracy.py --images <path_to_dir_with_plate_images>

أمثلة:
    python scripts/measure_accuracy.py --images data/test_plates/
    python scripts/measure_accuracy.py --images data/photos/

يصدر:
- ملخص في الكونسول
- ملف data/accuracy_report.json بكل التفاصيل
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

# تحقق من المكتبات
try:
    import cv2
except ImportError:
    print("ERROR: opencv-python غير مثبّت. شغّل: pip install opencv-python")
    sys.exit(1)

try:
    from ultralytics import YOLO
except ImportError:
    print("ERROR: ultralytics غير مثبّت. شغّل: pip install ultralytics")
    sys.exit(1)


MODELS_DIR = ROOT / "models"
PLATE_MODEL = MODELS_DIR / "license_plate_detector.pt"
OCR_MODEL = MODELS_DIR / "ocr_chars_detector.pt"
REPORT_PATH = ROOT / "data" / "accuracy_report.json"


def imread_unicode(path):
    """قراءة صورة بمسار قد يحوي أحرف غير ASCII (Windows-safe)."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def measure_plate_detector(images: list, conf_threshold: float = 0.25):
    """يقيس كاشف اللوحات."""
    print(f"\n{'='*65}")
    print("  [1/3] قياس كاشف اللوحات (license_plate_detector.pt)")
    print(f"{'='*65}")
    if not PLATE_MODEL.exists():
        print(f"  ✗ نموذج غير موجود: {PLATE_MODEL}")
        return None

    model = YOLO(str(PLATE_MODEL))

    stats = {
        "total_images": len(images),
        "detected": 0,
        "no_detection": 0,
        "multi_detection": 0,
        "confidences": [],
        "per_image": [],
    }

    for i, img_path in enumerate(images, 1):
        img = imread_unicode(img_path)
        if img is None:
            stats["no_detection"] += 1
            stats["per_image"].append({"file": img_path.name, "result": "unreadable"})
            continue

        results = model(img, conf=conf_threshold, verbose=False)
        boxes = results[0].boxes
        n = len(boxes) if boxes is not None else 0

        if n == 0:
            stats["no_detection"] += 1
            stats["per_image"].append({"file": img_path.name, "n_plates": 0, "max_conf": 0})
        else:
            stats["detected"] += 1
            if n > 1:
                stats["multi_detection"] += 1
            confs = boxes.conf.cpu().numpy().tolist() if hasattr(boxes.conf, 'cpu') else list(boxes.conf)
            max_c = float(max(confs))
            stats["confidences"].extend([float(c) for c in confs])
            stats["per_image"].append({
                "file": img_path.name,
                "n_plates": n,
                "max_conf": max_c,
            })
        if i % 5 == 0:
            print(f"  ... عُولج {i}/{len(images)}")

    # حسابات
    total = stats["total_images"]
    if stats["confidences"]:
        avg_conf = float(np.mean(stats["confidences"]))
        min_conf = float(np.min(stats["confidences"]))
        max_conf = float(np.max(stats["confidences"]))
    else:
        avg_conf = min_conf = max_conf = 0.0

    detection_rate = stats["detected"] / total if total else 0
    print(f"\n  📊 النتائج:")
    print(f"     معدل الكشف:        {detection_rate*100:.1f}%  ({stats['detected']}/{total})")
    print(f"     فشل الكشف:         {stats['no_detection']}")
    print(f"     متوسط الثقة:       {avg_conf*100:.1f}%")
    print(f"     أعلى ثقة:          {max_conf*100:.1f}%")
    print(f"     أدنى ثقة:          {min_conf*100:.1f}%")
    print(f"     لوحات متعدّدة:     {stats['multi_detection']}")

    stats["detection_rate"] = detection_rate
    stats["avg_conf"] = avg_conf
    stats["min_conf"] = min_conf
    stats["max_conf"] = max_conf
    return stats


def measure_ocr_detector(plate_crops: list, conf_threshold: float = 0.25):
    """يقيس قارئ الأحرف على مقتطعات اللوحات.

    القواعد الجديدة: قراءة كاملة = 4-7 خانات (1-4 أرقام + 3 حروف).

    plate_crops: list of np.ndarray (الصور المقصوصة على اللوحات فقط)
    """
    print(f"\n{'='*65}")
    print("  [2/3] قياس قارئ الأحرف (ocr_chars_detector.pt)")
    print("       القاعدة: 4-7 خانات صالحة (3 حروف + 1-4 أرقام)")
    print(f"{'='*65}")
    if not OCR_MODEL.exists():
        print(f"  ✗ نموذج غير موجود: {OCR_MODEL}")
        return None

    model = YOLO(str(OCR_MODEL))

    stats = {
        "total_crops": len(plate_crops),
        "complete_reads": 0,   # 4-7 خانات (لوحة صالحة)
        "partial_reads": 0,    # 1-3 خانات
        "no_reads": 0,         # 0 خانات
        "perfect_reads": 0,    # 7 خانات بالضبط (المعيار القديم — للمقارنة)
        "chars_per_plate": [],
        "all_confidences": [],
    }

    for i, crop in enumerate(plate_crops, 1):
        if crop is None or crop.size == 0:
            stats["no_reads"] += 1
            continue
        results = model(crop, conf=conf_threshold, verbose=False)
        boxes = results[0].boxes
        n = len(boxes) if boxes is not None else 0

        stats["chars_per_plate"].append(n)
        if n == 0:
            stats["no_reads"] += 1
        elif 4 <= n <= 7:
            # القاعدة الجديدة: قراءة صالحة (3 حروف + 1-4 أرقام)
            stats["complete_reads"] += 1
            if n == 7:
                stats["perfect_reads"] += 1
        else:
            # 1-3 خانات = قراءة جزئية
            stats["partial_reads"] += 1

        if n > 0:
            confs = boxes.conf.cpu().numpy().tolist() if hasattr(boxes.conf, 'cpu') else list(boxes.conf)
            stats["all_confidences"].extend([float(c) for c in confs])

    total = stats["total_crops"]
    if stats["all_confidences"]:
        avg_conf = float(np.mean(stats["all_confidences"]))
        min_conf = float(np.min(stats["all_confidences"]))
    else:
        avg_conf = min_conf = 0.0

    complete_rate = stats["complete_reads"] / total if total else 0
    perfect_rate = stats["perfect_reads"] / total if total else 0
    avg_chars = float(np.mean(stats["chars_per_plate"])) if stats["chars_per_plate"] else 0

    print(f"\n  📊 النتائج:")
    print(f"     قراءة صالحة (4-7 خانات): {complete_rate*100:.1f}%  ({stats['complete_reads']}/{total})")
    print(f"     قراءة مثالية (7 خانات): {perfect_rate*100:.1f}%  ({stats['perfect_reads']}/{total}) [مرجعي]")
    print(f"     قراءة جزئية (1-3):      {stats['partial_reads']}")
    print(f"     لا قراءة:               {stats['no_reads']}")
    print(f"     متوسط الأحرف/لوحة:      {avg_chars:.1f}")
    print(f"     متوسط ثقة الحرف:        {avg_conf*100:.1f}%")
    print(f"     أدنى ثقة:               {min_conf*100:.1f}%")

    stats["complete_rate"] = complete_rate
    stats["perfect_rate"] = perfect_rate
    stats["avg_conf"] = avg_conf
    stats["avg_chars_per_plate"] = avg_chars
    return stats


def end_to_end(images: list, plate_conf: float = 0.25, ocr_conf: float = 0.25):
    """يشغّل النظام الكامل: كشف لوحة → قص → قراءة أحرف."""
    print(f"\n{'='*65}")
    print("  [3/3] قياس النظام الكامل (end-to-end)")
    print(f"{'='*65}")

    if not (PLATE_MODEL.exists() and OCR_MODEL.exists()):
        print("  ✗ أحد النماذج غير موجود")
        return None

    plate_model = YOLO(str(PLATE_MODEL))
    ocr_model = YOLO(str(OCR_MODEL))

    crops = []
    full_success = 0   # كشف لوحة + قراءة 4-7 خانات صالحة (القاعدة الجديدة)
    perfect_success = 0  # كشف لوحة + قراءة 7 خانات (مرجعي)
    for i, img_path in enumerate(images, 1):
        img = imread_unicode(img_path)
        if img is None:
            continue
        # كشف لوحة
        pr = plate_model(img, conf=plate_conf, verbose=False)
        boxes = pr[0].boxes
        if boxes is None or len(boxes) == 0:
            continue
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, 'cpu') else boxes.xyxy
        confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, 'cpu') else boxes.conf
        idx = int(np.argmax(confs))
        x1, y1, x2, y2 = xyxy[idx].astype(int)
        crop = img[y1:y2, x1:x2].copy()
        crops.append(crop)

        # قراءة أحرف
        or_ = ocr_model(crop, conf=ocr_conf, verbose=False)
        ob = or_[0].boxes
        if ob is not None:
            n = len(ob)
            if 4 <= n <= 7:
                full_success += 1
            if n == 7:
                perfect_success += 1

    rate = full_success / len(images) if images else 0
    perfect_rate = perfect_success / len(images) if images else 0
    print(f"\n  📊 النتائج (القاعدة: 4-7 خانات صالحة):")
    print(f"     نجاح صالح (3 حروف + 1-4 أرقام): {rate*100:.1f}%  ({full_success}/{len(images)})")
    print(f"     نجاح مثالي (7 خانات بالضبط):    {perfect_rate*100:.1f}%  ({perfect_success}/{len(images)}) [مرجعي]")
    return {
        "end_to_end_rate": rate,
        "perfect_rate": perfect_rate,
        "successful": full_success,
        "perfect_successful": perfect_success,
        "crops": crops,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True,
                    help="مجلد الصور للاختبار. يدعم البحث في images/ subfolder تلقائياً.")
    ap.add_argument("--plate-conf", type=float, default=0.25)
    ap.add_argument("--ocr-conf", type=float, default=0.25)
    ap.add_argument("--mode", choices=["full", "ocr-only", "plate-only"],
                    default="full",
                    help="full=كل النماذج · ocr-only=الأحرف فقط (لوحات مقصوصة) · plate-only=كاشف اللوحات فقط")
    args = ap.parse_args()

    img_dir = Path(args.images)
    if not img_dir.exists():
        print(f"ERROR: المجلد غير موجود: {img_dir}")
        sys.exit(1)

    # محاولة العثور على images/ subfolder تلقائياً (Roboflow YOLO structure)
    if (img_dir / "images").exists() and (img_dir / "images").is_dir():
        img_dir = img_dir / "images"
        print(f"  ℹ تم العثور على subfolder 'images/' — سيُستخدم: {img_dir}")

    images = sorted([
        f for f in img_dir.iterdir()
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
    ])
    if not images:
        print(f"ERROR: لا توجد صور في {img_dir}")
        sys.exit(1)

    print(f"\n{'='*65}")
    print(f"  قياس دقة نماذج مرقاب")
    print(f"  الوضع:         {args.mode}")
    print(f"  المجلد:        {img_dir}")
    print(f"  عدد الصور:     {len(images)}")
    print(f"  Plate conf:    ≥ {args.plate_conf}")
    print(f"  OCR conf:      ≥ {args.ocr_conf}")
    print(f"{'='*65}")

    plate_stats = None
    ocr_stats = None
    e2e = None

    if args.mode == "ocr-only":
        # الصور هي لوحات مقصوصة → نشغّل OCR مباشرةً
        print(f"\n  🔧 وضع OCR-Only: نعتبر الصور لوحات مقصوصة جاهزة.")
        crops = [imread_unicode(p) for p in images]
        crops = [c for c in crops if c is not None]
        ocr_stats = measure_ocr_detector(crops, args.ocr_conf)
    elif args.mode == "plate-only":
        plate_stats = measure_plate_detector(images, args.plate_conf)
    else:  # full
        plate_stats = measure_plate_detector(images, args.plate_conf)
        e2e = end_to_end(images, args.plate_conf, args.ocr_conf)
        if e2e and e2e.get("crops"):
            ocr_stats = measure_ocr_detector(e2e["crops"], args.ocr_conf)

    # حفظ التقرير
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "input_dir": str(img_dir),
        "mode": args.mode,
        "n_images": len(images),
        "thresholds": {
            "plate_conf": args.plate_conf,
            "ocr_conf": args.ocr_conf,
        },
        "plate_detector": plate_stats,
        "ocr_detector": ocr_stats,
        "end_to_end": {k: v for k, v in (e2e or {}).items() if k != "crops"} if e2e else None,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n{'='*65}")
    print(f"  📄 التقرير الكامل: {REPORT_PATH}")
    print(f"{'='*65}\n")

    # ملخص نهائي
    print("الأرقام الجاهزة لـ صفحة 'معلومات النظام':\n")
    if plate_stats:
        print(f"  كاشف اللوحات:  معدل الكشف {plate_stats['detection_rate']*100:.1f}% · "
              f"متوسط الثقة {plate_stats['avg_conf']*100:.1f}%")
    if ocr_stats:
        print(f"  قارئ الأحرف:   قراءة صالحة {ocr_stats['complete_rate']*100:.1f}% · "
              f"متوسط ثقة {ocr_stats['avg_conf']*100:.1f}%")
    if e2e:
        print(f"  نجاح كامل:     {e2e['end_to_end_rate']*100:.1f}%")
    print()


if __name__ == "__main__":
    main()
