"""
سكربت اختبار سريع للـ pipeline على صورة واحدة
"""
from pathlib import Path
from plate_ocr import PlateOCR

PROJECT = Path(__file__).parent.parent

ocr = PlateOCR(
    detector_path=PROJECT / "models" / "license_plate_detector.pt",
    ocr_path=PROJECT / "models" / "ocr_chars_detector.pt",
    char_map_path=PROJECT / "ocr_training" / "character_map.json",
    detector_conf=0.25,
    ocr_conf=0.30,
)

# اختبار على صورة (غيّر المسار حسب الحاجة)
test_image = PROJECT / "test_images" / "sample.jpg"
if not test_image.exists():
    print(f"⚠️ ضع صورة اختبار في: {test_image}")
    exit(1)

result = ocr.read(test_image)
print(f"عدد اللوحات: {result['num_plates']}")
for i, plate in enumerate(result["plates"]):
    print(f"\nلوحة {i+1}:")
    print(f"  bbox: {plate['bbox']}")
    print(f"  ثقة الكشف: {plate['confidence']:.2%}")
    print(f"  النص: {plate.get('text', '')}")
    print(f"  عدد الأحرف: {len(plate.get('characters', []))}")

# حفظ صورة مع التعليق
out_path = PROJECT / "test_images" / "result_annotated.jpg"
ocr.visualize(test_image, out_path)
