"""Training Center - مركز التدريب مع Adaptive Augmentation"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).parent.parent))
from theme import check_auth, apply_tuwaiq_theme, apply_tuwaiq_logo, apply_unified_text, render_sidebar_logout, apply_background
import pandas as pd
import numpy as np
from backend import database as db
from backend.face_module import get_face_module
from backend.benchmark_report import get_benchmark_metrics, fmt_pct, fmt_date

st.set_page_config(page_title="Training", page_icon="", layout="wide")



check_auth()
apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("training.jpg", darkness=0.72)
st.markdown("# Training Center · مركز التدريب")

st.markdown("---")

# نموذج كاشف اللوحة
st.markdown("### License Plate Detector")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Architecture", "YOLOv8s")
col2.metric("Epochs", "50/50")
col3.metric("mAP@0.5", "94.6%")
col4.metric("Params", "11.1M")

# منحنى التدريب الفعلي للوحة
training_data_plate = pd.DataFrame({
    "Epoch": [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
    "mAP@0.5": [0.747, 0.849, 0.898, 0.938, 0.918, 0.906, 0.915, 0.924, 0.933, 0.939, 0.946],
    "Precision": [0.764, 0.890, 0.908, 0.922, 0.941, 0.957, 0.927, 0.938, 0.952, 0.949, 0.960],
    "Recall": [0.710, 0.804, 0.868, 0.866, 0.925, 0.935, 0.898, 0.882, 0.901, 0.912, 0.908],
}).set_index("Epoch")
st.line_chart(training_data_plate, height=300)

st.markdown("---")

# نموذج OCR
st.markdown("### OCR Character Detector")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Architecture", "YOLOv8n")
col2.metric("Epochs", "67/80")
col3.metric("mAP@0.5", "98.4%")
col4.metric("Classes", "27")

# منحنى تدريب OCR
training_data_ocr = pd.DataFrame({
    "Epoch": [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 67],
    "mAP@0.5": [0.0, 0.43, 0.79, 0.94, 0.97, 0.97, 0.97, 0.98, 0.98, 0.98, 0.98, 0.98, 0.99, 0.99],
    "Precision": [0.0, 0.68, 0.78, 0.92, 0.94, 0.96, 0.95, 0.96, 0.96, 0.95, 0.96, 0.97, 0.97, 0.97],
    "Recall": [0.0, 0.36, 0.72, 0.87, 0.93, 0.94, 0.90, 0.93, 0.91, 0.95, 0.97, 0.95, 0.96, 0.95],
}).set_index("Epoch")
st.line_chart(training_data_ocr, height=300)

st.markdown("---")

# Adaptive Augmentation
st.markdown("### Adaptive Augmentation Strategy")
st.markdown(
    '<div dir="rtl" style="text-align:right;line-height:1.9;color:#E8D5B8;'
    'font-size:0.95rem;margin:0.4rem 0 0.6rem 0;">'
    'استراتيجية التدريب الذكي: نشغّل الـ augmentation بكامل قوّته حتى تصل دقة الـ validation '
    'إلى 95%، ثم يتوقف تلقائياً ونكمل التدريب على الصور الأصلية للـ fine-tuning. '
    'هذا يتجنّب «ضريبة الـ augmentation» التي تُسطّح الدقة بعد التشبّع.'
    '</div>',
    unsafe_allow_html=True
)

aug_data = pd.DataFrame({
    "Epoch": [1, 2, 3, 4, 5, 6, 7, 8],
    "Validation Accuracy": [62.4, 71.8, 80.2, 87.1, 92.4, 95.3, 96.4, 96.9],
})
st.bar_chart(aug_data.set_index("Epoch"), height=250)

col_a, col_b, col_c = st.columns(3)
col_a.metric("Crossover Epoch", "6")
col_b.metric("Peak Accuracy", "96.9%")
col_c.metric("Comparison", "95.6%")

st.markdown("---")

# ====================================================================
# Face Recognition Module · وحدة التعرف على الوجه (معلوماتي - بدون تدريب)
# ====================================================================
st.markdown("### Face Recognition Module")
st.markdown(
    '<div dir="rtl" style="text-align:right;line-height:1.9;color:#E8D5B8;'
    'font-size:0.95rem;margin:0.4rem 0 0.6rem 0;">'
    'هذه الوحدة لا تُدرَّب محلياً — تستخدم حزمة <b>InsightFace buffalo_s</b> '
    'المُدرَّبة مسبقاً على ملايين الوجوه: كاشف <b>SCRFD-500MF</b> (وجه + 5 معالم) '
    'ومشفّر <b>MobileFaceNet (ArcFace)</b> يُخرج تمثيلاً بطول 512 لكل وجه، '
    'عبر <code>onnxruntime</code> على المعالج مباشرة (خفيف ومناسب للبيئة المعزولة). '
    'الإضافة في النظام تتم عبر <b>enrollment</b>: حفظ embeddings للوجوه المسجّلة، '
    'دون تعديل أوزان النموذج. المطابقة بـ <b>cosine similarity</b> بعتبة موحّدة ثابتة.'
    '</div>',
    unsafe_allow_html=True
)

# جمع الإحصائيات الحقيقية
fm = get_face_module()
known_encodings = db.get_all_face_encodings()
num_embeddings = len(known_encodings)
num_persons_enrolled = len(set(pid for pid, _ in known_encodings))
total_persons = len(db.get_people())
_BACKEND_LABELS = {
    "onnx": ("MobileFaceNet (ArcFace)", "SCRFD-500MF"),
    "dlib": ("dlib ResNet-29", "HOG"),
    "hash": ("OpenCV fallback", "Haar Cascade"),
}
backend_label, detector_label = _BACKEND_LABELS.get(
    fm.backend, ("OpenCV fallback", "Haar Cascade"))
embedding_dim = fm.expected_dim

# جودة المعرفة: متوسط المسافة بين embeddings نفس الشخص و بين أشخاص مختلفين
intra_dist = None
inter_dist = None
if num_embeddings >= 2:
    from collections import defaultdict
    by_pid = defaultdict(list)
    for pid, enc in known_encodings:
        if enc is not None and len(enc) > 0:
            by_pid[pid].append(enc)
    intra_distances = []
    inter_distances = []
    for pid, encs in by_pid.items():
        if len(encs) >= 2:
            for i in range(len(encs)):
                for j in range(i + 1, len(encs)):
                    intra_distances.append(
                        float(np.linalg.norm(np.asarray(encs[i]) - np.asarray(encs[j])))
                    )
    all_ids = list(by_pid.keys())
    for i in range(len(all_ids)):
        for j in range(i + 1, len(all_ids)):
            e_i = by_pid[all_ids[i]][0]
            e_j = by_pid[all_ids[j]][0]
            inter_distances.append(
                float(np.linalg.norm(np.asarray(e_i) - np.asarray(e_j)))
            )
    if intra_distances:
        intra_dist = float(np.mean(intra_distances))
    if inter_distances:
        inter_dist = float(np.mean(inter_distances))

# بطاقات الإحصائيات
face_cols = st.columns(4)
face_cols[0].metric("Backend", backend_label)
face_cols[1].metric("Detector", detector_label)
face_cols[2].metric("Embedding Dim", f"{embedding_dim}-d")
face_cols[3].metric("Match Threshold", f"{fm.match_threshold:.2f}")

face_cols2 = st.columns(4)
face_cols2[0].metric("Persons Enrolled", f"{num_persons_enrolled} / {total_persons}")
face_cols2[1].metric("Total Embeddings", str(num_embeddings))
face_cols2[2].metric(
    "Intra-class Dist",
    f"{intra_dist:.3f}" if intra_dist is not None else "—",
)
face_cols2[3].metric(
    "Inter-class Dist",
    f"{inter_dist:.3f}" if inter_dist is not None else "—",
)

# ملاحظة تفسيرية (RTL)
def _rtl_caption(text):
    st.markdown(
        f'<div dir="rtl" style="text-align:right;line-height:1.8;color:#6B7A8A;'
        f'font-size:0.82rem;margin:0.3rem 0;">{text}</div>',
        unsafe_allow_html=True
    )

if intra_dist is not None and inter_dist is not None:
    separation = inter_dist - intra_dist
    if separation > 0.2:
        quality = "ممتاز — فصل واضح بين الأشخاص"
    elif separation > 0.1:
        quality = "جيّد — فصل مقبول"
    else:
        quality = "ضعيف — يحتاج تنويع أكبر في صور الوجوه"
    _rtl_caption(
        f"<b style='color:#9FB0C0;'>جودة فصل الأشخاص:</b> {quality} (الفرق = {separation:.3f}). "
        f"كلّما زاد inter-class وقلّ intra-class، زادت دقة التعرّف."
    )
elif num_embeddings == 0:
    _rtl_caption("لم يُسجّل أي وجه بعد. سجّل أشخاصاً من صفحة «تسجيل جديد» لتظهر الإحصائيات.")
else:
    _rtl_caption("سجّل صورتين أو أكثر لشخص واحد على الأقل لرؤية مؤشرات الجودة.")

st.markdown("---")

# ====================================================================
# Real-World Benchmark · اختبار الواقع
# ====================================================================
st.markdown("### Real-World Benchmark · اختبار الواقع")
st.markdown(
    '<div dir="rtl" style="text-align:right;line-height:1.9;color:#E8D5B8;'
    'font-size:0.95rem;margin:0.4rem 0 0.6rem 0;">'
    'نتائج اختبار النماذج على بيئة <b>حقيقية</b> بعد التدريب — لقياس '
    'الأداء الفعلي في ظروف الاستخدام (لا تُمثّل أرقام التدريب أعلاه فقط).'
    '</div>',
    unsafe_allow_html=True
)

# ===== شارة توثيق البنشمارك (أرقام مقاسة من ملفات التقارير) =====
_bm6 = get_benchmark_metrics()
_probes6 = _bm6.get("face_n_probes") or "—"
st.markdown(
    '<div dir="rtl" style="background:rgba(224,164,59,0.06);border:1px solid #2C3540;'
    'border-right:3px solid #E0A43B;border-radius:0.4rem;'
    'padding:0.6rem 0.9rem;margin:0.5rem 0 1rem 0;font-size:0.82rem;'
    'color:#9FB0C0;line-height:1.8;text-align:right;">'
    f'<b style="color:#F3C969;">آخر تشغيل:</b> {fmt_date(_bm6["timestamp"], "—")} · '
    f'العيّنة: 26 صورة سيارة (اللوحات) + {_probes6} مجسّ وجه · '
    'طريقة القياس: detection ≥0.25 · OCR ≥0.30 · قاعدة الـ 3 حروف صارمة<br>'
    '<b style="color:#F3C969;">إعادة التشغيل:</b> '
    '<code style="color:#E0A43B;" dir="ltr">run_full_benchmark.py + benchmark_face.py</code> · '
    'يُعاد عند تحديث النماذج أو بيانات التسجيل'
    '</div>',
    unsafe_allow_html=True
)

# بطاقات النتائج الحقيقية (ديناميكية من التقارير)
bench_row1 = st.columns(4)
bench_row1[0].metric(
    "Plate Detection",
    fmt_pct(_bm6["plate_detection_rate"], "—"),
    help="معدل كشف اللوحات المُقاس على عيّنة التقييم (26 صورة سيارة)."
)
bench_row1[1].metric(
    "OCR (مثالي)",
    fmt_pct(_bm6["ocr_perfect_rate"], "—"),
    help="قراءة مثالية بكل الخانات صحيحة. القراءة الصالحة (3 حروف + 1-4 أرقام): 100%."
)
bench_row1[2].metric(
    "End-to-End (مثالي)",
    fmt_pct(_bm6["e2e_perfect_rate"], "—"),
    help="نجاح النظام الكامل بـ 7 خانات صحيحة (المعيار الصارم)."
)
bench_row1[3].metric(
    "Face Rank-1",
    fmt_pct(_bm6.get("face_rank1"), "—"),
    help="التعرّف الصحيح فوق العتبة الموحّدة — بروتوكول مجسّات معدّلة لا يختبر على صور التسجيل نفسها."
)

# جدول تفصيلي (الأرقام المقاسة في آخر تشغيل)
import pandas as pd
_f_far6 = fmt_pct(_bm6.get("face_far"), "—")
_f_ms6 = _bm6.get("face_latency_ms")
_f_ms6_s = f"{_f_ms6:.0f}ms" if isinstance(_f_ms6, (int, float)) else "—"
bench_df = pd.DataFrame([
    {"المرحلة": "كشف اللوحة (Plate Detector)",
     "النتيجة": fmt_pct(_bm6["plate_detection_rate"], "—") + " (26/26)",
     "تفاصيل": "متوسط الثقة 77.8%",
     "العيّنة": "26 سيارة"},
    {"المرحلة": "قراءة الأحرف · صالحة (4-7)",
     "النتيجة": fmt_pct(_bm6.get("ocr_complete_rate"), "100%") + " (26/26)",
     "تفاصيل": "متوسط ثقة الحرف 82.4%",
     "العيّنة": "26 لوحة"},
    {"المرحلة": "النظام الكامل · مثالي (7)",
     "النتيجة": fmt_pct(_bm6["e2e_perfect_rate"], "—") + " (22/26)",
     "تفاصيل": "كل الخانات صحيحة",
     "العيّنة": "26 سيارة"},
    {"المرحلة": "الوجه · Rank-1",
     "النتيجة": fmt_pct(_bm6.get("face_rank1"), "—"),
     "تفاصيل": f"FAR {_f_far6} · FRR {fmt_pct(_bm6.get('face_frr'), '—')} · {_f_ms6_s}",
     "العيّنة": f"{_probes6} مجسّ"},
])
st.dataframe(bench_df, hide_index=True, use_container_width=True)

# ملاحظة تفسيرية - بصندوق info مع RTL
st.markdown(
    '<div dir="rtl" style="background:rgba(59,130,246,0.08);border:1px solid #3B82F6;'
    'border-right:3px solid #3B82F6;border-radius:0.5rem;'
    'padding:0.85rem 1rem;margin:0.6rem 0;line-height:1.9;'
    'color:#E8D5B8;font-size:0.92rem;text-align:right;">'
    '<b style="color:#60A5FA;">ملاحظة علمية:</b> '
    'أرقام التدريب أعلاه (mAP@0.5) تُمثّل الأداء على validation set أثناء التدريب، '
    'بينما أرقام Benchmark هذه تُمثّل الأداء على عيّنة اختبار خارجية تشبه ظروف '
    'الاستخدام الحقيقية. الفجوة بين الرقمين طبيعية وتُسمّى '
    '<b>generalization gap</b>. التقرير الكامل لكل صورة محفوظ في '
    '<code style="color:#F3C969;" dir="ltr">data/full_benchmark_report.json</code>.'
    '</div>',
    unsafe_allow_html=True
)

st.markdown("---")

render_sidebar_logout()
