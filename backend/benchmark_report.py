"""
benchmark_report.py
====================
يحمّل تقارير البنشمارك المقاسة فعلياً من مجلد data/ ويستخرج المؤشرات
الجاهزة للعرض في الواجهة — بدل كتابة الأرقام يدوياً في الصفحات.

المصادر:
- data/full_benchmark_report.json  (الأساسي: كشف اللوحة + OCR + end-to-end)
- data/accuracy_report.json        (احتياطي)
- data/face_benchmark_report.json  (الوجه: Rank-1 / FAR / FRR / زمن)
- data/face_threshold_report.json  (معايرة العتبة الموحّدة)

كل الدوال آمنة: عند غياب الملفات تُعيد قيماً افتراضية موثّقة (fallback)
حتى لا تنكسر الواجهة.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# قيم احتياطية موثّقة (تُستخدم فقط إن تعذّر قراءة ملفات JSON)
_FALLBACK = {
    "available": False,
    "timestamp": None,
    "plate_detection_rate": 0.952,
    "plate_avg_conf": None,
    "n_plate_images": None,
    "ocr_complete_rate": None,
    "ocr_perfect_rate": 0.895,
    "ocr_avg_conf": None,
    "e2e_perfect_rate": 0.846,
    "e2e_rate": None,
    # الوجه (تُملأ من face_benchmark_report.json بعد تشغيل القياس)
    "face_available": False,
    "face_rank1": None,
    "face_far": None,
    "face_frr": None,
    "face_threshold": None,
    "face_latency_ms": None,
    "face_engine": None,
    "face_n_probes": None,
}


def _safe_load(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _g(d, *keys, default=None):
    """وصول آمن متداخل: _g(d, 'a', 'b') == d['a']['b'] أو default."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


def get_benchmark_metrics() -> dict:
    """يُرجع dict بالمؤشرات المقاسة (أو fallback عند غياب الملفات).

    المفاتيح المهمّة:
        available           هل قُرئت أرقام حقيقية؟
        timestamp           وقت آخر بنشمارك (ISO) أو None
        plate_detection_rate, plate_avg_conf, n_plate_images
        ocr_complete_rate, ocr_perfect_rate, ocr_avg_conf
        e2e_perfect_rate, e2e_rate
        composite           النتيجة المجمّعة (0..1) = متوسط المؤشرات الرئيسية
        grade               تقدير حرفي مشتقّ من composite
    """
    full = _safe_load(DATA_DIR / "full_benchmark_report.json")
    acc = _safe_load(DATA_DIR / "accuracy_report.json")

    m = dict(_FALLBACK)

    # المصدر الأساسي: التقرير الكامل (test_2_full_pipeline)
    t2 = _g(full, "test_2_full_pipeline") if full else None
    if not t2 and acc:
        t2 = acc  # accuracy_report بنفس بنية test_2 تقريباً

    if t2:
        m["available"] = True
        m["timestamp"] = _g(full, "timestamp") or _g(t2, "timestamp")
        m["plate_detection_rate"] = _g(t2, "plate_detector", "detection_rate",
                                        default=m["plate_detection_rate"])
        m["plate_avg_conf"] = _g(t2, "plate_detector", "avg_conf")
        m["n_plate_images"] = _g(t2, "plate_detector", "total_images")
        m["ocr_complete_rate"] = _g(t2, "ocr_detector", "complete_rate")
        m["ocr_perfect_rate"] = _g(t2, "ocr_detector", "perfect_rate",
                                   default=m["ocr_perfect_rate"])
        m["ocr_avg_conf"] = _g(t2, "ocr_detector", "avg_conf")
        m["e2e_perfect_rate"] = _g(t2, "end_to_end", "perfect_rate",
                                   default=m["e2e_perfect_rate"])
        m["e2e_rate"] = _g(t2, "end_to_end", "end_to_end_rate")

    # ===== الوجه: من قياس الأداء + معايرة العتبة =====
    face = _safe_load(DATA_DIR / "face_benchmark_report.json")
    if face:
        m["face_available"] = True
        m["face_rank1"] = _g(face, "rank1_accuracy")
        m["face_far"] = _g(face, "impostor_accept_rate")
        m["face_frr"] = _g(face, "false_reject_rate")
        m["face_threshold"] = _g(face, "threshold")
        m["face_latency_ms"] = _g(face, "avg_latency_ms")
        m["face_engine"] = _g(face, "engine")
        m["face_n_probes"] = _g(face, "n_probes")
    else:
        fcal = _safe_load(DATA_DIR / "face_threshold_report.json")
        if fcal:
            # احتياطي: من تقرير المعايرة فقط (TPR عند أفضل عتبة)
            m["face_available"] = True
            m["face_rank1"] = _g(fcal, "tpr_at_best")
            m["face_far"] = _g(fcal, "fpr_at_best")
            m["face_threshold"] = _g(fcal, "best_threshold_youden")

    # النتيجة المجمّعة = متوسط المؤشرات الرئيسية المتاحة
    components = [
        m["plate_detection_rate"],
        m["ocr_perfect_rate"],
        m["e2e_perfect_rate"],
        m["face_rank1"],
    ]
    components = [c for c in components if isinstance(c, (int, float))]
    m["composite"] = sum(components) / len(components) if components else None
    m["grade"] = _grade(m["composite"])
    return m


def _grade(composite) -> str:
    """تقدير حرفي من النتيجة المجمّعة (0..1)."""
    if composite is None:
        return "—"
    pct = composite * 100
    if pct >= 93:
        return "A"
    if pct >= 88:
        return "A−"
    if pct >= 83:
        return "B+"
    if pct >= 78:
        return "B"
    return "C"


def fmt_pct(value, default="—") -> str:
    """تنسيق نسبة (0..1) إلى '84.6%' بأمان."""
    if not isinstance(value, (int, float)):
        return default
    return f"{value * 100:.1f}%"


def fmt_date(iso_ts, default="—") -> str:
    """يحوّل ISO timestamp إلى 'YYYY-MM-DD' بأمان."""
    if not iso_ts:
        return default
    return str(iso_ts)[:10]


if __name__ == "__main__":
    import pprint
    pprint.pprint(get_benchmark_metrics())
