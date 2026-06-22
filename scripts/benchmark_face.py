# -*- coding: utf-8 -*-
"""
قياس أداء نظام التعرف على الوجه (buffalo_s / ArcFace 512-d)
=============================================================
بروتوكول صادق (لا يختبر على نفس الترميزات المخزنة):
  - المعرض (Gallery): ترميزات قاعدة البيانات الفعلية — نفس ما تستخدمه
    البوابة الحية تماماً.
  - المجسّات (Probes): نسخ معدّلة من صور كل شخص (قلب، إضاءة، ضبابية،
    دقة منخفضة) تحاكي ظروف الكاميرا — مختلفة عن المخزن.

المؤشرات:
  - Rank-1 Accuracy : هل أقرب تطابق هو الشخص الصحيح وفوق العتبة؟
  - False Accept    : مجسّ بعد استبعاد صاحبه من المعرض — هل يُقبل خطأً؟
  - زمن المعالجة    : كشف + تشفير + مطابقة (ms لكل صورة)

الناتج: data/face_benchmark_report.json (تقرأه صفحات الواجهة تلقائياً)

الاستخدام:
    python scripts/benchmark_face.py
"""
import sys
import json
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend import database as db                               # noqa: E402
from backend.face_module import get_face_module, imread_unicode  # noqa: E402
from backend.config import FACE_MATCH_THRESHOLD                  # noqa: E402

REPORT_PATH = ROOT / "data" / "face_benchmark_report.json"


def _augment(img):
    """نسخ تحاكي ظروف البوابة (مختلفة عن صورة التسجيل المخزنة)."""
    out = [cv2.flip(img, 1),
           cv2.convertScaleAbs(img, alpha=1.0, beta=35),
           cv2.convertScaleAbs(img, alpha=0.8, beta=-25),
           cv2.GaussianBlur(img, (5, 5), 1.2)]
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(64, w // 3), max(64, h // 3)))
    out.append(cv2.resize(small, (w, h)))
    return out


def main():
    fm = get_face_module()
    if fm.backend != "onnx":
        print(f"خطأ: المحرك '{fm.backend}' — القياس مخصص لمحرك onnx.")
        return 1

    db.init_db()
    thr = FACE_MATCH_THRESHOLD

    # ===== المعرض: ترميزات قاعدة البيانات الحقيقية (مطبّعة) =====
    gallery = [(pid, enc) for pid, enc in db.get_all_face_encodings()
               if enc is not None and len(enc) == fm.expected_dim]
    if not gallery:
        print("لا توجد ترميزات 512-d في قاعدة البيانات — شغّل الترحيل أولاً.")
        return 1
    g_ids = np.array([pid for pid, _ in gallery])
    g_mat = np.stack([e for _, e in gallery]).astype(np.float32)
    g_mat /= (np.linalg.norm(g_mat, axis=1, keepdims=True) + 1e-8)
    enrolled = set(int(i) for i in g_ids)

    # ===== المجسّات من صور الأشخاص =====
    from scripts.migrate_face_encodings import person_image_paths
    people = {p["id"]: p for p in db.get_people() if p["id"] in enrolled}
    print(f"المعرض: {len(gallery)} ترميز لـ {len(enrolled)} شخص | "
          f"العتبة الموحّدة: {thr:.2f}")
    print("توليد المجسّات وقياس الأداء (قد يستغرق دقائق)...")

    n_probes = 0
    rank1_hits = 0            # الشخص الصحيح + فوق العتبة
    top1_correct = 0          # الشخص الصحيح بغضّ النظر عن العتبة
    rejected = 0              # تحت العتبة (رفض)
    false_accepts = 0         # قُبل كشخص آخر (الأخطر أمنياً)
    impostor_accepts = 0      # سيناريو دخيل: صاحب المجسّ خارج المعرض
    impostor_trials = 0
    latencies = []
    genuine_sims = []

    for pid, person in people.items():
        for img_path in person_image_paths(person):
            base = imread_unicode(img_path)
            if base is None:
                continue
            for probe in _augment(base):
                t0 = time.perf_counter()
                enc = fm.encode_face(probe)
                if enc is None:
                    continue
                q = enc / (np.linalg.norm(enc) + 1e-8)
                sims = g_mat @ q
                ms = (time.perf_counter() - t0) * 1000
                latencies.append(ms)
                n_probes += 1

                # --- سيناريو التعرّف العادي ---
                top = int(np.argmax(sims))
                top_pid, top_sim = int(g_ids[top]), float(sims[top])
                if top_pid == pid:
                    top1_correct += 1
                    genuine_sims.append(top_sim)
                if top_sim >= thr:
                    if top_pid == pid:
                        rank1_hits += 1
                    else:
                        false_accepts += 1
                else:
                    rejected += 1

                # --- سيناريو الدخيل: استبعد صاحب المجسّ من المعرض ---
                mask = g_ids != pid
                if mask.any():
                    impostor_trials += 1
                    if float(sims[mask].max()) >= thr:
                        impostor_accepts += 1

    if n_probes == 0:
        print("لم يُنتج أي مجسّ — تحقق من الصور.")
        return 1

    rank1 = rank1_hits / n_probes
    top1 = top1_correct / n_probes
    frr = rejected / n_probes
    far_open = false_accepts / n_probes
    far_impostor = impostor_accepts / max(1, impostor_trials)
    lat = float(np.mean(latencies))
    lat_p95 = float(np.percentile(latencies, 95))

    print("-" * 64)
    print(f"المجسّات: {n_probes}")
    print(f"Rank-1 (صحيح + فوق العتبة)   : {rank1:.1%}")
    print(f"Top-1 (صحيح بلا عتبة)        : {top1:.1%}")
    print(f"رفض خاطئ FRR                 : {frr:.1%}")
    print(f"قبول خاطئ (كشخص آخر)         : {far_open:.2%}")
    print(f"قبول دخيل غير مسجّل FAR      : {far_impostor:.2%}")
    print(f"زمن المعالجة: متوسط {lat:.0f}ms · p95 {lat_p95:.0f}ms")

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "engine": "InsightFace buffalo_s (SCRFD + MobileFaceNet 512-d, ONNX/CPU)",
        "threshold": thr,
        "gallery_encodings": len(gallery),
        "enrolled_people": len(enrolled),
        "n_probes": n_probes,
        "rank1_accuracy": round(rank1, 4),
        "top1_accuracy": round(top1, 4),
        "false_reject_rate": round(frr, 4),
        "false_accept_rate": round(far_open, 4),
        "impostor_accept_rate": round(far_impostor, 4),
        "genuine_sim_mean": round(float(np.mean(genuine_sims)), 4) if genuine_sims else None,
        "avg_latency_ms": round(lat, 1),
        "p95_latency_ms": round(lat_p95, 1),
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"حُفظ التقرير: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
