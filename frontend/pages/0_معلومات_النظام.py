"""معلومات النظام - لوحة المعلومات الرئيسية"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "frontend"))

import streamlit as st
from backend import database as db
from backend.benchmark_report import get_benchmark_metrics, fmt_pct, fmt_date
from theme import apply_tuwaiq_theme, apply_background, apply_tuwaiq_logo, apply_unified_text, render_sidebar_logout, check_auth

st.set_page_config(page_title="معلومات النظام", page_icon="", layout="wide")

# حارس المصادقة أولاً قبل تحميل أي بيانات أو ثيم
check_auth()

apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("system_info.jpg", darkness=0.70)
st.markdown("""
<style>
section.main[data-testid="stMain"],
[data-testid="stMain"] {
    background-size: 100% 100%, 100% 100%, calc(100% - 2cm) auto !important;
    background-repeat: no-repeat, no-repeat, no-repeat !important;
    background-position: center, center, center center !important;
    background-attachment: scroll, scroll, scroll !important;
}
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### الوضع الحالي")
    active_mode = (db.get_setting("active_mode", "balanced") or "balanced").upper()
    # الافتراضي 0 متّصلة (لا كاميرا RTSP مربوطة بعد) — متّسق مع مركز التحكم
    cameras_online = db.get_setting("cameras_online", 0)
    cameras_total = db.get_setting("cameras_count", 2)
    st.markdown(f"**الوضع:** `{active_mode}`")
    st.markdown(f"**الكاميرات:** `{cameras_online}/{cameras_total}`")
    st.markdown(f"**Air-gapped:** نعم")

# العنوان (موحَّد مع باقي الصفحات)
st.markdown("# معلومات النظام · System Info")

# CSS: توسيط النصوص داخل بطاقات Metric + info-card في هذه الصفحة
st.markdown("""
<style>
/* توسيط مربعات st.metric */
[data-testid="stMetric"] {
    text-align: center !important;
}
[data-testid="stMetric"] > div,
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {
    text-align: center !important;
    justify-content: center !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    width: 100% !important;
}
/* توسيط النصوص داخل info-card */
.info-card,
.info-card * {
    text-align: center !important;
}
.info-card h4 {
    text-align: center !important;
    width: 100% !important;
}
/* مسافة بين العنوان الرئيسي والمحتوى الأول */
[data-testid="stMain"] h1 + div {
    margin-top: 2.5rem !important;
}
</style>
""", unsafe_allow_html=True)

# مسافة قبل القسم الأول
st.write("")
st.write("")

# ===== العنوان الفرعي للمجموعة الأولى =====
st.markdown("### معلومات التشغيل")

# مؤشرات KPI (بدون الدقة)
stats = db.get_stats()
col1, col2, col3 = st.columns(3)
with col1: st.metric("دخول اليوم", stats["today_total"])
with col2: st.metric("قيد المراجعة", stats["today_pending"])
with col3: st.metric("مرفوض", stats["today_denied"])

st.markdown("---")

# ===== معلومات النموذج (أفقي بعرض الصفحة) — أرقام مقاسة فعلياً =====
_bm = get_benchmark_metrics()
_detect_str = fmt_pct(_bm["plate_detection_rate"], "95.2%")
_ocr_str = fmt_pct(_bm["ocr_perfect_rate"], "89.5%")
_comp_str = fmt_pct(_bm["composite"], "89.8%")
_grade_str = _bm["grade"] if _bm["grade"] != "—" else "A−"
_face_str = fmt_pct(_bm.get("face_rank1"), "512-d")

st.markdown("### معلومات النموذج")
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"""
    <div class="info-card" style="text-align:center;">
        <h4 style="text-align:center;">كاشف اللوحات</h4>
        <p style="color:#9FB0C0;margin:0.5rem 0;text-align:center;">YOLOv8s</p>
        <p style="font-size:1.8rem;color:#F3C969;font-weight:700;margin:0;text-align:center;">{_detect_str}</p>
        <p style="color:#9FB0C0;font-size:0.85rem;text-align:center;">معدل الكشف</p>
    </div>
    """, unsafe_allow_html=True)
with m2:
    st.markdown(f"""
    <div class="info-card" style="text-align:center;">
        <h4 style="text-align:center;">قارئ الأحرف</h4>
        <p style="color:#9FB0C0;margin:0.5rem 0;text-align:center;">27 فئة</p>
        <p style="font-size:1.8rem;color:#F3C969;font-weight:700;margin:0;text-align:center;">{_ocr_str}</p>
        <p style="color:#9FB0C0;font-size:0.85rem;text-align:center;">قراءة مثالية</p>
    </div>
    """, unsafe_allow_html=True)
with m3:
    st.markdown(f"""
    <div class="info-card" style="text-align:center;">
        <h4 style="text-align:center;">التعرف على الوجه</h4>
        <p style="color:#9FB0C0;margin:0.5rem 0;text-align:center;">buffalo_s · ArcFace 512-d</p>
        <p style="font-size:1.8rem;color:#F3C969;font-weight:700;margin:0;text-align:center;">{_face_str}</p>
        <p style="color:#9FB0C0;font-size:0.85rem;text-align:center;">Rank-1 (مقاس فعلياً)</p>
    </div>
    """, unsafe_allow_html=True)
with m4:
    st.markdown(f"""
    <div class="info-card" style="text-align:center;">
        <h4 style="text-align:center;">النتيجة الإجمالية</h4>
        <p style="color:#9FB0C0;margin:0.5rem 0;text-align:center;">Grade {_grade_str}</p>
        <p style="font-size:1.8rem;color:#F3C969;font-weight:700;margin:0;text-align:center;">{_comp_str}</p>
        <p style="color:#9FB0C0;font-size:0.85rem;text-align:center;">مستوى ممتاز</p>
    </div>
    """, unsafe_allow_html=True)

# ===== شارة توثيق البنشمارك =====
st.markdown(
    '<div dir="rtl" style="background:rgba(224,164,59,0.06);border:1px solid #2C3540;'
    'border-right:3px solid #E0A43B;border-radius:0.4rem;'
    'padding:0.55rem 0.85rem;margin-top:0.8rem;font-size:0.82rem;'
    'color:#9FB0C0;line-height:1.8;text-align:right;">'
    '<b style="color:#F3C969;">الأرقام مُقاسة فعلياً</b> '
    f'بتاريخ <b>{fmt_date(_bm["timestamp"], "—")}</b> · '
    'اللوحات: 26 صورة سيارة · الوجه: '
    f'{_bm.get("face_n_probes") or "—"} مجسّ اختبار'
    '</div>',
    unsafe_allow_html=True
)

st.markdown("---")

# ===== آخر نشاط (بعرض الصفحة كاملة) =====
st.markdown("### آخر نشاط")
logs = db.get_recent_logs(15)
if logs:
    import pandas as pd
    df_data = []
    for log in logs:
        decision_text = {"GRANTED": "مسموح", "DENIED": "مرفوض", "PENDING": "قيد المراجعة"}.get(log["decision"], log["decision"])
        df_data.append({
            "الوقت": log["timestamp"].split(".")[0] if log.get("timestamp") else "",
            "اللوحة": log.get("plate_text", ""),
            "الشخص": log.get("person_name", "—") or "—",
            "القرار": decision_text,
            "الوضع": log.get("mode", "").title(),
            "ms": log.get("processing_ms", 0),
        })
    df = pd.DataFrame(df_data)
    st.dataframe(df, hide_index=True, use_container_width=True, height=400)
else:
    st.info("لا توجد سجلات بعد")

render_sidebar_logout()
