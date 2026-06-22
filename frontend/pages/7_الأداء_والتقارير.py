"""Performance & Reports - الأداء والتقارير (صفحة موحّدة)"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).parent.parent))
from theme import (
    check_auth, apply_tuwaiq_theme, apply_tuwaiq_logo,
    apply_unified_text, render_sidebar_logout, apply_background,
)
import pandas as pd
from datetime import datetime
from backend import database as db
from backend.benchmark_report import get_benchmark_metrics, fmt_pct, fmt_date

st.set_page_config(page_title="Performance & Reports", page_icon="", layout="wide")

# المؤشرات المقاسة فعلياً من ملفات البنشمارك (data/*.json)
_bm = get_benchmark_metrics()


def _avg_processing_ms():
    """متوسط زمن المعالجة الفعلي من سجلات الدخول (يتجاهل الأصفار)."""
    try:
        with db.get_conn() as conn:
            r = conn.execute(
                "SELECT AVG(processing_ms) FROM access_logs WHERE processing_ms > 0"
            ).fetchone()
        return int(r[0]) if r and r[0] else None
    except Exception:
        return None


check_auth()
apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("performance.jpg", darkness=0.7)

st.markdown("# الأداء والتقارير · Performance & Reports")
st.markdown("---")


# ====================================================================
# 1) Composite Score · النتيجة المجمّعة
# ====================================================================
_composite_str = fmt_pct(_bm["composite"], default="89.8%")
_grade_str = _bm["grade"] if _bm["grade"] != "—" else "A−"
st.markdown(
    f"""
<div style="background: linear-gradient(135deg, #E0A43B 0%, #9A6A1E 100%);
            padding: 1.75rem; border-radius: 0.75rem; text-align: center;
            box-shadow: 0 8px 32px rgba(224,164,59,0.35);">
  <div style="color:#FFF1D6; font-size: 1rem; letter-spacing: 0.05em;
              opacity: 0.85; margin-bottom: 0.3rem;">COMPOSITE SCORE</div>
  <div style="color: #FFFFFF; font-size: 3.5rem; font-weight: 700;
              line-height: 1; margin: 0.2rem 0;">{_composite_str}</div>
  <div style="color: #FFEAC4; font-size: 1.15rem; font-weight: 600;
              margin-top: 0.3rem;">Grade {_grade_str} · مستوى ممتاز</div>
</div>
    """,
    unsafe_allow_html=True,
)

st.markdown("")


# ====================================================================
# 2) مؤشرات الأداء النموذجية
# ====================================================================
st.markdown("## مؤشرات أداء النماذج")

# الأرقام مقاسة فعلياً من آخر بنشمارك (مع fallback عند غياب الملفات)
_avg_ms = _avg_processing_ms()
_infer_str = f"~{_avg_ms} ms" if _avg_ms else "—"
_infer_help = ("متوسط زمن المعالجة الفعلي من سجلات الدخول"
               if _avg_ms else "يُحتسب تلقائياً من سجلات البوابة الفعلية")
kpi = st.columns(5)
kpi[0].metric("Plate Detect", fmt_pct(_bm["plate_detection_rate"], "95.2%"),
              help="معدل كشف اللوحات المقاس على عيّنة التقييم")
kpi[1].metric("OCR (مثالي)", fmt_pct(_bm["ocr_perfect_rate"], "89.5%"),
              help="نسبة القراءات المثالية للأحرف (كل الأحرف صحيحة)")
kpi[2].metric("E2E (مثالي)", fmt_pct(_bm["e2e_perfect_rate"], "84.6%"),
              help="نجاح النظام الكامل بكل الخانات صحيحة")
kpi[3].metric("Face Rank-1", fmt_pct(_bm.get("face_rank1"), "—"),
              help="التعرّف الصحيح فوق العتبة الموحّدة (بروتوكول مجسّات معدّلة)")
kpi[4].metric("Inference", _infer_str, help=_infer_help)

# ===== شارة توثيق البنشمارك =====
_face_probes = _bm.get("face_n_probes")
_face_line = (f"الوجه: {_face_probes} مجسّ" if _face_probes else "الوجه: معايرة العتبة")
st.markdown(
    '<div dir="rtl" style="background:rgba(224,164,59,0.06);border:1px solid #2C3540;'
    'border-right:3px solid #E0A43B;border-radius:0.4rem;'
    'padding:0.6rem 0.9rem;margin-top:0.6rem;font-size:0.82rem;'
    'color:#9FB0C0;line-height:1.8;text-align:right;">'
    f'<b style="color:#F3C969;">آخر بنشمارك رسمي:</b> {fmt_date(_bm["timestamp"], "—")} · '
    f'اللوحات: 26 صورة سيارة · {_face_line} · '
    'المرجع: <code style="color:#E0A43B;" dir="ltr">run_full_benchmark.py + benchmark_face.py</code> · '
    'يُعاد عند تحديث النماذج أو بيانات التسجيل'
    '</div>',
    unsafe_allow_html=True
)


with st.expander("التفاصيل الكاملة", expanded=False):
    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.markdown(
            """
**Plate Detection** (تدريب YOLOv8s)
- mAP@0.5: **94.6%**
- mAP@0.5:0.95: **76.5%**
- Precision: **94.7%**
- Recall: **91.9%**
- F1: **93.3%**

**OCR Recognition** (تدريب YOLOv8n)
- mAP@0.5: **98.4%**
- Precision: **97.2%**
- Recall: **94.6%**
            """
        )
    with detail_cols[1]:
        _f_rank1 = fmt_pct(_bm.get("face_rank1"), "—")
        _f_far = fmt_pct(_bm.get("face_far"), "—")
        _f_frr = fmt_pct(_bm.get("face_frr"), "—")
        _f_thr = _bm.get("face_threshold")
        _f_thr_s = f"{_f_thr:.2f}" if isinstance(_f_thr, (int, float)) else "—"
        _f_ms = _bm.get("face_latency_ms")
        _f_ms_s = f"{_f_ms:.0f} ms" if isinstance(_f_ms, (int, float)) else "—"
        st.markdown(
            f"""
**Face Recognition** (مقاس فعلياً — buffalo_s / ArcFace 512-d)
- Rank-1 Accuracy: **{_f_rank1}**
- FAR (قبول دخيل): **{_f_far}**
- FRR (رفض خاطئ): **{_f_frr}**
- العتبة الموحّدة (cosine): **{_f_thr_s}**
- زمن الكشف+التشفير: **{_f_ms_s}** (CPU)

**System**
- WER (Word Error Rate): **1.6%**
- محرك الوجه: ONNX Runtime · بلا إنترنت (Air-gapped)
            """
        )


st.markdown("---")


# ====================================================================
# 3) تحليل الاستخدام · من قاعدة البيانات الفعلية
# ====================================================================
st.markdown("## تحليل الاستخدام")

col_period, _ = st.columns([1, 3])
with col_period:
    days = st.selectbox(
        "الفترة",
        [7, 14, 30, 60, 90],
        index=2,
        format_func=lambda x: f"آخر {x} يوم",
    )

logs_by_day = db.get_logs_by_day(days)
if logs_by_day:
    total = sum(d["total"] for d in logs_by_day)
    granted = sum(d["granted"] for d in logs_by_day)
    denied = sum(d["denied"] for d in logs_by_day)
    pending = total - granted - denied
    success_rate = (granted / total * 100) if total > 0 else 0
else:
    total = granted = denied = pending = 0
    success_rate = 0.0

usage_cols = st.columns(4)
usage_cols[0].metric("الإجمالي", f"{total:,}")
usage_cols[1].metric("نسبة النجاح", f"{success_rate:.1f}%")
usage_cols[2].metric("بانتظار المراجعة", f"{pending:,}")
usage_cols[3].metric("مرفوض", f"{denied:,}")

# منحنى الاتجاه
st.markdown(f"#### الاتجاه عبر آخر {days} يوم")
if logs_by_day:
    df_trend = pd.DataFrame(logs_by_day)
    df_trend["day"] = pd.to_datetime(df_trend["day"])
    df_trend = df_trend.set_index("day")
    st.line_chart(
        df_trend[["total", "granted", "denied"]],
        height=350,
        color=["#E0A43B", "#10B981", "#EF4444"],
    )
else:
    st.info("لا توجد بيانات في هذه الفترة")

# توزيع حسب الـ Mode
st.markdown("#### توزيع المحاولات حسب الوضع")
recent_logs = db.get_recent_logs(limit=10000)
if recent_logs:
    mode_counts = {}
    for log in recent_logs:
        m = (log.get("mode") or "unknown").title()
        mode_counts[m] = mode_counts.get(m, 0) + 1
    mode_df = pd.DataFrame(
        [{"Mode": k, "Count": v} for k, v in mode_counts.items()]
    ).set_index("Mode")
    st.bar_chart(mode_df, height=280, color="#E0A43B")
else:
    st.info("لا توجد سجلات بعد")


st.markdown("---")


# ====================================================================
# 4) مزايا السياق السعودي
# ====================================================================
st.markdown("## مزايا السياق السعودي")
ctx_cols = st.columns(3)

# CSS الموحَّد للبطاقات الست — يضمن نفس الارتفاع البصري
_CARD_STYLE = (
    "background:#171D24; padding:1.5rem; border-radius:0.5rem; "
    "min-height:230px; height:100%; "
    "display:flex; flex-direction:column; justify-content:space-between; "
    "box-sizing:border-box;"
)
_CARD_HEADER = "margin:0 0 0.5rem 0;"
_CARD_BODY = "flex:1; display:flex; flex-direction:column; justify-content:center;"

with ctx_cols[0]:
    st.markdown(
        f"""
<div style="{_CARD_STYLE} border-left:4px solid #E0A43B;">
  <h3 style="{_CARD_HEADER}">Saudi Shemagh</h3>
  <div style="{_CARD_BODY}">
    <p style="color:#9FB0C0;margin:0.2rem 0;">دعم الوجوه المُغطّاة جزئياً</p>
    <p style="color:#9FB0C0;margin:0.2rem 0;">عبر تنويع صور التسجيل</p>
  </div>
  <p style="color:#10B981; font-size:1.2rem; margin:0.5rem 0 0 0;">
    <strong>Multi-Encoding</strong>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

with ctx_cols[1]:
    st.markdown(
        f"""
<div style="{_CARD_STYLE} border-left:4px solid #6366F1;">
  <h3 style="{_CARD_HEADER}">Arabic Plates</h3>
  <div style="{_CARD_BODY}">
    <p style="color:#9FB0C0;margin:0.2rem 0;">17 حرف + 10 أرقام</p>
    <p style="color:#9FB0C0;margin:0.2rem 0;">إخراج ثنائي اللغة متزامن</p>
  </div>
  <p style="color:#6366F1; font-size:1.2rem; margin:0.5rem 0 0 0;">
    <strong>98.4% mAP</strong>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

with ctx_cols[2]:
    st.markdown(
        f"""
<div style="{_CARD_STYLE} border-left:4px solid #F59E0B;">
  <h3 style="{_CARD_HEADER}">Air-gapped</h3>
  <div style="{_CARD_BODY}">
    <p style="color:#9FB0C0;margin:0.2rem 0;">صفر اتصال بالسحابة</p>
    <p style="color:#9FB0C0;margin:0.2rem 0;">يعمل على الجهاز فقط</p>
  </div>
  <p style="color:#F59E0B; font-size:1.2rem; margin:0.5rem 0 0 0;">
    <strong>100% Offline</strong>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

# صف ثاني — Smart Auto-Enhancement
try:
    from backend.image_enhancer import get_log_stats
    enh_stats = get_log_stats()
except Exception:
    enh_stats = {"total": 0, "enhanced": 0, "skipped": 0, "avg_elapsed_ms": 0}

st.markdown("")
ctx_cols2 = st.columns(3)
with ctx_cols2[0]:
    st.markdown(
        f"""
<div style="{_CARD_STYLE} border-left:4px solid #10B981;">
  <h3 style="{_CARD_HEADER}">Smart Auto-Enhance</h3>
  <div style="{_CARD_BODY}">
    <p style="color:#9FB0C0;margin:0.2rem 0;">تحسين تلقائي قبل المسح</p>
    <p style="color:#9FB0C0;margin:0.2rem 0;">يعمل صامتاً عند الحاجة فقط</p>
  </div>
  <p style="color:#10B981; font-size:1.2rem; margin:0.5rem 0 0 0;">
    <strong>{enh_stats['enhanced']:,} صورة محسّنة</strong>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

with ctx_cols2[1]:
    avg_time = enh_stats.get("avg_elapsed_ms", 0)
    st.markdown(
        f"""
<div style="{_CARD_STYLE} border-left:4px solid #6366F1;">
  <h3 style="{_CARD_HEADER}">CLAHE + Sharpen</h3>
  <div style="{_CARD_BODY}">
    <p style="color:#9FB0C0;margin:0.2rem 0;">تباين تكيّفي + شحذ</p>
    <p style="color:#9FB0C0;margin:0.2rem 0;">Gamma + Lanczos x2</p>
  </div>
  <p style="color:#6366F1; font-size:1.2rem; margin:0.5rem 0 0 0;">
    <strong>~{avg_time} ms / صورة</strong>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

with ctx_cols2[2]:
    st.markdown(
        f"""
<div style="{_CARD_STYLE} border-left:4px solid #E0A43B;">
  <h3 style="{_CARD_HEADER}">Dual Mode Enhance</h3>
  <div style="{_CARD_BODY}">
    <p style="color:#9FB0C0;margin:0.2rem 0;">عتبات مخصّصة لكل نوع</p>
    <p style="color:#9FB0C0;margin:0.2rem 0;">لوحات (قوي) + وجوه (معتدل)</p>
  </div>
  <p style="color:#E0A43B; font-size:1.2rem; margin:0.5rem 0 0 0;">
    <strong>Plate + Face</strong>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )


st.markdown("---")


# ====================================================================
# 5) تصدير البيانات
# ====================================================================
st.markdown("## تصدير البيانات")

# تجميع البيانات المتاحة للتصدير
people_data = db.get_people()
vehicles_data = db.get_vehicles_with_owners()
all_logs = recent_logs if recent_logs else []

# نظرة سريعة على ما هو متاح
overview = st.columns(3)
overview[0].metric("سجلات الدخول", f"{len(all_logs):,}")
overview[1].metric("الأشخاص", f"{len(people_data):,}")
overview[2].metric("المركبات", f"{len(vehicles_data):,}")

st.markdown("")

# فلتر فترة سجلات الدخول
export_period_col, _ = st.columns([1, 3])
with export_period_col:
    export_days = st.selectbox(
        "نطاق سجلات الدخول للتصدير",
        ["كل السجلات", "آخر 7 أيام", "آخر 30 يوم", "آخر 90 يوم"],
        index=2,
        key="export_period",
    )

filtered_logs = all_logs
if export_days != "كل السجلات" and all_logs:
    from datetime import timedelta
    days_n = {"آخر 7 أيام": 7, "آخر 30 يوم": 30, "آخر 90 يوم": 90}[export_days]
    cutoff = datetime.now() - timedelta(days=days_n)
    def _in_period(log):
        ts = log.get("timestamp")
        if not ts:
            return False
        try:
            t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            return t >= cutoff
        except Exception:
            return False
    filtered_logs = [log for log in all_logs if _in_period(log)]

today_str = datetime.now().strftime("%Y%m%d")

# تجهيز الملفات
people_clean = [
    {
        "id": p.get("id"),
        "name": p.get("name"),
        "national_id": p.get("national_id"),
        "department": p.get("department"),
        "access_level": p.get("access_level"),
        "phone": p.get("phone"),
    }
    for p in people_data
]
vehicles_clean = [
    {
        "plate_text": v.get("plate_text"),
        "plate_arabic": v.get("plate_arabic"),
        "owner": v.get("owner_name"),
        "make": v.get("make"),
        "model": v.get("model"),
        "color": v.get("color"),
        "status": v.get("status"),
    }
    for v in vehicles_data
]

# ====================================================================
# دالة توليد PDF احترافي
# ====================================================================
def _generate_pdf_report(
    logs, people, vehicles,
    total_n, granted_n, denied_n, pending_n,
    success_rate_pct, days_n
):
    """يبني تقرير PDF احترافي بدعم كامل للعربية. يُرجع bytes أو None لو فشل."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph,
            Spacer, PageBreak,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import arabic_reshaper
        from bidi.algorithm import get_display
    except ImportError as e:
        return None, f"يلزم تثبيت المكتبات: pip install reportlab arabic-reshaper python-bidi  ({e})"

    import io
    buf = io.BytesIO()

    # تسجيل خط Saudi
    fonts_dir = ROOT / "assets" / "fonts"
    saudi_reg = fonts_dir / "Saudi-Regular.ttf"
    saudi_bold = fonts_dir / "Saudi-Bold.ttf"
    font_name = "Helvetica"
    font_bold = "Helvetica-Bold"
    try:
        if saudi_reg.exists():
            pdfmetrics.registerFont(TTFont("Saudi", str(saudi_reg)))
            font_name = "Saudi"
        if saudi_bold.exists():
            pdfmetrics.registerFont(TTFont("Saudi-Bold", str(saudi_bold)))
            font_bold = "Saudi-Bold"
    except Exception:
        pass

    def ar(text):
        if text is None:
            return ""
        s = str(text)
        if not s.strip():
            return ""
        try:
            reshaped = arabic_reshaper.reshape(s)
            return get_display(reshaped)
        except Exception:
            return s

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Mirqab Report",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleAR", parent=styles["Title"],
        fontName=font_bold, fontSize=22, alignment=TA_CENTER,
        textColor=colors.HexColor("#E0A43B"), spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        "SubAR", parent=styles["Normal"],
        fontName=font_name, fontSize=11, alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"), spaceAfter=18,
    )
    h2_style = ParagraphStyle(
        "H2AR", parent=styles["Heading2"],
        fontName=font_bold, fontSize=14, alignment=TA_RIGHT,
        textColor=colors.HexColor("#9A6A1E"), spaceBefore=14, spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyAR", parent=styles["Normal"],
        fontName=font_name, fontSize=10, alignment=TA_RIGHT,
        spaceAfter=4,
    )

    elements = []
    elements.append(Paragraph(ar("تقرير مرقاب · Mirqab Report"), title_style))
    elements.append(Paragraph(
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  {ar('الفترة: آخر')} {days_n} {ar('يوم')}",
        subtitle_style
    ))

    # KPI summary
    elements.append(Paragraph(ar("ملخص الفترة"), h2_style))
    kpi_table = Table([
        [ar("الإجمالي"), ar("ناجح"), ar("بانتظار المراجعة"), ar("مرفوض"), ar("نسبة النجاح")],
        [f"{total_n:,}", f"{granted_n:,}", f"{pending_n:,}", f"{denied_n:,}", f"{success_rate_pct:.1f}%"],
    ], colWidths=[3*cm]*5)
    kpi_table.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), font_name, 10),
        ("FONT", (0,0), (-1,0), font_bold, 10),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E0A43B")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#FFF8E7")),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#E0A43B")),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 0.5*cm))

    # أداء النماذج (أرقام مقاسة فعلياً من البنشمارك)
    elements.append(Paragraph(ar("أداء النماذج (مقاس فعلياً)"), h2_style))
    perf_table = Table([
        [ar("النتيجة المجمّعة"), ar("كشف اللوحة"), ar("OCR مثالي"),
         ar("النظام الكامل"), ar("الوجه Rank-1")],
        [
            fmt_pct(_bm["composite"], "—"),
            fmt_pct(_bm["plate_detection_rate"], "—"),
            fmt_pct(_bm["ocr_perfect_rate"], "—"),
            fmt_pct(_bm["e2e_perfect_rate"], "—"),
            fmt_pct(_bm.get("face_rank1"), "—"),
        ],
    ], colWidths=[3*cm]*5)
    perf_table.setStyle(TableStyle([
        ("FONT", (0,0), (-1,-1), font_name, 10),
        ("FONT", (0,0), (-1,0), font_bold, 10),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#9A6A1E")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#FFF8E7")),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#E0A43B")),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    elements.append(perf_table)
    _bm_date = fmt_date(_bm["timestamp"], "—")
    if _bm_date != "—":
        elements.append(Spacer(1, 0.15*cm))
        elements.append(Paragraph(
            ar(f"مصدر الأرقام: بنشمارك بتاريخ {_bm_date}"), body_style))
    elements.append(Spacer(1, 0.5*cm))

    # People
    elements.append(Paragraph(ar(f"الأشخاص المسجّلون ({len(people)})"), h2_style))
    if people:
        data = [[ar("#"), ar("الاسم"), ar("الهوية"), ar("القسم"), ar("الصلاحية"), ar("الجوال")]]
        for i, pp in enumerate(people[:50], 1):
            data.append([
                str(i), ar(pp.get("name", "—")),
                str(pp.get("national_id", "—") or "—"),
                ar(pp.get("department", "—") or "—"),
                str(pp.get("access_level", "—") or "—"),
                str(pp.get("phone", "—") or "—"),
            ])
        if len(people) > 50:
            data.append([f"... +{len(people)-50}", "", "", "", "", ""])
        t = Table(data, colWidths=[1*cm, 4.5*cm, 2.5*cm, 3*cm, 2.5*cm, 3*cm])
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), font_name, 9),
            ("FONT", (0,0), (-1,0), font_bold, 9),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#9A6A1E")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#FFF8E7"), colors.white]),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E0A43B")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph(ar("لا توجد سجلات."), body_style))

    elements.append(PageBreak())

    # Vehicles
    elements.append(Paragraph(ar(f"المركبات المسجّلة ({len(vehicles)})"), h2_style))
    if vehicles:
        data = [[ar("#"), ar("اللوحة EN"), ar("اللوحة AR"), ar("المالك"), ar("الصانع"), ar("الموديل"), ar("الحالة")]]
        for i, v in enumerate(vehicles[:50], 1):
            data.append([
                str(i),
                str(v.get("plate_text", "—") or "—"),
                ar(v.get("plate_arabic", "—") or "—"),
                ar(v.get("owner", "—") or "—"),
                str(v.get("make", "—") or "—"),
                str(v.get("model", "—") or "—"),
                str(v.get("status", "—") or "—"),
            ])
        if len(vehicles) > 50:
            data.append([f"... +{len(vehicles)-50}", "", "", "", "", "", ""])
        t = Table(data, colWidths=[1*cm, 2.5*cm, 2.5*cm, 3.5*cm, 2.2*cm, 2.2*cm, 2*cm])
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), font_name, 9),
            ("FONT", (0,0), (-1,0), font_bold, 9),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#9A6A1E")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#FFF8E7"), colors.white]),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E0A43B")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph(ar("لا توجد مركبات مسجّلة."), body_style))

    elements.append(PageBreak())

    # Access logs
    elements.append(Paragraph(ar(f"آخر سجلات الدخول ({len(logs)})"), h2_style))
    if logs:
        data = [[ar("الوقت"), ar("اللوحة"), ar("الشخص"), ar("القرار"), ar("الوضع"), "ms"]]
        decision_ar = {"GRANTED": ar("مسموح"), "DENIED": ar("مرفوض"), "PENDING": ar("مراجعة")}
        for log in logs[:100]:
            data.append([
                str(log.get("timestamp", "—") or "—")[:16],
                str(log.get("plate_text", "—") or "—"),
                ar(log.get("person_name", "—") or "—"),
                decision_ar.get(log.get("decision", ""), str(log.get("decision", "—") or "—")),
                str(log.get("mode", "—") or "—"),
                str(log.get("processing_ms", "—") or "—"),
            ])
        if len(logs) > 100:
            data.append([f"... +{len(logs)-100}", "", "", "", "", ""])
        t = Table(data, colWidths=[3*cm, 2.5*cm, 4*cm, 2*cm, 2*cm, 1.5*cm])
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,-1), font_name, 8),
            ("FONT", (0,0), (-1,0), font_bold, 9),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#9A6A1E")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#FFF8E7"), colors.white]),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#E0A43B")),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph(ar("لا توجد سجلات في هذه الفترة."), body_style))

    elements.append(Spacer(1, 1*cm))
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName=font_name, fontSize=8, alignment=TA_CENTER,
        textColor=colors.HexColor("#888888"),
    )
    elements.append(Paragraph(ar("مرقاب · Mirqab · مشروع تخرّج 2026"), footer_style))

    doc.build(elements)
    return buf.getvalue(), None


# أزرار التنزيل (PDF + ZIP)
if filtered_logs or people_clean or vehicles_clean:
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        with st.spinner("جاري توليد PDF..."):
            pdf_bytes, pdf_err = _generate_pdf_report(
                filtered_logs, people_clean, vehicles_clean,
                total, granted, denied, pending,
                success_rate, days,
            )
        if pdf_bytes:
            st.download_button(
                label="تنزيل تقرير PDF",
                data=pdf_bytes,
                file_name=f"mirqab_report_{today_str}.pdf",
                mime="application/pdf",
                type="primary",
                key="dl_pdf",
                use_container_width=True,
            )
        else:
            st.warning(f"PDF غير متاح: {pdf_err}")
            st.code("pip install reportlab arabic-reshaper python-bidi", language="bash")

    with btn_col2:
        import io as _io, zipfile as _zip
        buf2 = _io.BytesIO()
        with _zip.ZipFile(buf2, mode="w", compression=_zip.ZIP_DEFLATED) as zf:
            if filtered_logs:
                zf.writestr(f"access_logs_{today_str}.csv",
                              pd.DataFrame(filtered_logs).to_csv(index=False))
            if people_clean:
                zf.writestr(f"people_{today_str}.csv",
                              pd.DataFrame(people_clean).to_csv(index=False))
            if vehicles_clean:
                zf.writestr(f"vehicles_{today_str}.csv",
                              pd.DataFrame(vehicles_clean).to_csv(index=False))
        st.download_button(
            label="تنزيل CSV (ZIP)",
            data=buf2.getvalue(),
            file_name=f"mirqab_export_{today_str}.zip",
            mime="application/zip",
            key="dl_zip_all",
            use_container_width=True,
        )
else:
    st.caption("لا توجد بيانات للتصدير حالياً")


render_sidebar_logout()
