"""
run_full_benchmark.py
=====================
سكربت موحَّد لتشغيل اختبارَين متتاليَين:

1. **اختبار قارئ الأحرف** على dataset الـ27 فئة (لوحات مقصوصة)
2. **اختبار كاشف اللوحات + النظام الكامل** على صور سيارات

ينتج عنه:
- ملخص موحَّد لكل النماذج
- ملف JSON بتفاصيل كل اختبار
- الأرقام الجاهزة لاستخدامها في صفحة "معلومات النظام"

الاستخدام:
    python scripts/run_full_benchmark.py

أو مع مسارات مخصّصة:
    python scripts/run_full_benchmark.py ^
        --chars-dir "C:\\path\\to\\character-dataset\\test" ^
        --cars-dir "C:\\path\\to\\car-images"
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

# المسارات الافتراضية
DEFAULT_CHARS_DIR = Path(r"C:\Users\mohne\Desktop\License-Characters-by-2-27classes\test")
DEFAULT_CARS_DIR = ROOT / "data" / "test_cars"

MEASURE_SCRIPT = ROOT / "scripts" / "measure_accuracy.py"
REPORT_PATH = ROOT / "data" / "accuracy_report.json"
FINAL_REPORT_PATH = ROOT / "data" / "full_benchmark_report.json"


def run_test(test_name: str, images_dir: Path, mode: str) -> dict:
    """يشغّل measure_accuracy.py ويُرجع التقرير."""
    print(f"\n{'='*70}")
    print(f"  ▶ بدء: {test_name}")
    print(f"  المجلد: {images_dir}")
    print(f"  الوضع: {mode}")
    print(f"{'='*70}")

    if not images_dir.exists():
        print(f"  ✗ المجلد غير موجود — يُتخطّى الاختبار")
        return None

    cmd = [
        sys.executable, str(MEASURE_SCRIPT),
        "--images", str(images_dir),
        "--mode", mode,
    ]
    try:
        result = subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"  ✗ فشل الاختبار: exit code {e.returncode}")
        return None

    # قراءة التقرير
    if REPORT_PATH.exists():
        with open(REPORT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chars-dir", default=str(DEFAULT_CHARS_DIR),
                    help="مجلد لوحات مقصوصة لاختبار قارئ الأحرف")
    ap.add_argument("--cars-dir", default=str(DEFAULT_CARS_DIR),
                    help="مجلد صور سيارات لاختبار كاشف اللوحات والنظام الكامل")
    args = ap.parse_args()

    chars_dir = Path(args.chars_dir)
    cars_dir = Path(args.cars_dir)

    print("\n" + "="*70)
    print("    Mirqab · Full Benchmark Suite")
    print(f"    التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    print(f"  📁 dataset الأحرف:  {chars_dir}")
    print(f"  📁 صور السيارات:   {cars_dir}")

    # الاختبار 1: قارئ الأحرف
    ocr_report = run_test(
        "اختبار 1/2 · قارئ الأحرف على dataset الـ27 فئة",
        chars_dir,
        "ocr-only"
    )

    # الاختبار 2: كاشف اللوحات + النظام الكامل
    full_report = run_test(
        "اختبار 2/2 · كاشف اللوحات + النظام الكامل",
        cars_dir,
        "full"
    )

    # دمج النتائج
    combined = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "test_1_ocr_only": ocr_report,
        "test_2_full_pipeline": full_report,
    }

    FINAL_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FINAL_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2, default=str)

    # الملخص النهائي
    print("\n" + "="*70)
    print("    ⭐ الملخص النهائي — الأرقام الحقيقية المُقاسة")
    print("="*70)

    if ocr_report and ocr_report.get("ocr_detector"):
        ocr = ocr_report["ocr_detector"]
        print(f"\n  🔹 قارئ الأحرف (على {ocr_report['n_images']} لوحة مقصوصة)")
        print(f"      قراءة كاملة (7 خانات): {ocr['complete_rate']*100:>5.1f}%")
        print(f"      متوسط ثقة الحرف:        {ocr['avg_conf']*100:>5.1f}%")
        print(f"      متوسط الأحرف/لوحة:      {ocr['avg_chars_per_plate']:>5.1f}")
    else:
        print(f"\n  🔹 قارئ الأحرف: لم يُنفَّذ (تحقّق من المسار)")

    if full_report:
        if full_report.get("plate_detector"):
            pd = full_report["plate_detector"]
            print(f"\n  🔹 كاشف اللوحات (على {full_report['n_images']} صورة سيارة)")
            print(f"      معدل الكشف:         {pd['detection_rate']*100:>5.1f}%")
            print(f"      متوسط الثقة:        {pd['avg_conf']*100:>5.1f}%")
        if full_report.get("end_to_end"):
            e2e = full_report["end_to_end"]
            print(f"\n  🔹 النظام الكامل (لوحة + قراءة 7 خانات)")
            print(f"      النجاح الكامل:      {e2e['end_to_end_rate']*100:>5.1f}%")
    else:
        print(f"\n  🔹 كاشف اللوحات: لم يُنفَّذ (لا يوجد مجلد صور سيارات)")

    print()
    print(f"  📄 التقرير الكامل: {FINAL_REPORT_PATH}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
