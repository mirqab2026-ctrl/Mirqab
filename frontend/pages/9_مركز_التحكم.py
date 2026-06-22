"""Control Center - مركز التحكم"""
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
from backend import database as db
from backend.decision import MODES, set_active_mode
import shutil
from datetime import datetime, timedelta

st.set_page_config(page_title="Control Center", page_icon="", layout="wide")


check_auth()
apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("admin.jpg", darkness=0.72)

st.markdown("# مركز التحكم · Control Center")
st.markdown("---")


# ====================================================================
# 1) شريط حالة حية في الأعلى — System Status Bar
# ====================================================================
def _status_pill(label, value, color):
    # سطر واحد بدون indent — يمنع Markdown من تفسيره code block
    return (
        f'<div style="background:rgba(23,29,36,0.85);border:1px solid {color};'
        f'border-radius:999px;padding:0.45rem 1rem;display:inline-flex;'
        f'align-items:center;gap:0.6rem;font-size:0.9rem;color:#E6ECF2;'
        f'font-family:\'Saudi\',system-ui,sans-serif;">'
        f'<span style="width:0.55rem;height:0.55rem;border-radius:50%;'
        f'background:{color};box-shadow:0 0 8px {color};"></span>'
        f'<span style="color:#9FB0C0;">{label}</span>'
        f'<strong style="color:{color};letter-spacing:0.02em;">{value}</strong>'
        f'</div>'
    )


# فحص حالة قاعدة البيانات
try:
    with db.get_conn() as conn:
        conn.execute("SELECT 1").fetchone()
    db_status = ("سليمة", "#10B981")
except Exception:
    db_status = ("خلل", "#EF4444")

# عدد السجلات الإجمالي
try:
    with db.get_conn() as conn:
        total_logs = conn.execute("SELECT COUNT(*) FROM access_logs").fetchone()[0]
except Exception:
    total_logs = 0

# الوضع النشط
active_mode_name = db.get_setting("active_mode", "balanced")
active_mode = MODES.get(active_mode_name, MODES["balanced"])

# حجم قاعدة البيانات
db_path = Path(__file__).parent.parent.parent / "data" / "gate.db"
db_size_mb = round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0

# عرض الشريط — متوسّط أفقياً
pills_html = (
    '<div style="display:flex; gap:0.6rem; flex-wrap:wrap; '
    'justify-content:center; align-items:center; '
    'margin:0.5rem 0 1.2rem 0;">'
    + _status_pill("النظام", "يعمل", "#10B981")
    + _status_pill("قاعدة البيانات", db_status[0], db_status[1])
    + _status_pill("الوضع النشط", active_mode.label, "#F3C969")
    + _status_pill("Air-gapped", "نعم", "#6366F1")
    + "</div>"
)
st.markdown(pills_html, unsafe_allow_html=True)


# ====================================================================
# 2) لوحة المؤشرات الحيّة — Live KPIs
# ====================================================================
st.markdown("## لوحة المؤشرات الحيّة")

# سجلات اليوم
try:
    with db.get_conn() as conn:
        today_count = conn.execute(
            "SELECT COUNT(*) FROM access_logs WHERE DATE(timestamp)=DATE('now')"
        ).fetchone()[0]
except Exception:
    today_count = 0

# عدد الأشخاص والمركبات
people_count = len(db.get_people())
vehicles_count = len(db.get_vehicles_with_owners())

m = st.columns(4)
m[0].metric("سجلات اليوم", f"{today_count:,}")
m[1].metric("الإجمالي", f"{total_logs:,}")
m[2].metric("الأشخاص", f"{people_count:,}")
m[3].metric("المركبات", f"{vehicles_count:,}")


st.markdown("---")


# ====================================================================
# 3) إعدادات التعرف — Recognition Mode
# ====================================================================
st.markdown("## وضع التعرف النشط")

mode_col1, mode_col2 = st.columns([2, 3])

with mode_col1:
    # قائمة منسدلة لتغيير الوضع
    mode_options = list(MODES.keys())
    mode_labels = {k: MODES[k].label for k in mode_options}
    current_idx = mode_options.index(active_mode_name) if active_mode_name in mode_options else 1
    new_mode = st.selectbox(
        "اختر الوضع",
        mode_options,
        index=current_idx,
        format_func=lambda x: f"{mode_labels[x]} ({x})",
        key="mode_select",
    )
    if new_mode != active_mode_name:
        if st.button("تطبيق الوضع الجديد", type="primary", use_container_width=True):
            set_active_mode(new_mode)
            st.success(f"تم التغيير إلى وضع {mode_labels[new_mode]}")
            st.rerun()

with mode_col2:
    # عرض تفاصيل الوضع الحالي
    mode_info = MODES[active_mode_name]
    require_both_text = "كلاهما مطلوب" if mode_info.require_both else "أحدهما كافٍ"
    st.markdown(
        f"""
<div style="background:#171D24; padding:1.1rem 1.4rem; border-radius:0.6rem;
            border-left:4px solid #E0A43B; height:100%;">
  <div style="display:flex; justify-content:space-between; align-items:start;">
    <h4 style="margin:0; color:#F3C969;">{mode_info.label}</h4>
    <span style="color:#9FB0C0; font-size:0.85rem;">{mode_info.use_case}</span>
  </div>
  <p style="color:#E6ECF2; margin:0.5rem 0;">{mode_info.description}</p>
  <hr style="border-color:#2C3540; margin:0.6rem 0;">
  <div style="display:flex; gap:1.5rem; flex-wrap:wrap; color:#9FB0C0; font-size:0.9rem;">
    <div>عتبة اللوحة: <strong style="color:#FFE0A0;">{mode_info.plate_conf_threshold:.0%}</strong></div>
    <div>عتبة الوجه: <strong style="color:#FFE0A0;">{mode_info.face_conf_threshold:.0%}</strong></div>
    <div>التحقق: <strong style="color:#FFE0A0;">{require_both_text}</strong></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


st.markdown("---")


# ====================================================================
# 4) معلومات النظام — System Info
# ====================================================================
st.markdown("## معلومات النظام")

info_cols = st.columns(4)
info_cols[0].metric("الإصدار", "v6.0")
info_cols[1].metric("حجم القاعدة", f"{db_size_mb:.1f} MB")

# عدد الكاميرات
cameras_count = int(db.get_setting("cameras_count", 2) or 2)
cameras_online = int(db.get_setting("cameras_online", 0) or 0)
info_cols[2].metric("الكاميرات", f"{cameras_online} / {cameras_count}")

# آخر سجل
try:
    with db.get_conn() as conn:
        last_log = conn.execute(
            "SELECT timestamp FROM access_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    last_log_time = last_log[0] if last_log else "—"
except Exception:
    last_log_time = "—"
info_cols[3].metric("آخر نشاط", last_log_time.split(" ")[0] if " " in last_log_time else last_log_time)


st.markdown("---")


# ====================================================================
# 5) الكاميرات — Cameras (placeholder for future RTSP)
# ====================================================================
st.markdown("## مصادر الفيديو")

cam_cols = st.columns(2)
with cam_cols[0]:
    st.markdown(
        """
<div style="background:#171D24; padding:1.2rem; border-radius:0.6rem;
            border-left:4px solid #E0A43B;">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <h4 style="margin:0;">Camera A · المركبة</h4>
    <span style="background:#9A6A1E; color:#FFEAC4; padding:0.2rem 0.6rem;
                 border-radius:999px; font-size:0.75rem; font-weight:600;">OFFLINE</span>
  </div>
  <p style="color:#9FB0C0; margin:0.5rem 0;">RTSP / IP Camera</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    cam_a_url = st.text_input("RTSP URL", "", key="cam_a_url",
                                placeholder="rtsp://192.168.1.10/stream")

with cam_cols[1]:
    st.markdown(
        """
<div style="background:#171D24; padding:1.2rem; border-radius:0.6rem;
            border-left:4px solid #6366F1;">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <h4 style="margin:0;">Camera B · السائق</h4>
    <span style="background:#9A6A1E; color:#FFEAC4; padding:0.2rem 0.6rem;
                 border-radius:999px; font-size:0.75rem; font-weight:600;">OFFLINE</span>
  </div>
  <p style="color:#9FB0C0; margin:0.5rem 0;">RTSP / IP Camera</p>
</div>
        """,
        unsafe_allow_html=True,
    )
    cam_b_url = st.text_input("RTSP URL", "", key="cam_b_url",
                                placeholder="rtsp://192.168.1.11/stream")

if st.button("حفظ إعدادات الكاميرات", use_container_width=False):
    if cam_a_url:
        db.set_setting("cam_a_rtsp", cam_a_url)
    if cam_b_url:
        db.set_setting("cam_b_rtsp", cam_b_url)
    st.success("تم حفظ الإعدادات. سيُحاول النظام الاتصال عند تشغيل البوابة المباشرة.")


st.markdown("---")


# ====================================================================
# 6) النسخ الاحتياطي — Backup
# ====================================================================
st.markdown("## النسخ الاحتياطي")

backup_dir = Path(__file__).parent.parent.parent / "data" / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)

# قائمة النسخ السابقة
backups = sorted(backup_dir.glob("gate_backup_*.db"), reverse=True)
last_backup_str = "—"
if backups:
    last_backup_str = backups[0].stem.replace("gate_backup_", "")

bk_cols = st.columns([2, 1, 1])
with bk_cols[0]:
    st.markdown(
        f"""
<div style="background:#171D24; padding:1.1rem 1.4rem; border-radius:0.6rem;
            border-left:4px solid #A855F7;">
  <h4 style="margin:0; color:#F3C969;">آخر نسخة احتياطية</h4>
  <p style="color:#E6ECF2; font-size:1.2rem; margin:0.4rem 0;">
    <strong>{last_backup_str}</strong>
  </p>
  <p style="color:#9FB0C0; margin:0; font-size:0.85rem;">
    عدد النسخ المتوفرة: <strong>{len(backups)}</strong>
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )

with bk_cols[1]:
    st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)
    if st.button("إنشاء نسخة الآن", use_container_width=True):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = backup_dir / f"gate_backup_{ts}.db"
            shutil.copy2(db_path, dest)
            st.success(f"تم إنشاء النسخة: {dest.name}")
            st.rerun()
        except Exception as e:
            st.error(f"فشل النسخ: {e}")

with bk_cols[2]:
    st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)
    if backups and st.button("حذف القديم (>30 يوم)", use_container_width=True):
        cutoff = datetime.now() - timedelta(days=30)
        removed = 0
        for b in backups:
            try:
                ts_str = b.stem.replace("gate_backup_", "")
                t = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                if t < cutoff:
                    b.unlink()
                    removed += 1
            except Exception:
                continue
        st.success(f"تم حذف {removed} نسخة قديمة")
        st.rerun()


st.markdown("---")


# ====================================================================
# 7) منطقة الخطر — Danger Zone
# ====================================================================
st.markdown("## منطقة الخطر")
st.caption("هذه العمليات لا يمكن التراجع عنها. تأكّد قبل التنفيذ.")

dz_cols = st.columns(2)

with dz_cols[0]:
    st.markdown(
        """
<div dir="rtl" style="background:rgba(239,68,68,0.08); padding:1rem 1.2rem;
            border-radius:0.6rem; border-right:4px solid #EF4444; height:100%;
            text-align:right;">
  <h4 style="margin-top:0; color:#FCA5A5; text-align:right;">إعادة تعيين قاعدة البيانات</h4>
  <p style="color:#FECACA; font-size:0.9rem; line-height:1.9; text-align:right; margin:0;">
    حذف <strong>كل</strong> الأشخاص والمركبات والسجلات وإعادة إنشاء البيانات التجريبية.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )
    confirm_reset = st.checkbox("أؤكد إعادة التعيين (لا رجعة)", key="confirm_reset_db")
    if confirm_reset and st.button("تنفيذ إعادة التعيين",
                                       type="primary", key="exec_reset_db",
                                       use_container_width=True):
        try:
            db.seed_db()
            st.success("تم إعادة التعيين بنجاح")
            st.rerun()
        except Exception as e:
            st.error(f"فشل: {e}")

with dz_cols[1]:
    st.markdown(
        """
<div dir="rtl" style="background:rgba(245,158,11,0.08); padding:1rem 1.2rem;
            border-radius:0.6rem; border-right:4px solid #F59E0B; height:100%;
            text-align:right;">
  <h4 style="margin-top:0; color:#FCD34D; text-align:right;">مسح سجلات الدخول فقط</h4>
  <p style="color:#FDE68A; font-size:0.9rem; line-height:1.9; text-align:right; margin:0;">
    حذف <strong><span dir="ltr">access_logs</span></strong> فقط مع الإبقاء على الأشخاص والمركبات والإعدادات.
  </p>
</div>
        """,
        unsafe_allow_html=True,
    )
    confirm_clear = st.checkbox("أؤكد مسح السجلات", key="confirm_clear_logs")
    if confirm_clear and st.button("تنفيذ مسح السجلات",
                                       type="primary", key="exec_clear_logs",
                                       use_container_width=True):
        try:
            with db.get_conn() as conn:
                conn.execute("DELETE FROM access_logs")
            st.success("تم مسح كل سجلات الدخول")
        except Exception as e:
            st.error(f"فشل: {e}")


render_sidebar_logout()
