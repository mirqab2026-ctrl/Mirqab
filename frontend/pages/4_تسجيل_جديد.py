"""Register - تسجيل شخص أو مركبة أو كلاهما + الربط"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).parent.parent))
from theme import check_auth, apply_tuwaiq_theme, apply_tuwaiq_logo, apply_unified_text, render_sidebar_logout, apply_background
from plate_widget import plate_input
import cv2
import numpy as np
from backend import database as db
from backend.face_module import get_face_module
from backend import face_correction as fc
from backend.plate_normalizer import to_canonical, to_arabic_display

st.set_page_config(page_title="Register", page_icon="", layout="wide")



check_auth()
apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("register.jpg", darkness=0.72)
st.markdown("# Register · تسجيل جديد")
st.markdown("سجّل شخصاً جديداً، مركبة جديدة، أو كلاهما معاً مع الربط التلقائي")
st.markdown("---")

# CSS لجعل حقل اللوحة بالعربي RTL (المعيار السعودي: أرقام يساراً + حروف يميناً)
st.markdown("""
<style>
input[aria-label*="اللوحة بالعربي"] {
    direction: rtl !important;
    unicode-bidi: plaintext !important;
    text-align: right !important;
    font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
    letter-spacing: 0.05em !important;
    font-size: 1rem !important;
}
</style>
""", unsafe_allow_html=True)

face_module = get_face_module()

# Tabs
tab_p, tab_v, tab_pv = st.tabs([
    "شخص فقط",
    "مركبة فقط",
    "شخص + مركبة (مع ربط)"
])


def render_person_form(form_key="person_only"):
    """يعرض form الشخص ويعيد النتيجة عند الحفظ."""
    col_info, col_face = st.columns(2)

    with col_info:
        st.markdown("### المعلومات الشخصية")
        name = st.text_input("الاسم الكامل *",
                              placeholder="Mohammed Al-Ahmadi",
                              key=f"{form_key}_name")
        national_id = st.text_input("الهوية الوطنية (اختياري)",
                                      placeholder="1023456789",
                                      max_chars=10,
                                      key=f"{form_key}_nid")
        department = st.selectbox("القسم",
            ["Engineering", "Marketing", "Operations", "IT",
              "Executive", "Security", "Visitor"],
            key=f"{form_key}_dept")
        access_level = st.selectbox("مستوى الوصول",
            ["Staff", "VIP", "Visitor"],
            key=f"{form_key}_lvl")
        phone = st.text_input("الجوال",
                                placeholder="+966...",
                                key=f"{form_key}_phone")

    with col_face:
        st.markdown("### صور الوجه")
        st.markdown(
            '<div dir="rtl" style="background:rgba(224,164,59,0.08);border:1px solid #8B5A2A;'
            'border-right:3px solid #E0A43B;'
            'border-radius:0.4rem;padding:0.6rem 0.9rem;margin-bottom:0.5rem;'
            'font-size:0.85rem;line-height:1.9;color:#9FB0C0;text-align:right;">'
            '<b style="color:#F3C969;">من صورة واحدة حتى 10 صور</b> '
            '<span style="color:#6B7A8A;">(حسب المتوفر — كلما زاد التنويع تحسّن التعرّف)</span><br>'
            '<span style="color:#6B7A8A;">'
            '• صورة أمامية واضحة<br>'
            '• صور بزوايا مختلفة (<span dir="ltr">±30° / ±45°</span>)<br>'
            '• مع/بدون نظارة شمسية<br>'
            '• مع/بدون شماغ أو غطاء رأس<br>'
            '• إضاءات متنوّعة (نهار/ليل/ظل)'
            '</span>'
            '</div>',
            unsafe_allow_html=True
        )
        face_files_raw = st.file_uploader("صور الوجه",
                                        type=["jpg", "jpeg", "png"],
                                        accept_multiple_files=True,
                                        key=f"{form_key}_faces")

        # ✨ الحد الأقصى الصارم: 10 صور
        _MAX_FACES = 10
        face_files = face_files_raw[:_MAX_FACES] if face_files_raw else []
        if face_files_raw and len(face_files_raw) > _MAX_FACES:
            st.warning(
                f"⚠ تم رفع {len(face_files_raw)} صورة — "
                f"سيُستخدم أول {_MAX_FACES} فقط (تجاهل {len(face_files_raw) - _MAX_FACES})."
            )

        if face_files:
            _n = len(face_files)
            _pct = _n / _MAX_FACES
            st.progress(_pct)
            # شارة لونية حسب عدد الصور
            if _n >= 7:
                _ratio_color = "#10B981"
                _hint = "تنويع ممتاز — تعرّف عالي الدقة"
            elif _n >= 4:
                _ratio_color = "#10B981"
                _hint = "تنويع جيد"
            elif _n >= 2:
                _ratio_color = "#F59E0B"
                _hint = "مقبول — يُفضّل إضافة المزيد"
            else:
                _ratio_color = "#F59E0B"
                _hint = "صورة واحدة فقط — تعرّف محدود"
            st.markdown(
                f'<div style="color:{_ratio_color};font-size:0.9rem;font-weight:600;margin:0.3rem 0;">'
                f'{_n} / {_MAX_FACES} صور · {_hint}'
                f'</div>',
                unsafe_allow_html=True
            )

            # ✨ معاينة كل صورة في صفوف من 5 أعمدة + فحص وجود وجه
            def _render_face_thumb(idx, f):
                """يعرض ميزانية واحدة مع badge وجه."""
                try:
                    _bytes = f.getvalue()
                    _img = cv2.imdecode(np.frombuffer(_bytes, np.uint8), cv2.IMREAD_COLOR)
                    _has_face = False
                    if _img is not None:
                        _locs = face_module.detect_faces(_img)
                        _has_face = len(_locs) > 0
                    _badge_color = "#10B981" if _has_face else "#EF4444"
                    _badge_text = "✓ وجه" if _has_face else "✗ لا يوجد"
                    st.image(f, use_container_width=True)
                    st.markdown(
                        f'<div style="text-align:center;color:{_badge_color};'
                        f'font-size:0.75rem;font-weight:700;margin-top:-0.3rem;">'
                        f'{_badge_text}</div>',
                        unsafe_allow_html=True
                    )
                except Exception:
                    st.image(f, use_container_width=True)

            # عرض في صفوف من 5 أعمدة (لمنع الصور من أن تصير صغيرة جداً عند 10)
            _per_row = 5
            for _row_start in range(0, _n, _per_row):
                _row_items = face_files[_row_start:_row_start + _per_row]
                _row_cols = st.columns(_per_row)
                for i, f in enumerate(_row_items):
                    with _row_cols[i]:
                        _render_face_thumb(_row_start + i, f)

    return {
        "name": name, "national_id": national_id,
        "department": department, "access_level": access_level,
        "phone": phone, "face_files": face_files,
    }


def save_person(data):
    """يحفظ شخصاً في DB ويعيد person_id أو None. المطلوب: الاسم فقط."""
    if not data["name"] or not str(data["name"]).strip():
        st.error("اسم الشخص مطلوب")
        return None

    # الهوية اختيارية — الفارغة تُخزَّن NULL (العمود UNIQUE يرفض تكرار "")
    _nid = (data.get("national_id") or "").strip() or None
    try:
        person_id = db.add_person(
            data["name"].strip(), _nid, data["department"],
            data["access_level"], data["phone"]
        )
    except Exception as e:
        st.error(f"خطأ في الإنشاء: {e}")
        return None

    n_encodings = 0
    n_failed = 0
    if data.get("face_files"):
        _total = len(data["face_files"])
        _progress = st.progress(0, text=f"معالجة 0/{_total} صورة...")
        for idx, ff in enumerate(data["face_files"][:10]):  # حد أقصى 10
            try:
                img_bytes = ff.getvalue() if hasattr(ff, 'getvalue') else ff.read()
                img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8),
                                    cv2.IMREAD_COLOR)
                if img is not None:
                    encoding = face_module.encode_face(img)
                    if encoding is not None:
                        db.add_face_encoding(person_id, encoding)
                        n_encodings += 1
                        from backend.face_correction import _save_face_image
                        _save_face_image(person_id, img)
                    else:
                        n_failed += 1
                else:
                    n_failed += 1
            except Exception:
                n_failed += 1
            _progress.progress((idx + 1) / _total,
                               text=f"معالجة {idx+1}/{_total} صورة...")
        _progress.empty()

    # تقرير مفصّل بعد الحفظ
    if data.get("face_files"):
        if n_encodings == 0:
            st.warning("⚠ لم يُكتشف وجه في أي من الصور المرفوعة — الشخص محفوظ بدون تعريف وجه")
        elif n_failed > 0:
            st.info(
                f"تم حفظ **{n_encodings}** تشفير وجه من أصل **{n_encodings + n_failed}** صورة. "
                f"({n_failed} صورة بدون وجه واضح — تجاهلت)"
            )
        else:
            _quality_hint = (
                "تنويع ممتاز · تعرّف عالي الدقة في كل الأوضاع" if n_encodings >= 7
                else "تنويع جيد · تعرّف موثوق في معظم الحالات" if n_encodings >= 4
                else "تعرّف أساسي · يُفضّل إضافة المزيد لاحقاً لتحسين الدقة"
            )
            st.success(
                f"تم حفظ **{n_encodings}** تشفير وجه بنجاح — {_quality_hint}"
            )
    return person_id


def render_vehicle_form(form_key="vehicle_only", default_owner=None):
    """يعرض form المركبة ويعيد البيانات."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### معلومات المركبة")
        st.markdown("**اللوحة (اكتب بأي لغة — النظام يتعرّف تلقائياً)**")
        # المكوّن الموحّد: حقل واحد + شبكة معاينة EN/AR + تحقّق
        plate_text = plate_input(
            label="اللوحة (اكتب بالعربي أو الإنجليزي)",
            key=f"{form_key}_plate",
            default="",
            show_preview=True,
            show_validation=True,
        )
        # نُولّد الـ AR تلقائياً للحفظ (compatibility مع DB الحالية)
        plate_arabic = to_arabic_display(plate_text) if plate_text else ""
        make = st.text_input("الصانع",
                              placeholder="Toyota",
                              key=f"{form_key}_make")
        model = st.text_input("الموديل",
                                placeholder="Camry",
                                key=f"{form_key}_model")

    with col2:
        st.markdown("### تفاصيل إضافية")
        color = st.text_input("اللون",
                                placeholder="Silver",
                                key=f"{form_key}_color")
        status = st.selectbox("الحالة",
            ["Active", "VIP", "Review", "Suspended"],
            key=f"{form_key}_status")

        if default_owner is None:
            people = db.get_people()
            people_opts = {f"{p['name']} ({p.get('department','—')})": p["id"]
                            for p in people}
            options = ["(بدون مالك)"] + list(people_opts.keys())
            owner_label = st.selectbox("المالك", options,
                                         key=f"{form_key}_owner")
            owner_id = people_opts.get(owner_label) if owner_label != "(بدون مالك)" else None
        else:
            st.info(f"المالك سيكون: **{default_owner.get('name')}** (الشخص المُسجَّل)")
            owner_id = default_owner.get("id")

    return {
        "plate_text": plate_text, "plate_arabic": plate_arabic,
        "make": make, "model": model, "color": color,
        "status": status, "owner_id": owner_id,
    }


def save_vehicle(data):
    """يحفظ مركبة في DB. المطلوب: رقم اللوحة فقط (المالك اختياري)."""
    if not data["plate_text"] or not str(data["plate_text"]).strip():
        st.error("رقم اللوحة مطلوب")
        return None

    try:
        # upsert: لو اللوحة مسجّلة مسبقاً تُحدَّث بدل الفشل (مناسب للتجارب)
        vehicle_id, created = db.add_or_update_vehicle(
            plate_text=data["plate_text"].strip().upper(),
            owner_id=data["owner_id"],
            make=data["make"],
            model=data["model"],
            color=data["color"],
            status=data["status"],
            plate_arabic=data["plate_arabic"],
        )
        if not created:
            st.info("هذه اللوحة مسجّلة مسبقاً — تم تحديث بياناتها.")
        return vehicle_id
    except Exception as e:
        st.error(f"خطأ في حفظ المركبة: {e}")
        return None


# TAB 1: PERSON ONLY
with tab_p:
    person_data = render_person_form("person_only")
    st.markdown("---")
    if st.button("حفظ الشخص",
                  type="primary", use_container_width=True,
                  key="save_person_only"):
        pid = save_person(person_data)
        if pid:
            st.success(f"تم تسجيل **{person_data['name']}** بنجاح! (ID: {pid})")
            st.balloons()

# TAB 2: VEHICLE ONLY
with tab_v:
    vehicle_data = render_vehicle_form("vehicle_only")
    st.markdown("---")
    if st.button("حفظ المركبة",
                  type="primary", use_container_width=True,
                  key="save_vehicle_only"):
        vid = save_vehicle(vehicle_data)
        if vid:
            owner = db.get_person(vehicle_data["owner_id"]) if vehicle_data["owner_id"] else None
            owner_name = owner["name"] if owner else "(بدون مالك)"
            st.success(f"تم تسجيل **{vehicle_data['plate_text']}** "
                       f"({vehicle_data['make']} {vehicle_data['model']}) - المالك: {owner_name}")
            st.balloons()

# TAB 3: PERSON + VEHICLE LINKED
with tab_pv:
    st.info("سنُسجّل الشخص أولاً ثم نربطه بالمركبة كمالك تلقائياً")
    st.markdown("### الخطوة 1: معلومات الشخص")
    person_data = render_person_form("combo_person")

    st.markdown("---")
    st.markdown("### الخطوة 2: معلومات المركبة")
    vehicle_data = render_vehicle_form("combo_vehicle",
                                          default_owner={"name": "الشخص الجديد", "id": None})

    st.markdown("---")
    if st.button("حفظ الشخص + المركبة + الربط",
                  type="primary", use_container_width=True,
                  key="save_combo"):
        pid = save_person(person_data)
        if pid:
            st.success(f"الشخص: {person_data['name']} (ID: {pid})")
            vehicle_data["owner_id"] = pid
            vid = save_vehicle(vehicle_data)
            if vid:
                st.success(f"المركبة: {vehicle_data['plate_text']} "
                           f"({vehicle_data['make']} {vehicle_data['model']})")
                st.success(f"تم الربط: {person_data['name']} ↔ {vehicle_data['plate_text']}")
                st.balloons()
            else:
                st.warning("تم تسجيل الشخص لكن فشل تسجيل المركبة - راجع البيانات")


# Stats Sidebar
with st.sidebar:
    st.markdown("### إحصائيات سريعة")
    n_people = len(db.get_people())
    n_vehicles = len(db.get_vehicles_with_owners())
    st.metric("الأشخاص المسجّلين", n_people)
    st.metric("المركبات المسجّلة", n_vehicles)
