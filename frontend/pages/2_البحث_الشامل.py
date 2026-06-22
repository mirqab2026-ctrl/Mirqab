"""Comprehensive Search — البحث الشامل عن الأشخاص والمركبات"""
import sys
import base64
import html
import mimetypes
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).parent.parent))
from theme import check_auth, apply_tuwaiq_theme, apply_tuwaiq_logo, apply_unified_text, render_sidebar_logout, apply_background
from plate_widget import plate_input, render_slots_html
import pandas as pd
from backend import database as db
from backend.plate_normalizer import to_canonical, to_arabic_display


# ============================================================
# Helpers لعرض الصور وبيانات المركبات داخل بطاقات الأشخاص
# ============================================================

@st.cache_data(show_spinner=False)
def _photo_data_uri(photo_path: str) -> str:
    """تحويل photo_path نسبي إلى data URI base64 للعرض في HTML."""
    if not photo_path:
        return ""
    p = Path(photo_path)
    if not p.is_absolute():
        p = ROOT / photo_path
    if not p.exists() or not p.is_file():
        return ""
    try:
        suf = p.suffix.lower()
        mime = "image/jpeg" if suf in (".jpg", ".jpeg") else "image/png" if suf == ".png" else mimetypes.guess_type(str(p))[0] or "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


@st.cache_data(show_spinner=False, ttl=60)
def _vehicles_of(person_id: int):
    """جلب المركبات المرتبطة بشخص (كمالك أو مفوّض)."""
    from backend.database import get_conn
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, plate_text, plate_arabic, make, model, color, status, created_at
            FROM vehicles WHERE owner_id = ?
            ORDER BY plate_text
        """, (person_id,)).fetchall()
        return [dict(r) for r in rows]


def _update_vehicle(vehicle_id: int, **fields):
    """تحديث بيانات مركبة (يبقي plate_canonical متزامناً تلقائياً)."""
    from backend.database import update_vehicle
    update_vehicle(vehicle_id, **fields)


def _delete_vehicle(vehicle_id: int):
    """حذف مركبة."""
    from backend.database import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM vehicles WHERE id=?", (vehicle_id,))


def _format_date(s):
    """تنسيق التاريخ من قاعدة البيانات."""
    if not s:
        return "—"
    try:
        return str(s)[:10]
    except Exception:
        return "—"

st.set_page_config(page_title="Search", page_icon="", layout="wide")


check_auth()
apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("people.jpg", darkness=0.72)

st.markdown("# البحث الشامل · Comprehensive Search")

# =============================================================
# صندوق البحث الموحّد + أزرار + فلاتر اختيارية
# =============================================================
# تهيئة حالة البحث: لا يُفعّل إلا عند الضغط على "بحث" أو Enter
if "active_search" not in st.session_state:
    st.session_state["active_search"] = ""

# CSS لمحاذاة أزرار البحث/المسح + تنسيق RTL لحقول اللوحة العربية
st.markdown("""
<style>
/* محاذاة الأزرار مع مربع البحث في نفس الصف */
div[data-testid="stHorizontalBlock"]:has(input[aria-label*="بحث شامل"]) {
    align-items: flex-end;
}
div[data-testid="stHorizontalBlock"]:has(input[aria-label*="بحث شامل"]) .stButton > button {
    height: 2.65rem !important;
    min-height: 2.65rem !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    line-height: 1 !important;
    margin: 0 !important;
}

/* تنسيق RTL لحقل اللوحة العربية أثناء الإدخال (يُظهر: أرقام يساراً + حروف يميناً) */
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

col_input, col_btn_search, col_btn_clear = st.columns([5, 1, 1])
with col_input:
    typed = st.text_input(
        "بحث شامل (اسم · هوية · قسم · لوحة · ماركة · موديل · لون · حالة · جوال)",
        value=st.session_state["active_search"],
        key="typed_query",
        placeholder="اكتب أي كلمة ثم اضغط بحث",
    )
with col_btn_search:
    do_search = st.button("بحث", use_container_width=True,
                            key="btn_run_search")
with col_btn_clear:
    do_clear = st.button("مسح", use_container_width=True, key="btn_clear_search")

# تفعيل البحث عند الضغط
if do_search:
    st.session_state["active_search"] = typed
    st.rerun()
if do_clear:
    st.session_state["active_search"] = ""
    # امسح الـ widget state أيضاً عبر rerun
    st.rerun()

# عند ضغط Enter في text_input يحدث rerun طبيعي → نُحدّث active_search تلقائياً
# لو القيمة المكتوبة مختلفة عن الفعّالة ولم يكن مسح، نُحدّث الفعّالة لتطابق المكتوبة
# (هذا يجعل Enter يعمل كزر "بحث")
if typed != st.session_state["active_search"] and not do_clear:
    # نُبقي الفعّالة فارغة حتى يضغط المستخدم بحث صراحةً
    pass

# القيمة المستخدمة فعلياً للفلترة هي active_search فقط
search = st.session_state["active_search"]

col_a, col_b, col_c = st.columns(3)
with col_a:
    filter_dept = st.selectbox(
        "قسم الشخص",
        ["كل الأقسام"] + sorted(list(set(p["department"] or "—"
                                            for p in db.get_people())))
    )
with col_b:
    filter_level = st.selectbox(
        "مستوى الشخص",
        ["الكل", "VIP", "Staff", "Visitor", "Suspended"]
    )
with col_c:
    filter_vstatus = st.selectbox(
        "حالة المركبة",
        ["كل الحالات", "Active", "VIP", "Suspended", "Review"]
    )

has_filter = (
    bool(search.strip())
    or filter_dept != "كل الأقسام"
    or filter_level != "الكل"
    or filter_vstatus != "كل الحالات"
)


# =============================================================
# منطق البحث
# =============================================================
all_people = db.get_people()
all_vehicles = db.get_vehicles_with_owners()

people_results = []
vehicles_results = []

if has_filter:
    s = search.lower().strip()

    def _match_person(p):
        if not s:
            return True
        fields = [
            p.get("name", ""),
            p.get("national_id", ""),
            p.get("department", ""),
            p.get("access_level", ""),
            p.get("phone", ""),
            str(p.get("id", "")),
        ]
        return any(s in str(f).lower() for f in fields)

    def _match_vehicle(v):
        if not s:
            return True
        fields = [
            v.get("plate_text", ""),
            v.get("plate_arabic", ""),
            v.get("owner_name", ""),
            v.get("make", ""),
            v.get("model", ""),
            v.get("color", ""),
            v.get("status", ""),
            str(v.get("id", "")),
        ]
        return any(s in str(f).lower() for f in fields)

    people_results = [p for p in all_people if _match_person(p)]
    if filter_dept != "كل الأقسام":
        people_results = [p for p in people_results
                            if p.get("department") == filter_dept]
    if filter_level != "الكل":
        people_results = [p for p in people_results
                            if p.get("access_level") == filter_level]

    vehicles_results = [v for v in all_vehicles if _match_vehicle(v)]
    if filter_vstatus != "كل الحالات":
        vehicles_results = [v for v in vehicles_results
                              if v.get("status") == filter_vstatus]

    st.markdown(f"### نتائج البحث · أشخاص: {len(people_results)} · "
                  f"مركبات: {len(vehicles_results)}")
else:
    st.markdown(f"### إجمالي المسجّلين · أشخاص: {len(all_people)} · "
                  f"مركبات: {len(all_vehicles)}")


# =============================================================
# عرض النتائج في tabs (تظهر فقط عند البحث)
# =============================================================
badge_map = {
    "VIP": '<span style="background:#F3C969;color:#000;padding:.2rem .5rem;border-radius:.3rem;font-weight:600;font-size:.75rem;">VIP</span>',
    "Staff": '<span style="background:#10B981;color:#000;padding:.2rem .5rem;border-radius:.3rem;font-weight:600;font-size:.75rem;">Staff</span>',
    "Visitor": '<span style="background:#6366F1;color:#fff;padding:.2rem .5rem;border-radius:.3rem;font-weight:600;font-size:.75rem;">Visitor</span>',
    "Suspended": '<span style="background:#EF4444;color:#fff;padding:.2rem .5rem;border-radius:.3rem;font-weight:600;font-size:.75rem;">Suspended</span>',
}

if has_filter:
    tab_p, tab_v = st.tabs([
        f"الأشخاص ({len(people_results)})",
        f"المركبات ({len(vehicles_results)})",
    ])

    # ----- الأشخاص -----
    with tab_p:
        if people_results:
            DEPT_OPTIONS = ["Engineering", "Marketing", "Operations", "IT",
                            "Executive", "Security", "Visitor", "خارجي - عرض"]
            LEVEL_OPTIONS = ["Staff", "VIP", "Visitor", "Suspended", "Watchlist"]
            STATUS_OPTIONS = ["Active", "VIP", "Review", "Suspended"]

            cols_per_row = 3
            for i in range(0, len(people_results), cols_per_row):
                cols = st.columns(cols_per_row)
                for j, person in enumerate(people_results[i:i+cols_per_row]):
                    with cols[j]:
                        face_count = db.get_face_count(person["id"])
                        level_badge = badge_map.get(
                            person.get("access_level", "Staff"), "")

                        # الصورة (إن وُجدت)
                        photo_uri = _photo_data_uri(person.get("photo_path", ""))
                        if photo_uri:
                            photo_html = (
                                f'<div style="width:100%;aspect-ratio:1/1;border-radius:0.5rem;'
                                f'overflow:hidden;background:#0E1217;margin-bottom:0.75rem;'
                                f'border:1px solid #2C3540;">'
                                f'<img src="{photo_uri}" alt="{html.escape(person["name"] or "")}" '
                                f'style="width:100%;height:100%;object-fit:cover;display:block;">'
                                f'</div>'
                            )
                        else:
                            initial = html.escape(person["name"][:1]) if person.get("name") else "؟"
                            photo_html = (
                                f'<div style="width:100%;aspect-ratio:1/1;border-radius:0.5rem;'
                                f'background:linear-gradient(135deg,#222A33 0%,#2C3540 100%);'
                                f'display:flex;align-items:center;justify-content:center;'
                                f'margin-bottom:0.75rem;border:1px solid #2C3540;">'
                                f'<span style="font-size:3rem;color:#F3C969;font-weight:700;'
                                f'font-family:\'Saudi\',system-ui;">{initial}</span>'
                                f'</div>'
                            )

                        # ===== المعلومات الكاملة (rows من label:value) =====
                        info_rows = []
                        # تخطّى الحقول الفارغة لكن أظهر "—" للحقول المهمة
                        info_rows.append(("الهوية الوطنية", person.get("national_id", "—") or "—", "mono"))
                        info_rows.append(("القسم", person.get("department", "—") or "—", ""))
                        info_rows.append(("مستوى الوصول", person.get("access_level", "Staff") or "Staff", ""))
                        if person.get("phone"):
                            info_rows.append(("الجوال", person["phone"], "ltr"))
                        info_rows.append(("صور الوجه", f"{face_count}", ""))
                        info_rows.append(("تاريخ التسجيل", _format_date(person.get("created_at")), ""))

                        info_html = ""
                        for label, value, extra_cls in info_rows:
                            extra_style = ""
                            if extra_cls == "mono":
                                extra_style = "font-family:monospace;"
                            elif extra_cls == "ltr":
                                extra_style = "direction:ltr;text-align:right;display:inline-block;"
                            info_html += (
                                f"<div style='display:flex;justify-content:space-between;"
                                f"gap:0.5rem;padding:0.25rem 0;border-bottom:1px solid #222A33;'>"
                                f"<span style='color:#6B7A8A;font-size:0.78rem;'>{label}</span>"
                                f"<span style='color:#E6ECF2;font-size:0.82rem;font-weight:500;{extra_style}'>{html.escape(str(value))}</span>"
                                f"</div>"
                            )

                        # ===== المركبات المرتبطة =====
                        vehicles = _vehicles_of(person["id"])
                        if vehicles:
                            v_items = []
                            for v in vehicles:
                                # canonical (يدعم plate_text القديم بأي تنسيق)
                                canonical = to_canonical(v.get("plate_text", "") or "")
                                if not canonical:
                                    # fallback لو plate_text فاضي، نجرّب plate_arabic
                                    canonical = to_canonical(v.get("plate_arabic", "") or "")
                                make = html.escape(v.get("make", "") or "")
                                model = html.escape(v.get("model", "") or "")
                                color = html.escape(v.get("color", "") or "")
                                vstatus = html.escape(v.get("status", "") or "")
                                veh_desc_parts = [x for x in [make, model, color] if x]
                                veh_desc = " · ".join(veh_desc_parts)
                                status_badge = ""
                                if vstatus:
                                    color_map = {
                                        "Active": "#10B981", "VIP": "#F3C969",
                                        "Review": "#6366F1", "Suspended": "#EF4444"
                                    }
                                    sc = color_map.get(vstatus, "#2C3540")
                                    status_badge = (
                                        f"<div style='text-align:center;margin-top:0.2rem;'>"
                                        f"<span style='background:{sc};color:#000;padding:.1rem .4rem;"
                                        f"border-radius:.25rem;font-size:.65rem;font-weight:600;'>{vstatus}</span>"
                                        f"</div>"
                                    )
                                # شبكة الخانات (EN فوق، AR تحت) - بدلاً من النص
                                slots_html = render_slots_html(canonical, with_header=False)
                                desc_html = f"<div style='color:#6B7A8A;font-size:0.72rem;text-align:center;margin-top:0.2rem;'>{veh_desc}</div>" if veh_desc else ""
                                v_items.append(
                                    f"<div style='background:#0E1217;padding:0.5rem;border-radius:0.4rem;margin:0.3rem 0;border-right:2px solid #E0A43B;'>"
                                    f"{slots_html}{status_badge}{desc_html}"
                                    f"</div>"
                                )
                            vehicles_block = (
                                f"<div style='margin-top:0.5rem;padding-top:0.5rem;"
                                f"border-top:1px dashed #2C3540;'>"
                                f"<div style='color:#F3C969;font-size:0.78rem;font-weight:600;"
                                f"margin-bottom:0.3rem;'>المركبات المرتبطة ({len(vehicles)})</div>"
                                f"{''.join(v_items)}"
                                f"</div>"
                            )
                        else:
                            vehicles_block = (
                                "<div style='margin-top:0.5rem;padding-top:0.5rem;"
                                "border-top:1px dashed #2C3540;color:#3A444F;"
                                "font-size:0.78rem;text-align:center;'>لا توجد مركبات مرتبطة</div>"
                            )

                        # ===== رسم البطاقة الكاملة =====
                        person_name_safe = html.escape(person["name"] or "")
                        card_html = (
                            "<div style=\"background:linear-gradient(180deg,#171D24 0%,#141A21 100%); padding:0.9rem; border-radius:0.75rem; border-left:4px solid #E0A43B; margin-bottom:0.5rem; box-shadow:0 4px 12px rgba(0,0,0,0.45);\">"
                            f"{photo_html}"
                            "<div style=\"display:flex; justify-content:space-between; align-items:start; gap:0.5rem; margin-bottom:0.3rem;\">"
                            f"<h4 style=\"margin:0; color:#F3C969; font-size:1.05rem; line-height:1.3;\">{person_name_safe}</h4>"
                            f"{level_badge}"
                            "</div>"
                            f"{info_html}"
                            f"{vehicles_block}"
                            "</div>"
                        )
                        st.markdown(card_html, unsafe_allow_html=True)

                        # ===== expander للتعديل =====
                        with st.expander("تعديل البيانات", expanded=False):
                            ekey = f"edit_p_{person['id']}"
                            st.markdown("**معلومات الشخص**")
                            new_name = st.text_input(
                                "الاسم الكامل", value=person.get("name", ""),
                                key=f"{ekey}_name")
                            new_nid = st.text_input(
                                "الهوية الوطنية", value=person.get("national_id", "") or "",
                                key=f"{ekey}_nid")
                            cur_dept = person.get("department") or DEPT_OPTIONS[0]
                            dept_idx = DEPT_OPTIONS.index(cur_dept) if cur_dept in DEPT_OPTIONS else 0
                            new_dept = st.selectbox(
                                "القسم", DEPT_OPTIONS,
                                index=dept_idx, key=f"{ekey}_dept")
                            cur_lvl = person.get("access_level") or "Staff"
                            lvl_idx = LEVEL_OPTIONS.index(cur_lvl) if cur_lvl in LEVEL_OPTIONS else 0
                            new_lvl = st.selectbox(
                                "مستوى الوصول", LEVEL_OPTIONS,
                                index=lvl_idx, key=f"{ekey}_lvl")
                            new_phone = st.text_input(
                                "الجوال", value=person.get("phone", "") or "",
                                key=f"{ekey}_phone")

                            bc1, bc2 = st.columns(2)
                            with bc1:
                                save_p = st.button("حفظ التعديلات",
                                    type="primary", key=f"{ekey}_save",
                                    use_container_width=True)
                            with bc2:
                                del_p = st.button("حذف الشخص",
                                    type="secondary", key=f"{ekey}_del",
                                    use_container_width=True)

                            if save_p:
                                try:
                                    db.update_person(
                                        person["id"],
                                        name=new_name, national_id=new_nid,
                                        department=new_dept, access_level=new_lvl,
                                        phone=new_phone
                                    )
                                    st.success("تم الحفظ. يُرجى إعادة البحث لرؤية التغييرات.")
                                    _vehicles_of.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"خطأ: {e}")
                            if del_p:
                                try:
                                    from backend.database import get_conn as _gc
                                    with _gc() as c:
                                        c.execute("DELETE FROM face_encodings WHERE person_id=?", (person["id"],))
                                        # تنظيف المراجع لتجنّب صفوف يتيمة
                                        c.execute("DELETE FROM vehicle_authorizations WHERE person_id=?", (person["id"],))
                                        c.execute("UPDATE vehicles SET owner_id=NULL WHERE owner_id=?", (person["id"],))
                                        c.execute("DELETE FROM people WHERE id=?", (person["id"],))
                                    st.success("حُذف الشخص.")
                                    _vehicles_of.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"خطأ في الحذف: {e}")

                            # ----- تعديل المركبات المرتبطة -----
                            if vehicles:
                                st.markdown("---")
                                st.markdown("**المركبات المرتبطة (تعديل)**")
                                for v in vehicles:
                                    vkey = f"edit_v_{v['id']}"
                                    with st.container(border=True):
                                        st.caption(f"مركبة #{v['id']}")
                                        # حقل موحّد يقبل EN/AR + معاينة فورية
                                        v_plate = plate_input(
                                            label="اللوحة (اكتب بالعربي أو الإنجليزي)",
                                            key=f"{vkey}_plate",
                                            default=v.get("plate_text", "") or "",
                                            show_preview=True,
                                            show_validation=True,
                                        )
                                        v_plate_ar = to_arabic_display(v_plate) if v_plate else ""
                                        vc1, vc2 = st.columns(2)
                                        with vc1:
                                            v_make = st.text_input(
                                                "الصانع", value=v.get("make", "") or "",
                                                key=f"{vkey}_make")
                                            v_color = st.text_input(
                                                "اللون", value=v.get("color", "") or "",
                                                key=f"{vkey}_color")
                                        with vc2:
                                            v_model = st.text_input(
                                                "الموديل", value=v.get("model", "") or "",
                                                key=f"{vkey}_model")
                                            cur_vs = v.get("status") or "Active"
                                            vs_idx = STATUS_OPTIONS.index(cur_vs) if cur_vs in STATUS_OPTIONS else 0
                                            v_status = st.selectbox(
                                                "الحالة", STATUS_OPTIONS,
                                                index=vs_idx, key=f"{vkey}_status")
                                        vsc1, vsc2 = st.columns(2)
                                        with vsc1:
                                            v_save = st.button("حفظ المركبة",
                                                type="primary", key=f"{vkey}_save",
                                                use_container_width=True)
                                        with vsc2:
                                            v_del = st.button("حذف المركبة",
                                                key=f"{vkey}_del",
                                                use_container_width=True)
                                        if v_save:
                                            try:
                                                _update_vehicle(
                                                    v["id"],
                                                    plate_text=v_plate,
                                                    plate_arabic=v_plate_ar,
                                                    make=v_make, model=v_model,
                                                    color=v_color, status=v_status
                                                )
                                                st.success("تم حفظ المركبة.")
                                                _vehicles_of.clear()
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"خطأ: {e}")
                                        if v_del:
                                            try:
                                                _delete_vehicle(v["id"])
                                                st.success("حُذفت المركبة.")
                                                _vehicles_of.clear()
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"خطأ: {e}")

                            # ----- إضافة مركبة جديدة مربوطة بالشخص -----
                            st.markdown("---")
                            st.markdown("**إضافة مركبة جديدة لهذا الشخص**")
                            akey = f"add_v_{person['id']}"
                            with st.container(border=True):
                                # حقل موحّد يقبل EN/AR + معاينة فورية
                                a_plate = plate_input(
                                    label="اللوحة (اكتب بالعربي أو الإنجليزي) *",
                                    key=f"{akey}_plate",
                                    default="",
                                    show_preview=True,
                                    show_validation=True,
                                )
                                a_plate_ar = to_arabic_display(a_plate) if a_plate else ""
                                ac1, ac2 = st.columns(2)
                                with ac1:
                                    a_make = st.text_input(
                                        "الصانع", placeholder="Toyota",
                                        key=f"{akey}_make")
                                    a_color = st.text_input(
                                        "اللون", placeholder="أبيض",
                                        key=f"{akey}_color")
                                with ac2:
                                    a_model = st.text_input(
                                        "الموديل", placeholder="Camry",
                                        key=f"{akey}_model")
                                    a_status = st.selectbox(
                                        "الحالة", STATUS_OPTIONS,
                                        index=0, key=f"{akey}_status")
                                a_save = st.button(
                                    "ربط المركبة بالشخص",
                                    type="primary", key=f"{akey}_save",
                                    use_container_width=True)
                                if a_save:
                                    if not a_plate.strip():
                                        st.warning("رقم اللوحة مطلوب")
                                    else:
                                        try:
                                            db.add_vehicle(
                                                plate_text=a_plate.strip(),
                                                owner_id=person["id"],
                                                make=a_make,
                                                model=a_model,
                                                color=a_color,
                                                status=a_status,
                                                plate_arabic=a_plate_ar,
                                            )
                                            st.success(f"تمت إضافة المركبة {a_plate} وربطها بـ {person['name']}.")
                                            _vehicles_of.clear()
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"خطأ في الإضافة (قد تكون اللوحة مكرّرة): {e}")
        else:
            st.warning("لا يوجد أشخاص يطابقون البحث")

    # ----- المركبات -----
    with tab_v:
        if vehicles_results:
            rows = []
            for v in vehicles_results:
                rows.append({
                    "Plate (EN)": v["plate_text"],
                    "Plate (AR)": v.get("plate_arabic", ""),
                    "Owner": v.get("owner_name", "—") or "—",
                    "Make": v.get("make", ""),
                    "Model": v.get("model", ""),
                    "Color": v.get("color", "—"),
                    "Status": v.get("status", ""),
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, hide_index=True, use_container_width=True, height=500)

            st.markdown("---")
            st.markdown("### إحصائيات المركبات")
            cols = st.columns(4)
            statuses = [v.get("status") for v in vehicles_results]
            cols[0].metric("Active", statuses.count("Active"))
            cols[1].metric("VIP", statuses.count("VIP"))
            cols[2].metric("Review", statuses.count("Review"))
            cols[3].metric("Suspended", statuses.count("Suspended"))
        else:
            st.warning("لا توجد مركبات تطابق البحث")


render_sidebar_logout()
