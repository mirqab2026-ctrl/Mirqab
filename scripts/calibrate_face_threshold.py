# -*- coding: utf-8 -*-
"""
معايرة العتبة الموحّدة للوجه (cosine similarity)
==================================================
يبني توزيعين من صور الأشخاص المسجلين:
  - أزواج حقيقية (نفس الشخص): صور متعددة لنفس الشخص + نسخ معدّلة
    (قلب أفقي، سطوع، ضبابية خفيفة) تحاكي ظروف الكاميرا.
  - أزواج دخيلة (أشخاص مختلفون): مقارنات متقاطعة بين الأشخاص.

ثم يحسب:
  - أفضل عتبة بمعيار Youden (TPR - FPR)
  - نقطة EER (تساوي الخطأين)
ويحفظ تقريراً في data/face_threshold_report.json

بعد التشغيل: ثبّت القيمة المختارة يدوياً في backend/config.py
(FACE_MATCH_THRESHOLD) — هذا مقصود، فالعتبة قرار كود لا إعداد واجهة.

الاستخدام:
    python scripts/calibrate_face_threshold.py
"""
import sys
import json
import itertools
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend import database as db                              # noqa: E402
from backend.face_module import get_face_module, imread_unicode  # noqa: E402

REPORT_PATH = ROOT / "data" / "face_threshold_report.json"
MAX_IMPOSTOR_PAIRS = 4000


def augment(img: np.ndarray) -> list:
    """نسخ معدّلة تحاكي ظروف البوابة (إضاءة/ضبابية/زاوية مرآة)."""
    out = [cv2.flip(img, 1)]                                   # قلب أفقي
    out.append(cv2.convertScaleAbs(img, alpha=1.0, beta=35))   # أفتح
    out.append(cv2.convertScaleAbs(img, alpha=0.8, beta=-25))  # أغمق
    out.append(cv2.GaussianBlur(img, (5, 5), 1.2))             # ضبابية خفيفة
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(64, w // 3), max(64, h // 3)))
    out.append(cv2.resize(small, (w, h)))                      # دقة منخفضة
    return out


def collect_embeddings(fm) -> dict:
    """{person_id: [embeddings]} من photo_path و data/faces/<pid>."""
    from scripts.migrate_face_encodings import person_image_paths
    people = db.get_people()
    bank = {}
    for person in people:
        embs = []
        for img_path in person_image_paths(person):
            img = imread_unicode(img_path)
            if img is None:
                continue
            base = fm.encode_face(img)
            if base is not None:
                embs.append(base)
            for aug in augment(img):
                e = fm.encode_face(aug)
                if e is not None:
                    embs.append(e)
        if len(embs) >= 2:
            bank[person["id"]] = embs
    return bank


def main():
    fm = get_face_module()
    if fm.backend != "onnx":
        print(f"خطأ: المحرك النشط '{fm.backend}' — المعايرة مخصصة لمحرك onnx.")
        return 1

    db.init_db()
    print("جمع الترميزات (قد يستغرق دقائق حسب عدد الصور)...")
    bank = collect_embeddings(fm)
    print(f"أشخاص صالحون للمعايرة (≥2 ترميز): {len(bank)}")
    if len(bank) < 2:
        print("لا يكفي — أضف صوراً أكثر أو سجّل أشخاصاً إضافيين.")
        return 1

    # أزواج حقيقية
    genuine = []
    for embs in bank.values():
        for a, b in itertools.combinations(embs, 2):
            genuine.append(float(np.dot(a, b)))

    # أزواج دخيلة (عينة محدودة كي لا تنفجر التركيبات)
    rng = np.random.default_rng(42)
    pids = list(bank.keys())
    impostor = []
    pair_pool = list(itertools.combinations(pids, 2))
    rng.shuffle(pair_pool)
    for p1, p2 in pair_pool:
        for a in bank[p1][:3]:
            for b in bank[p2][:3]:
                impostor.append(float(np.dot(a, b)))
        if len(impostor) >= MAX_IMPOSTOR_PAIRS:
            break

    g = np.array(genuine)
    i = np.array(impostor)
    print(f"أزواج حقيقية: {len(g)} (متوسط {g.mean():.3f} ± {g.std():.3f})")
    print(f"أزواج دخيلة : {len(i)} (متوسط {i.mean():.3f} ± {i.std():.3f})")

    # مسح العتبات
    thresholds = np.arange(0.05, 0.95, 0.01)
    best_t, best_j = 0.45, -1.0
    eer_t, eer_gap = 0.45, 9.9
    rows = []
    for t in thresholds:
        tpr = float((g >= t).mean())          # قبول صحيح
        fpr = float((i >= t).mean())          # قبول خاطئ (الأخطر أمنياً)
        fnr = 1.0 - tpr
        j = tpr - fpr
        rows.append({"threshold": round(float(t), 2),
                     "tpr": round(tpr, 4), "fpr": round(fpr, 4)})
        if j > best_j:
            best_j, best_t = j, float(t)
        if abs(fpr - fnr) < eer_gap:
            eer_gap, eer_t = abs(fpr - fnr), float(t)

    tpr_b = float((g >= best_t).mean())
    fpr_b = float((i >= best_t).mean())
    print("-" * 60)
    print(f"أفضل عتبة (Youden) : {best_t:.2f}  → قبول صحيح {tpr_b:.1%}، "
          f"قبول خاطئ {fpr_b:.2%}")
    print(f"عتبة EER           : {eer_t:.2f}")
    print(f"\nالتوصية: ثبّت FACE_MATCH_THRESHOLD في backend/config.py "
          f"بين {best_t:.2f} و {min(best_t + 0.05, 0.9):.2f} "
          f"(الأعلى = أكثر أماناً).")

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "backend": fm.backend,
        "people_used": len(bank),
        "genuine_pairs": len(g),
        "impostor_pairs": len(i),
        "genuine_mean": round(float(g.mean()), 4),
        "impostor_mean": round(float(i.mean()), 4),
        "best_threshold_youden": round(best_t, 2),
        "eer_threshold": round(eer_t, 2),
        "tpr_at_best": round(tpr_b, 4),
        "fpr_at_best": round(fpr_b, 4),
        "curve": rows,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"حُفظ التقرير: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
