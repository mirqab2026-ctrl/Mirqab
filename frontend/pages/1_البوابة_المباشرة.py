"""Live Gate - الكشف المباشر للوحة + الوجه + Active Learning"""
import sys
import html
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).parent.parent))
from theme import check_auth, apply_tuwaiq_theme, apply_tuwaiq_logo, apply_unified_text, render_sidebar_logout, apply_background
from plate_widget import render_slots_html
import live_capture as lc
import cv2
import numpy as np
import time

from backend import database as db
from backend import training_queue as tq
from backend.plate_pipeline import PlatePipeline
from backend.face_module import get_face_module
from backend.decision import final_verdict, get_active_mode
from backend.validation import full_validate
from backend.plate_normalizer import to_canonical, validate_canonical, split_digits_letters

st.set_page_config(page_title="Live Gate", page_icon="", layout="wide")



check_auth()
apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("live_gate.jpg", darkness=0.72)
st.markdown("# Live Gate · البوابة المباشرة")
st.caption("ارفع صورة أو التقط من الكاميرا المباشرة لكلٍّ من اللوحة والوجه، "
           "ثم يصدر النظام القرار تلقائياً حسب الوضع النشط.")

# CSS: مساواة ارتفاع بطاقات نتائج اللوحة/الوجه في الصفّ + tooltip للأسماء
st.markdown("""
<style>
/* اجعل الأعمدة التي تحوي بطاقة النتيجة تتمدّد لنفس الارتفاع */
div[data-testid="stHorizontalBlock"]:has(.lg-result-card) {
    align-items: stretch !important;
}
div[data-testid="stHorizontalBlock"]:has(.lg-result-card) > div[data-testid="column"] {
    display: flex !important;
    flex-direction: column !important;
}
.lg-result-card { flex: 1 1 auto; height: 100%; }

/* === Tooltip للأسماء — يظهر بيانات الشخص كاملة عند المرور بالفأرة === */
.person-tip {
    position: relative;
    cursor: help;
    border-bottom: 1px dashed rgba(243,201,105,0.4);
    padding-bottom: 1px;
}
.person-tip:hover::after {
    content: attr(data-tip);
    position: absolute;
    bottom: calc(100% + 8px);
    left: 50%;
    transform: translateX(-50%);
    background: linear-gradient(180deg, #171D24 0%, #1f1610 100%);
    color: #E6ECF2;
    padding: 0.7rem 0.9rem;
    border-radius: 0.5rem;
    border: 1px solid #E0A43B;
    font-size: 0.85rem;
    line-height: 1.7;
    white-space: pre-line;
    text-align: right;
    direction: rtl;
    min-width: 240px;
    max-width: 360px;
    z-index: 9999;
    box-shadow: 0 4px 18px rgba(0,0,0,0.6);
    font-family: 'Saudi', system-ui, sans-serif;
    font-weight: 400;
    pointer-events: none;
}
.person-tip:hover::before {
    content: "";
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-top-color: #E0A43B;
    z-index: 9999;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# Helper: بناء tooltip محتوى الشخص
# ============================================================
def _person_tooltip_attr(person: dict) -> str:
    """يبني نصّ tooltip بمعلومات الشخص الكاملة (لاستخدامه في data-tip)."""
    if not person:
        return ""
    parts = [
        f"الاسم: {person.get('name','—')}",
        f"الهوية: {person.get('national_id','—')}",
        f"القسم: {person.get('department','—')}",
        f"الصلاحية: {person.get('access_level','—')}",
    ]
    if person.get("phone"):
        parts.append(f"الجوال: {person['phone']}")
    if person.get("created_at"):
        parts.append(f"التسجيل: {str(person['created_at'])[:10]}")
    # نستخدم &#10; لإجبار الـ newline داخل attribute (مع white-space: pre-line)
    # html.escape يعالج < > & و " لمنع كسر العنصر أو حقن HTML من بيانات قاعدة البيانات
    return html.escape("\n".join(parts))

# تحميل النماذج
@st.cache_resource
def load_models():
    pp = PlatePipeline.get_instance()
    fm = get_face_module()
    return pp, fm


# ✨ cache قاعدة بيانات الوجوه — نمسحه يدوياً عند تسجيل وجه جديد
@st.cache_data(ttl=60, show_spinner=False)
def _cached_known_encodings():
    """يقرأ كل face_encodings من DB مرة واحدة في الجلسة (TTL 60 ثانية)."""
    return db.get_all_face_encodings()


with st.spinner("تحميل النماذج..."):
    plate_pipeline, face_module = load_models()

mode = get_active_mode()

# ============================================================
# شاشات الكاميرات (placeholders جاهزة للربط لاحقاً)
# ============================================================
def _camera_placeholder_html(title: str, subtitle: str) -> str:
    return f"""
    <div style="
        background: linear-gradient(135deg, #0E1217 0%, #171D24 50%, #0E1217 100%);
        border: 1px solid #2C3540;
        border-top: 3px solid #E0A43B;
        border-radius: 0.6rem;
        aspect-ratio: 16/9;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 24px rgba(0,0,0,0.6);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        text-align: center;
    ">
      <!-- زاوية النبض (مؤشر بصري) -->
      <div style="
          position:absolute; top:0.6rem; right:0.6rem;
          display:flex; align-items:center; gap:0.4rem;
          color:#9FB0C0; font-size:0.75rem; letter-spacing:0.08em;
          font-family:'Saudi',system-ui,sans-serif;
      ">
        <span style="
            width:0.5rem; height:0.5rem; border-radius:50%;
            background:#9A6A1E; box-shadow:0 0 6px #9A6A1E;
        "></span>
        OFFLINE
      </div>
      <!-- شبكة زخرفية خفيفة -->
      <div style="
          position:absolute; inset:0;
          background:
            repeating-linear-gradient(0deg, transparent 0 23px, rgba(224,164,59,0.04) 23px 24px),
            repeating-linear-gradient(90deg, transparent 0 23px, rgba(224,164,59,0.04) 23px 24px);
      "></div>
      <!-- علامات الزوايا -->
      <div style="position:absolute; top:0.5rem; left:0.5rem; width:1.2rem; height:1.2rem; border-top:2px solid #E0A43B; border-left:2px solid #E0A43B;"></div>
      <div style="position:absolute; bottom:0.5rem; left:0.5rem; width:1.2rem; height:1.2rem; border-bottom:2px solid #E0A43B; border-left:2px solid #E0A43B;"></div>
      <div style="position:absolute; bottom:0.5rem; right:0.5rem; width:1.2rem; height:1.2rem; border-bottom:2px solid #E0A43B; border-right:2px solid #E0A43B;"></div>
      <!-- النص المركزي -->
      <div style="position:relative; z-index:2;">
        <div style="
            font-family:'Saudi',system-ui,sans-serif;
            font-size:1.4rem; font-weight:600; color:#F3C969;
            letter-spacing:0.01em; margin-bottom:0.35rem;
        ">{title}</div>
        <div style="
            font-family:'Saudi',system-ui,sans-serif;
            font-size:0.95rem; color:#9FB0C0;
            letter-spacing:0.01em;
        ">{subtitle}</div>
        <div style="
            margin-top:0.85rem;
            font-family:'Saudi',system-ui,sans-serif;
            font-size:0.8rem; color:#6B7A8A;
            letter-spacing:0.05em;
        ">في انتظار ربط الكاميرا</div>
      </div>
    </div>
    """

# ============================================================
# Helper: قصّ مركزي لصورة لجعلها بنسبة أبعاد ثابتة
# ============================================================
def _center_crop_to_aspect(img: np.ndarray, target_aspect: float = 4/3) -> np.ndarray:
    """يقصّ الصورة من المركز لجعلها بنسبة أبعاد محدّدة (للحفاظ على ارتفاع موحَّد).

    target_aspect = w/h (الافتراضي 4/3 = 1.333)
    """
    if img is None or img.size == 0:
        return img
    h, w = img.shape[:2]
    current = w / h
    if abs(current - target_aspect) < 0.01:
        return img
    if current > target_aspect:
        # الصورة أعرض من المطلوب → قصّ يميناً/يساراً
        new_w = int(h * target_aspect)
        off = (w - new_w) // 2
        return img[:, off:off + new_w]
    else:
        # الصورة أطول → قصّ أعلى/أسفل
        new_h = int(w / target_aspect)
        off = (h - new_h) // 2
        return img[off:off + new_h, :]


# ============================================================
# دالة عرض شريط نتيجة فوري (تحت كل upload)
# ============================================================
def _result_card_html(state: str, title: str, body: str) -> str:
    """state: 'ok' | 'warn' | 'fail' | 'idle'"""
    colors = {
        "ok":   ("#10B981", "rgba(16,185,129,0.10)", "TYRES MATCH" if "TYRES" in title else "MATCH"),
        "warn": ("#F59E0B", "rgba(245,158,11,0.10)", "REVIEW"),
        "fail": ("#EF4444", "rgba(239,68,68,0.10)", "NO MATCH"),
        "idle": ("#2C3540", "rgba(44,53,64,0.10)", "WAITING"),
    }
    border, bg, label = colors[state]
    # min-height يضمن تساوي ارتفاع البطاقات في الصفّ حتى لو كان المحتوى مختلفاً
    return f"""
    <div class="lg-result-card" style="
        background:{bg};
        border:1px solid {border};
        border-radius:0.5rem;
        padding:0.85rem 1rem;
        margin-top:0.5rem;
        font-family:'Saudi',system-ui,sans-serif;
        min-height:180px;
        display:flex;
        flex-direction:column;
        box-sizing:border-box;
    ">
      <div style="
        display:flex; justify-content:space-between; align-items:center;
        margin-bottom:0.35rem;
      ">
        <div style="color:#FFE0A0; font-weight:600; font-size:0.95rem;">{title}</div>
        <div style="
          color:{border}; font-size:0.7rem; font-weight:700;
          letter-spacing:0.08em; padding:0.15rem 0.5rem;
          border:1px solid {border}; border-radius:0.25rem;
        ">{label}</div>
      </div>
      <div style="color:#E6ECF2; font-size:0.9rem; line-height:1.6;
                  flex:1; display:flex; flex-direction:column; justify-content:center;">{body}</div>
    </div>
    """


# ============================================================
# الشاشتان + الرفع + النتيجة الفورية تحت كل واحدة
# ============================================================
# قياس زمن المعالجة الفعلي (يُجمع زمن اللوحة + الوجه)
_plate_ms = 0.0
_face_ms = 0.0

class _FrameFile:
    """يغلّف إطار BGR من الكاميرا ككائن يشبه الملف المرفوع (getvalue → PNG bytes)،
    ليعمل مع منطق المعالجة الحالي بلا تغيير."""
    def __init__(self, frame):
        ok, buf = cv2.imencode(".png", frame)
        self._bytes = buf.tobytes() if ok else b""

    def getvalue(self):
        return self._bytes


# خيار «كاميرا الجهاز (منفذ)» في قائمة المصدر — نفس طريقة البوابة التلقائية
_CAM_DEVICE = "كاميرا الجهاز (منفذ)"

# عرض المعاينة الحية بدقة عالية + JPEG (كاميرا واحدة نشطة فقط في كل
# مرحلة، فنستطيع تحمّل الدقة الكاملة بلا تقطيع — JPEG أخف من PNG ~10×)
_PREVIEW_MAX_W = 1280


def _show_preview(holder, frame_bgr, caption):
    h, w = frame_bgr.shape[:2]
    if w > _PREVIEW_MAX_W:
        frame_bgr = cv2.resize(frame_bgr, (_PREVIEW_MAX_W, int(h * _PREVIEW_MAX_W / w)),
                               interpolation=cv2.INTER_AREA)
    holder.image(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), channels="RGB",
                 use_container_width=True, caption=caption,
                 output_format="JPEG")


# عنصرا شاشة البث — يُنشآن داخل قسمَي اللوحة/الوجه (المكان الأصلي)
# ويُملآن بالبث الحي المتواصل في نهاية السكربت (انظر أسفل الملف)
_plate_prev_holder = None
_face_prev_holder = None

cam_col_a, cam_col_b = st.columns(2)

with cam_col_a:
    enable_plate = st.toggle("تفعيل التحقق من اللوحة",
                                value=st.session_state.get("enable_plate", True),
                                key="enable_plate")
    plate_source = st.radio(
        "مصدر صورة اللوحة",
        ["رفع صورة", _CAM_DEVICE],
        horizontal=True,
        key="plate_source",
        label_visibility="collapsed",
        disabled=not enable_plate,
    )
    if plate_source == _CAM_DEVICE:
        # كاميرا الجهاز عبر المنفذ (cv2) — نفس طريقة البوابة التلقائية
        _pc1, _pc2 = st.columns([2, 1])
        with _pc1:
            _pport = st.number_input(
                "منفذ كاميرا اللوحة (USB)", 0, 10,
                int(db.get_setting("plate_cam_index", 1) or 1),
                key="lg_plate_port", disabled=not enable_plate)
        with _pc2:
            st.markdown('<div style="height:1.7rem"></div>', unsafe_allow_html=True)
            _pcap = st.button("📷 التقاط", key="lg_plate_cap",
                              use_container_width=True, disabled=not enable_plate)

        if _pcap:
            _ok, _fr = lc.read_frame(int(_pport))
            if _ok:
                st.session_state["lg_plate_devfile"] = _FrameFile(_fr)
                db.set_setting("plate_cam_index", int(_pport))
            else:
                st.error("تعذّر الالتقاط — تحقّق من رقم المنفذ")
        plate_img_file = st.session_state.get("lg_plate_devfile")

        # شاشة البث في مكانها الأصلي — بث حي متواصل (يُملأ آخر السكربت)
        _plate_prev_holder = st.empty()
        if plate_img_file is not None:
            _cap_img = cv2.imdecode(
                np.frombuffer(plate_img_file.getvalue(), np.uint8),
                cv2.IMREAD_COLOR)
            if _cap_img is not None:
                _show_preview(_plate_prev_holder, _cap_img,
                              "✓ تم التقاط اللوحة")
    else:
        # الإطار الزخرفي يظهر فقط في وضع الرفع
        st.markdown(_camera_placeholder_html("Camera A", "كاميرا المركبة · اللوحة"),
                    unsafe_allow_html=True)
        plate_img_file = st.file_uploader(
            "plate_image",
            type=["jpg", "jpeg", "png", "webp"],
            key="plate_upload",
            label_visibility="collapsed",
            disabled=not enable_plate,
        )
        st.session_state.pop("lg_plate_devfile", None)

    # معالجة فورية للوحة (فقط إذا كان التحقق مُفعّلاً)
    plate_result = None
    if not enable_plate:
        st.markdown(_result_card_html("idle", "التحقق معطّل",
                                        "اللوحة لن تُؤخذ بالحسبان في القرار"),
                      unsafe_allow_html=True)
    elif plate_img_file:
        img_bytes = plate_img_file.getvalue()
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            st.error("تعذّر قراءة الصورة المرفوعة — تأكد من أنها ملف صورة صالح.")
            st.stop()
        with st.spinner("كشف اللوحة..."):
            _t0 = time.time()
            result = plate_pipeline.process(img)
            _plate_ms = (time.time() - _t0) * 1000
        if result["plates"]:
            best = max(result["plates"], key=lambda p: p["confidence"])
            x1, y1, x2, y2 = best["bbox"]
            plate_crop = img[y1:y2, x1:x2].copy()
            plate_result = {
                "text": best.get("text", ""),
                "text_ar": best.get("text_ar", ""),
                "confidence": best["confidence"],
                "bbox": best["bbox"],
                "characters": best.get("characters", []),
                "annotated_img": plate_pipeline.visualize(img),
            }
            st.session_state["plate_result"] = plate_result
            st.session_state["plate_crop"] = plate_crop
            st.session_state["validation"] = full_validate(plate_result, db)

            # عرض النتيجة الفورية بشبكة الخانات (موحّد مع باقي النظام)
            text = plate_result["text"]
            text_ar = plate_result["text_ar"]
            conf = plate_result["confidence"]
            canonical = to_canonical(text)  # توحيد قبل البحث
            # ✨ فحص صارم: قاعدة 3 حروف بالضبط للوحة السعودية
            _v_ok, _v_msg = validate_canonical(canonical)
            _digits, _letters = split_digits_letters(canonical)
            # خزّن الحالة لاستخدامها في القرار النهائي والمراجعة
            plate_result["is_valid"] = _v_ok
            plate_result["validation_msg"] = _v_msg
            plate_result["letters_count"] = len(_letters)
            plate_result["digits_count"] = len(_digits)
            st.session_state["plate_result"] = plate_result

            vehicle = db.find_vehicle_by_plate(canonical or text) if _v_ok else None
            slots_html = render_slots_html(canonical, with_header=False) if canonical else ""

            # ============ إذا كانت القراءة غير مكتملة (حروف < 3): لا نقبل ============
            if canonical and not _v_ok:
                body = (
                    f"{slots_html}"
                    f"<div style='text-align:center;color:#EF4444;font-size:0.9rem;margin-top:0.5rem;font-weight:600;'>"
                    f"⚠ قراءة غير مكتملة</div>"
                    f"<div style='text-align:center;color:#F59E0B;font-size:0.82rem;margin-top:0.2rem;'>"
                    f"{_v_msg}</div>"
                    f"<div style='text-align:center;color:#9FB0C0;font-size:0.78rem;margin-top:0.35rem;'>"
                    f"الحروف المكتشفة: <b>{len(_letters)}</b> · الأرقام: <b>{len(_digits)}</b> · "
                    f"ثقة {conf:.1%}<br>"
                    f"<span style='color:#6B7A8A;'>صحّح القراءة يدوياً من قسم «Active Learning» أدناه</span></div>"
                )
                st.markdown(_result_card_html("fail", "قراءة مرفوضة", body), unsafe_allow_html=True)
            elif vehicle and vehicle.get("status") != "Suspended" and conf >= mode.plate_conf_threshold:
                body = (
                    f"{slots_html}"
                    f"<div style='text-align:center;color:#9FB0C0;font-size:0.85rem;margin-top:0.4rem;'>"
                    f"المركبة: <b style='color:#F3C969;'>{vehicle.get('make','')} {vehicle.get('model','')}</b> "
                    f"· الحالة: {vehicle.get('status','')} · ثقة {conf:.1%}</div>"
                )
                st.markdown(_result_card_html("ok", "اللوحة مطابقة", body), unsafe_allow_html=True)
            elif vehicle and vehicle.get("status") == "Suspended":
                body = (
                    f"{slots_html}"
                    f"<div style='text-align:center;color:#EF4444;font-size:0.85rem;margin-top:0.4rem;'>"
                    f"المركبة موقوفة (Suspended) · ثقة {conf:.1%}</div>"
                )
                st.markdown(_result_card_html("fail", "اللوحة موقوفة", body), unsafe_allow_html=True)
            elif vehicle:
                body = (
                    f"{slots_html}"
                    f"<div style='text-align:center;color:#F59E0B;font-size:0.85rem;margin-top:0.4rem;'>"
                    f"ثقة منخفضة {conf:.1%} (مطلوب ≥ {mode.plate_conf_threshold:.0%})</div>"
                )
                st.markdown(_result_card_html("warn", "ثقة منخفضة", body), unsafe_allow_html=True)
            else:
                body = (
                    f"{slots_html}"
                    f"<div style='text-align:center;color:#9FB0C0;font-size:0.85rem;margin-top:0.4rem;'>"
                    f"هذه اللوحة غير مسجّلة في النظام</div>"
                )
                st.markdown(_result_card_html("fail", "لوحة غير معروفة", body), unsafe_allow_html=True)
        else:
            st.session_state["plate_result"] = None
            _h, _w = img.shape[:2]
            _body = "لم يتمكن النموذج من العثور على لوحة في الصورة"
            if plate_source == _CAM_DEVICE:
                _body += (
                    f"<br><span style='font-size:0.78rem;color:#9FB0C0;'>"
                    f"دقة الالتقاط: {_w}×{_h} — قرّب اللوحة لتملأ الإطار، "
                    f"حسّن الإضاءة، وتجنّب الانعكاس والاهتزاز.</span>"
                )
            st.markdown(_result_card_html("fail", "لم تُكتشف لوحة", _body),
                          unsafe_allow_html=True)
    else:
        # idle state - clear previous
        if "plate_result" in st.session_state and not plate_img_file:
            st.session_state["plate_result"] = None
        if plate_source == _CAM_DEVICE:
            st.markdown(_result_card_html(
                "idle", "بانتظار الالتقاط",
                "وجّه كاميرا اللوحة واضغط «التقاط». إن ظهر خطأ منفذ، "
                "غيّر رقم المنفذ (0 أو 1 أو 2)."),
                unsafe_allow_html=True)


with cam_col_b:
    enable_face = st.toggle("تفعيل التحقق من الوجه",
                              value=st.session_state.get("enable_face", True),
                              key="enable_face")
    face_source = st.radio(
        "مصدر صورة الوجه",
        ["رفع صورة", _CAM_DEVICE],
        horizontal=True,
        key="face_source",
        label_visibility="collapsed",
        disabled=not enable_face,
    )
    if face_source == _CAM_DEVICE:
        _fc1, _fc2 = st.columns([2, 1])
        with _fc1:
            _fport = st.number_input(
                "منفذ كاميرا الوجه (مدمجة)", 0, 10,
                int(db.get_setting("face_cam_index", 0) or 0),
                key="lg_face_port", disabled=not enable_face)
        with _fc2:
            st.markdown('<div style="height:1.7rem"></div>', unsafe_allow_html=True)
            _fcap = st.button("📷 التقاط", key="lg_face_cap",
                              use_container_width=True, disabled=not enable_face)

        if _fcap:
            _ok, _fr = lc.read_frame(int(_fport))
            if _ok:
                st.session_state["lg_face_devfile"] = _FrameFile(_fr)
                db.set_setting("face_cam_index", int(_fport))
            else:
                st.error("تعذّر الالتقاط — تحقّق من رقم المنفذ")
        face_img_file = st.session_state.get("lg_face_devfile")

        # شاشة البث في مكانها الأصلي — بث حي متواصل (يُملأ آخر السكربت)
        _face_prev_holder = st.empty()
        if face_img_file is not None:
            _cap_img = cv2.imdecode(
                np.frombuffer(face_img_file.getvalue(), np.uint8),
                cv2.IMREAD_COLOR)
            if _cap_img is not None:
                _show_preview(_face_prev_holder, _cap_img,
                              "✓ تم التقاط الوجه")
    else:
        st.markdown(_camera_placeholder_html("Camera B", "كاميرا السائق · الوجه"),
                    unsafe_allow_html=True)
        face_img_file = st.file_uploader(
            "face_image",
            type=["jpg", "jpeg", "png", "webp"],
            key="face_upload",
            label_visibility="collapsed",
            disabled=not enable_face,
        )
        st.session_state.pop("lg_face_devfile", None)

    # معالجة فورية للوجه (فقط إذا كان التحقق مُفعّلاً)
    face_result = None
    if not enable_face:
        st.markdown(_result_card_html("idle", "التحقق معطّل",
                                        "الوجه لن يُؤخذ بالحسبان في القرار"),
                      unsafe_allow_html=True)
    elif face_img_file:
        img_bytes = face_img_file.getvalue()
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            st.error("تعذّر قراءة الصورة المرفوعة — تأكد من أنها ملف صورة صالح.")
            st.stop()
        with st.spinner("التعرف على الوجه..."):
            known = _cached_known_encodings()
            _t0 = time.time()
            face_results = face_module.identify(img, known)
            _face_ms = (time.time() - _t0) * 1000
        if face_results:
            best_face = max(face_results, key=lambda f: f["confidence"])
            face_result = {
                "person_id": best_face["person_id"],
                "confidence": best_face["confidence"],
                "bbox": best_face["bbox"],
                "img": img,
                # نحتفظ بالترميز الجاهز — يوفّر إعادة حسابه عند تسجيل سائق جديد
                "encoding": best_face.get("encoding"),
            }
            st.session_state["face_result"] = face_result

            conf = face_result["confidence"]
            person = db.get_person(face_result["person_id"]) if face_result["person_id"] else None
            if person and conf >= mode.face_conf_threshold:
                tip = _person_tooltip_attr(person)
                body = (
                    f'<b class="person-tip" data-tip="{tip}">{html.escape(person["name"] or "")}</b><br>'
                    f"ثقة {conf:.1%}"
                )
                st.markdown(_result_card_html("ok", "الوجه معروف", body), unsafe_allow_html=True)
            elif person:
                tip = _person_tooltip_attr(person)
                body = (
                    f'<b class="person-tip" data-tip="{tip}">{html.escape(person["name"] or "")}</b> · '
                    f"ثقة منخفضة {conf:.1%} (مطلوب ≥ {mode.face_conf_threshold:.0%})"
                )
                st.markdown(_result_card_html("warn", "تطابق ضعيف", body), unsafe_allow_html=True)
            else:
                body = f"تم اكتشاف وجه لكنه غير مسجّل في النظام · ثقة {conf:.1%}"
                st.markdown(_result_card_html("fail", "وجه غير معروف", body), unsafe_allow_html=True)
        else:
            st.session_state["face_result"] = None
            _h, _w = img.shape[:2]
            _body = "لم يتمكن النموذج من العثور على وجه في الصورة"
            if face_source == _CAM_DEVICE:
                _body += (
                    f"<br><span style='font-size:0.78rem;color:#9FB0C0;'>"
                    f"دقة الالتقاط: {_w}×{_h} — واجه الكاميرا مباشرة، "
                    f"قرّب الوجه، وحسّن الإضاءة.</span>"
                )
            st.markdown(_result_card_html("fail", "لم يُكتشف وجه", _body),
                          unsafe_allow_html=True)
    else:
        if "face_result" in st.session_state and not face_img_file:
            st.session_state["face_result"] = None
        if face_source == _CAM_DEVICE:
            st.markdown(_result_card_html(
                "idle", "بانتظار الالتقاط",
                "وجّه كاميرا الوجه واضغط «التقاط». إن ظهر خطأ منفذ، "
                "غيّر رقم المنفذ (0 أو 1 أو 2)."),
                unsafe_allow_html=True)


# حالة الالتقاط (تُستخدم لاختيار الكاميرا النشطة في حلقة البث آخر السكربت)
_dev_plate = bool(enable_plate and plate_source == _CAM_DEVICE)
_dev_face = bool(enable_face and face_source == _CAM_DEVICE)
_plate_captured = st.session_state.get("lg_plate_devfile") is not None
_face_captured = st.session_state.get("lg_face_devfile") is not None

# زر بدء دورة رصد جديدة (يمسح الالتقاطات ويعيد بثّ اللوحة)
if (_dev_plate or _dev_face) and (_plate_captured or _face_captured):
    _rc1, _rc2, _rc3 = st.columns([1, 2, 1])
    with _rc2:
        if st.button("↻ مسح جديد — مركبة تالية", use_container_width=True,
                     key="lg_new_scan"):
            for _k in ("lg_plate_devfile", "lg_face_devfile", "plate_result",
                       "face_result", "plate_crop", "face_crop", "validation",
                       "lg_logged_sig"):
                st.session_state.pop(_k, None)
            st.rerun()

# للحفاظ على توافق الكود اللاحق
run = bool(plate_img_file or face_img_file)
plate_result = st.session_state.get("plate_result") if enable_plate else None
face_result = st.session_state.get("face_result") if enable_face else None

# لو لا توجد أي صورة، امسح الحالة
if not plate_img_file and not face_img_file:
    for k in ("plate_result", "face_result", "plate_crop", "validation",
              "lg_logged_sig"):
        st.session_state.pop(k, None)

st.markdown("---")


# عرض النتائج (إذا موجودة)
if plate_result or face_result:
    validation = st.session_state.get("validation") if enable_plate else None
    # زمن المعالجة الفعلي المقيس في هذه الجولة (لوحة + وجه)
    processing_ms = int(_plate_ms + _face_ms)

    # ✨ بناء وضع تشغيل ديناميكي حسب الـ toggles:
    # إذا كان أحدهما معطّلاً، نخفّض require_both فلا يُشترط الوجه/اللوحة المعطّلة
    import copy
    effective_mode = copy.copy(mode)
    if not (enable_plate and enable_face):
        effective_mode.require_both = False

    # القرار من المصدر الموحّد final_verdict (بلا اشتراط ربط المركبة بالسائق)
    decision = final_verdict(plate_result, face_result, effective_mode,
                             need_plate=enable_plate, need_face=enable_face)

    # سجّل مرة واحدة فقط لكل عملية رصد — كان يُسجَّل مع كل تفاعل
    # بالصفحة (فتح expander، كتابة ملاحظة...) فتمتلئ التقارير بالتكرار.
    _log_sig = (f"{(plate_result or {}).get('text', '')}"
                f"|{(plate_result or {}).get('confidence', '')}"
                f"|{(face_result or {}).get('person_id', '')}"
                f"|{(face_result or {}).get('confidence', '')}")
    if run and st.session_state.get("lg_logged_sig") != _log_sig:
        db.add_log(
            plate_text=plate_result["text"] if plate_result else None,
            plate_confidence=plate_result["confidence"] if plate_result else None,
            person_id=face_result["person_id"] if face_result else None,
            face_confidence=face_result["confidence"] if face_result else None,
            decision=decision["decision"],
            reason=decision["reason"],
            mode=mode.name,
            processing_ms=processing_ms,
        )
        st.session_state["lg_logged_sig"] = _log_sig

    st.markdown("---")

    # (تم حذف البانر القديم — يستخدم النظام بطاقة "القرار النهائي" المتشدّدة أدناه)

    # تفاصيل
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Plate Recognition")
        if plate_result:
            _plate_img_rgb = cv2.cvtColor(plate_result["annotated_img"], cv2.COLOR_BGR2RGB)
            _plate_img_rgb = _center_crop_to_aspect(_plate_img_rgb, 4/3)
            st.image(_plate_img_rgb, use_container_width=True)

            text_en = plate_result['text']
            text_ar = plate_result['text_ar']

            # بناء أعمدة (كل حرف إنجليزي فوق ما يناظره بالعربي) - بدون مسافات بادئة
            en_chars = text_en.split()
            ar_chars = text_ar.split()

            cells_html = ""
            for en, ar in zip(en_chars, ar_chars):
                cells_html += (
                    '<div style="display:flex;flex-direction:column;align-items:center;'
                    'padding:0.4rem 0.5rem;background:#0E1217;border-radius:0.4rem;'
                    'border:1px solid #2C3540;flex:1;min-width:0;">'
                    f'<span style="color:#E0A43B;font-size:1.6rem;font-weight:700;'
                    f'font-family:Consolas,monospace;line-height:1.2;">{en}</span>'
                    '<hr style="border:0;border-top:1px solid #7A5C42;width:80%;margin:0.3rem 0;">'
                    f'<span style="color:#F3C969;font-size:1.6rem;font-weight:700;'
                    f'font-family:\'Saudi\',Tahoma,Arial;line-height:1.2;direction:ltr;">{ar}</span>'
                    '</div>'
                )

            plate_html = (
                '<div style="background:#171D24;padding:1rem;border-radius:0.5rem;'
                'margin-top:1rem;text-align:center;">'
                '<div style="color:#9FB0C0;font-size:0.85rem;margin-bottom:0.8rem;'
                'text-transform:uppercase;letter-spacing:0.1em;">'
                'Plate · لوحة المركبة</div>'
                '<div style="display:flex;justify-content:center;gap:0.3rem;'
                'flex-wrap:nowrap;overflow-x:auto;direction:ltr;">'
                f'{cells_html}'
                '</div></div>'
            )
            st.markdown(plate_html, unsafe_allow_html=True)
            st.markdown(f"**Confidence:** {plate_result['confidence']:.1%}")
            if decision["vehicle"]:
                v = decision["vehicle"]
                badge = {"VIP": "", "Active": "", "Suspended": "", "Review": ""}.get(v.get("status"), "")
                st.markdown(f"**Match:** {badge} {v.get('make','')} {v.get('model','')} - {v.get('status')}")

    with col2:
        st.markdown("### Face Recognition")
        if face_result:
            face_img_rgb = cv2.cvtColor(face_result["img"], cv2.COLOR_BGR2RGB)
            top, right, bottom, left = face_result["bbox"]
            cv2.rectangle(face_img_rgb, (left, top), (right, bottom), (0, 255, 0), 3)
            face_img_rgb = _center_crop_to_aspect(face_img_rgb, 4/3)
            st.image(face_img_rgb, use_container_width=True)
            st.markdown(f"**Confidence:** {face_result['confidence']:.1%}")
            if decision["person"]:
                p = decision["person"]
                tip = _person_tooltip_attr(p)
                st.markdown(
                    f'<div style="margin-top:0.4rem;font-size:0.95rem;">'
                    f'<span style="color:#9FB0C0;">Person:</span> '
                    f'<b class="person-tip" data-tip="{tip}" '
                    f'style="color:#F3C969;">{p["name"]}</b>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.info("لم تُرفع صورة وجه")

    st.markdown("---")

    # ============================================================
    # القرار النهائي + إجراءات سياقية بناءً على ما هو ناقص
    # ============================================================
    from plate_widget import plate_input as _plate_input_widget
    from backend.plate_normalizer import to_arabic_display as _to_ar_disp
    from backend import face_correction as _fc

    # تحديد الحالة — كلها من القرار الموحّد final_verdict
    _plate_canonical = decision.get("plate_canonical", "")
    _plate_is_valid = decision.get("plate_is_valid", True)
    _plate_invalid_msg = ""
    if _plate_canonical and not _plate_is_valid:
        _, _plate_invalid_msg = validate_canonical(_plate_canonical)

    _vehicle = decision.get("vehicle")
    _person = decision.get("person")
    _both_known = bool(_vehicle and _person)
    # الربط لم يعد مطلوباً للسماح — نبقي المتغيّرات للتوافق فقط
    _is_authorized = _both_known
    _auth_rel = ""

    # عرض البطاقة الكبرى للقرار
    st.markdown("## القرار النهائي · ACCESS DECISION")

    # إظهار أي فشل في تسجيل قرار يدوي سابق (بدل ابتلاعه صامتاً)
    if st.session_state.get("_op_log_error"):
        st.error(
            "تعذّر تسجيل القرار اليدوي في السجلّ: "
            + st.session_state["_op_log_error"]
        )

    # ============================================================
    # وضع المراجعة اليدوية: لو أيٌّ من نظامي التحقّق معطّل
    # ============================================================
    _manual_review = (not enable_plate) or (not enable_face)
    _disabled_systems = []
    if not enable_plate:
        _disabled_systems.append("التحقق من اللوحة")
    if not enable_face:
        _disabled_systems.append("التحقق من الوجه")

    # نُعرّف مفتاح فريد للقرار اليدوي بناءً على ما تم رفعه (يتغيّر = مراجعة جديدة)
    _scan_signature = f"{(plate_result or {}).get('text','')}_{bool(face_result)}"
    _op_decision_key = f"operator_decision_{_scan_signature}"
    _operator_decision = st.session_state.get(_op_decision_key)

    if _manual_review and _operator_decision is None:
        # ========== المراجعة اليدوية مطلوبة ==========
        st.markdown(f"""
        <div style="background:rgba(245,158,11,0.10); border:2px solid #F59E0B;
                    border-radius:0.6rem; padding:1.2rem;">
            <div style="font-size:2.2rem; color:#F59E0B; font-weight:700;
                        text-align:center; margin-bottom:0.3rem;">
                ⚠ PENDING REVIEW
            </div>
            <div style="color:#F59E0B; font-size:1.05rem; text-align:center;
                        font-weight:600; margin-bottom:0.7rem;">
                مراجعة يدوية مطلوبة من المشغّل
            </div>
            <div style="color:#9FB0C0; font-size:0.9rem; text-align:center;">
                النظام التالي معطّل: <b style="color:#F3C969;">{' و '.join(_disabled_systems)}</b><br>
                <span style="font-size:0.85rem;">لا يمكن للنظام اتخاذ قرار آلي — يُرجى مراجعة المعلومات أعلاه واتخاذ القرار يدوياً.</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # أزرار القبول/الرفض — تلوين عبر JavaScript injection (يعمل بشكل موثوق)
        _bc1, _bc2 = st.columns(2)
        with _bc1:
            if st.button("✓ قبول الدخول",
                          key=f"op_accept_{_scan_signature}",
                          use_container_width=True):
                st.session_state[_op_decision_key] = "accepted"
                try:
                    db.add_log(
                        plate_text=_plate_canonical or "",
                        plate_confidence=(plate_result or {}).get("confidence", 0),
                        person_id=(_person or {}).get("id"),
                        face_confidence=(face_result or {}).get("confidence", 0),
                        decision="GRANTED",
                        reason=f"Manual override (operator) — disabled: {', '.join(_disabled_systems)}",
                        mode=mode.name,
                        processing_ms=processing_ms,
                    )
                    st.session_state.pop("_op_log_error", None)
                except Exception as e:
                    # نحفظ الخطأ لإظهاره بعد إعادة التحميل بدل ابتلاعه صامتاً
                    st.session_state["_op_log_error"] = str(e)
                st.rerun()
        with _bc2:
            if st.button("✗ رفض الدخول",
                          key=f"op_reject_{_scan_signature}",
                          use_container_width=True):
                st.session_state[_op_decision_key] = "rejected"
                try:
                    db.add_log(
                        plate_text=_plate_canonical or "",
                        plate_confidence=(plate_result or {}).get("confidence", 0),
                        person_id=(_person or {}).get("id"),
                        face_confidence=(face_result or {}).get("confidence", 0),
                        decision="DENIED",
                        reason=f"Manual rejection (operator) — disabled: {', '.join(_disabled_systems)}",
                        mode=mode.name,
                        processing_ms=processing_ms,
                    )
                    st.session_state.pop("_op_log_error", None)
                except Exception as e:
                    # نحفظ الخطأ لإظهاره بعد إعادة التحميل بدل ابتلاعه صامتاً
                    st.session_state["_op_log_error"] = str(e)
                st.rerun()

        # JavaScript يلوّن الأزرار حسب نصّها (يعمل بشكل موثوق في Streamlit)
        import streamlit.components.v1 as _components
        _components.html("""
        <script>
        (function() {
            function colorOpButtons() {
                const doc = window.parent.document;
                doc.querySelectorAll('button').forEach(function(btn) {
                    const txt = (btn.innerText || '').trim();
                    if (txt === '✓ قبول الدخول' || txt === 'قبول الدخول') {
                        btn.style.background = 'linear-gradient(180deg, #10B981 0%, #059669 100%)';
                        btn.style.borderColor = '#059669';
                        btn.style.color = '#ffffff';
                        btn.style.fontWeight = '700';
                        btn.style.boxShadow = '0 2px 10px rgba(16,185,129,0.35)';
                    } else if (txt === '✗ رفض الدخول' || txt === 'رفض الدخول') {
                        btn.style.background = 'linear-gradient(180deg, #EF4444 0%, #DC2626 100%)';
                        btn.style.borderColor = '#DC2626';
                        btn.style.color = '#ffffff';
                        btn.style.fontWeight = '700';
                        btn.style.boxShadow = '0 2px 10px rgba(239,68,68,0.35)';
                    }
                });
            }
            // تلوين فوري
            colorOpButtons();
            // إعادة التلوين عند تغيّر DOM (Streamlit re-renders)
            const observer = new MutationObserver(colorOpButtons);
            observer.observe(window.parent.document.body, { childList: true, subtree: true });
            // تلوين متكرّر لأول 3 ثوانٍ للتأكّد
            let attempts = 0;
            const iv = setInterval(function() {
                colorOpButtons();
                attempts++;
                if (attempts > 15) clearInterval(iv);
            }, 200);
        })();
        </script>
        """, height=0)

    elif _manual_review and _operator_decision == "accepted":
        # ========== المشغّل قبل يدوياً ==========
        st.markdown(f"""
        <div style="background:rgba(16,185,129,0.10); border:2px solid #10B981;
                    border-radius:0.6rem; padding:1.2rem; text-align:center;">
            <div style="font-size:2.5rem; color:#10B981; font-weight:700; margin-bottom:0.3rem;">
                ✓ ACCESS GRANTED (Manual)
            </div>
            <div style="color:#10B981; font-size:1.1rem; font-weight:600;">السماح بالدخول بقرار يدوي</div>
            <div style="color:#9FB0C0; font-size:0.9rem; margin-top:0.5rem;">
                قبل المشغّل الدخول رغم تعطيل: <b style="color:#F3C969;">{' و '.join(_disabled_systems)}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif _manual_review and _operator_decision == "rejected":
        # ========== المشغّل رفض يدوياً ==========
        st.markdown(f"""
        <div style="background:rgba(239,68,68,0.10); border:2px solid #EF4444;
                    border-radius:0.6rem; padding:1.2rem; text-align:center;">
            <div style="font-size:2.2rem; color:#EF4444; font-weight:700; margin-bottom:0.3rem;">
                ✗ ACCESS DENIED (Manual)
            </div>
            <div style="color:#EF4444; font-size:1.05rem; font-weight:600;">رفض الدخول بقرار يدوي</div>
            <div style="color:#9FB0C0; font-size:0.9rem; margin-top:0.5rem;">
                رفض المشغّل الدخول بسبب تعطيل: <b style="color:#F3C969;">{' و '.join(_disabled_systems)}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif decision.get("decision") == "GRANTED":
        # ✅ مسموح (تطابق كامل: لوحة مصرّح لها + وجه مطابق)
        st.markdown(f"""
        <div style="background:rgba(16,185,129,0.10); border:2px solid #10B981;
                    border-radius:0.6rem; padding:1.2rem; text-align:center;">
            <div style="font-size:2.5rem; color:#10B981; font-weight:700; margin-bottom:0.3rem;">
                ✓ ACCESS GRANTED
            </div>
            <div style="color:#10B981; font-size:1.1rem; font-weight:600;">السماح بالدخول</div>
            <div style="color:#9FB0C0; font-size:0.95rem; margin-top:0.5rem;">
                السائق <b style="color:#F3C969;">{html.escape((_person or {}).get('name','') or '')}</b> ·
                مركبة <b style="color:#F3C969;">{html.escape((_vehicle or {}).get('make','') or '')} {html.escape((_vehicle or {}).get('model','') or '')}</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    else:
        # ✗ ممنوع — مع تحديد سبب وإجراء سياقي
        reasons = []
        if not _person and face_result:
            reasons.append("السائق غير مسجّل في النظام")
        if not _plate_canonical:
            reasons.append("لم تُكتشف لوحة")
        elif not _plate_is_valid:
            reasons.append(f"قراءة اللوحة غير مكتملة ({_plate_invalid_msg}) — صحّحها من Active Learning")
        elif not _vehicle:
            reasons.append("المركبة غير مسجّلة في النظام")
        if _vehicle and _vehicle.get("status") == "Suspended":
            reasons.append("المركبة موقوفة (Suspended)")
        if _person and _person.get("access_level") == "Suspended":
            reasons.append("الشخص موقوف (Suspended)")
        if not face_result:
            reasons.append("لم تُرفع صورة وجه")

        reason_html = "".join(f"<li>{r}</li>" for r in reasons) or "<li>بيانات غير مكتملة</li>"
        st.markdown(f"""
        <div style="background:rgba(239,68,68,0.10); border:2px solid #EF4444;
                    border-radius:0.6rem; padding:1.2rem;">
            <div style="font-size:2.2rem; color:#EF4444; font-weight:700;
                        text-align:center; margin-bottom:0.3rem;">
                ✗ ACCESS DENIED
            </div>
            <div style="color:#EF4444; font-size:1.05rem; text-align:center;
                        font-weight:600; margin-bottom:0.7rem;">
                منع الدخول حتى استيفاء الشروط
            </div>
            <div style="color:#9FB0C0; font-size:0.9rem;">
                <b style="color:#F3C969;">الأسباب:</b>
                <ul style="margin:0.3rem 1.5rem;">{reason_html}</ul>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ===== إجراءات ديناميكية: زر/نموذج لكل نقص =====
        st.markdown("### الإجراءات المطلوبة")

        # ----- 1) المركبة غير مسجّلة → نموذج إضافة باللوحة الملتقطة -----
        # (نتجاهل النموذج لو اللوحة غير صالحة — يجب تصحيحها أولاً من Active Learning)
        if _plate_canonical and _plate_is_valid and not _vehicle:
            with st.expander(
                f"إضافة المركبة الجديدة ({_plate_canonical})",
                expanded=True
            ):
                st.info(f"تم اكتشاف لوحة جديدة: **{_plate_canonical}** · سيتم حفظها مع البيانات أدناه.")
                qvc1, qvc2 = st.columns(2)
                with qvc1:
                    new_v_make = st.text_input("الصانع", key="ctx_v_make",
                                                placeholder="Toyota")
                    new_v_color = st.text_input("اللون", key="ctx_v_color",
                                                placeholder="أبيض")
                with qvc2:
                    new_v_model = st.text_input("الموديل", key="ctx_v_model",
                                                placeholder="Camry")
                    new_v_status = st.selectbox("الحالة",
                        ["Active", "VIP", "Review", "Suspended"],
                        key="ctx_v_status")
                # ربط بالشخص لو معروف، أو اختيار من القائمة
                if _person:
                    st.success(f"سيتم ربطها بالسائق المُكتشف: **{_person['name']}**")
                    new_v_owner = _person["id"]
                else:
                    all_p = db.get_people()
                    opts_ctx_v = {f"{p['name']} ({p.get('national_id','—')})": p["id"]
                                   for p in all_p}
                    sel = st.selectbox("ربط بمالك (اختياري)",
                                        ["(لاحقاً)"] + list(opts_ctx_v.keys()),
                                        key="ctx_v_owner")
                    new_v_owner = opts_ctx_v.get(sel) if sel != "(لاحقاً)" else None
                if st.button("حفظ المركبة وإعادة التحقّق",
                              type="primary", key="ctx_save_vehicle",
                              use_container_width=True):
                    try:
                        vid, _created = db.add_or_update_vehicle(
                            plate_text=_plate_canonical,
                            owner_id=new_v_owner,
                            make=new_v_make, model=new_v_model,
                            color=new_v_color, status=new_v_status,
                            plate_arabic=_to_ar_disp(_plate_canonical),
                        )
                        st.success(
                            (f"تمت إضافة المركبة {_plate_canonical} · ID: {vid}"
                             if _created else
                             f"المركبة {_plate_canonical} مسجّلة مسبقاً — حُدّثت بياناتها."))
                        st.rerun()
                    except Exception as e:
                        st.error(f"خطأ في الإضافة: {e}")

        # ----- 2) السائق غير مسجّل → نموذج إضافة بالصورة الملتقطة -----
        if face_result is not None and not _person:
            with st.expander(
                "إضافة السائق الجديد (مع الصورة الملتقطة)",
                expanded=True
            ):
                st.info("سيتم حفظ الوجه الملتقط مع البيانات أدناه — لا تحتاج لرفع صورة أخرى.")
                # عرض صورة الوجه الملتقطة
                if "face_crop" in st.session_state:
                    _crop = st.session_state["face_crop"]
                    if _crop is not None:
                        _crop_rgb = cv2.cvtColor(_crop, cv2.COLOR_BGR2RGB)
                        _cprev, _cforms = st.columns([1, 3])
                        with _cprev:
                            st.image(_crop_rgb, caption="الوجه الملتقط",
                                      use_container_width=True)
                        with _cforms:
                            new_p_name = st.text_input("الاسم الكامل *",
                                key="ctx_p_name", placeholder="محمد الأحمدي")
                            new_p_nid = st.text_input("الهوية الوطنية (اختياري)",
                                key="ctx_p_nid", placeholder="1023456789",
                                max_chars=10)
                            new_p_phone = st.text_input("الجوال",
                                key="ctx_p_phone", placeholder="+966...")
                            new_p_dept = st.selectbox("القسم",
                                ["Engineering", "Marketing", "Operations", "IT",
                                 "Executive", "Security", "Visitor"],
                                key="ctx_p_dept")
                            new_p_lvl = st.selectbox("مستوى الوصول",
                                ["Staff", "VIP", "Visitor"],
                                key="ctx_p_lvl")

                # خيار ربط فوري بالمركبة إن وُجدت
                _link_to_vehicle = False
                if _vehicle:
                    _link_to_vehicle = st.checkbox(
                        f"ربطه تلقائياً بالمركبة {_plate_canonical} كسائق معتمد",
                        value=True, key="ctx_link_after_add"
                    )

                if st.button("حفظ السائق وإعادة التحقّق",
                              type="primary", key="ctx_save_person",
                              use_container_width=True):
                    if not new_p_name.strip():
                        st.warning("اسم الشخص مطلوب")
                    else:
                        try:
                            pid = db.add_person(
                                new_p_name.strip(),
                                new_p_nid.strip() or None,
                                new_p_dept, new_p_lvl, new_p_phone
                            )
                            # حفظ encoding وصورة الوجه
                            if face_result and "face_crop" in st.session_state:
                                _crop_img = st.session_state["face_crop"]
                                enc = face_result.get("encoding")
                                if enc is None and _crop_img is not None:
                                    enc = face_module.encode_face(_crop_img)
                                if enc is not None:
                                    db.add_face_encoding(pid, enc)
                                if _crop_img is not None:
                                    _fc._save_face_image(pid, _crop_img)
                            # ربط بالمركبة لو طُلب
                            if _link_to_vehicle and _vehicle:
                                db.add_vehicle_authorization(
                                    _vehicle["id"], pid, "authorized",
                                    "Auto-linked at live gate"
                                )
                            st.success(f"تمت إضافة {new_p_name} · ID: {pid}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ: {e}")

        # (أُلغي اشتراط ربط المركبة بالسائق — لم يعد الربط مطلوباً للسماح)

    # ====== Active Learning - قابل للطي + تصحيح مباشر من المشغّل ======
    if plate_result:
        st.markdown("---")
        # نفتح المربع تلقائياً إذا كانت القراءة ناقصة (تنبيه للمشغّل)
        _needs_correction = (not _plate_is_valid) or (
            validation and validation.get("status") in ("warning", "needs_review")
        )
        with st.expander(
            "Active Learning · مراجعة وتحسين النموذج"
            + (" — تصحيح مطلوب" if _needs_correction else ""),
            expanded=bool(_needs_correction),
        ):
            # ===== لوحة الجودة =====
            if validation:
                status_color = {"ok": "#10B981", "warning": "#F59E0B", "needs_review": "#EF4444"}
                status_emoji = {"ok": "✓", "warning": "⚠", "needs_review": "✗"}
                col_vs, col_vd = st.columns([1, 3])
                with col_vs:
                    score = validation["score"]
                    st.markdown(f"""
                    <div style="background:#171D24; padding:1rem; border-radius:0.5rem; text-align:center;
                                border:2px solid {status_color[validation['status']]};">
                        <div style="color:#9FB0C0; font-size:0.8rem;">QUALITY SCORE</div>
                        <div style="color:{status_color[validation['status']]}; font-size:3rem; font-weight:700; margin:0.3rem 0;">{score}</div>
                        <div style="color:{status_color[validation['status']]}; font-weight:700;">
                          {status_emoji[validation['status']]} {validation['status'].upper()}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_vd:
                    st.markdown(f"**{validation['recommendation']}**")
                    if validation["issues"]:
                        for issue in validation["issues"]:
                            st.markdown(f"- {issue}")
                    else:
                        st.markdown("كل الفحوصات اجتازت بنجاح")

            # ===== تنبيه القراءة الناقصة =====
            if not _plate_is_valid:
                st.markdown(f"""
                <div style="background:rgba(239,68,68,0.10); border:1px solid #EF4444;
                            border-radius:0.5rem; padding:0.85rem; margin:0.8rem 0;">
                    <div style="color:#EF4444; font-weight:700; margin-bottom:0.3rem;">
                        ⚠ القراءة الآلية ناقصة: {_plate_invalid_msg}
                    </div>
                    <div style="color:#9FB0C0; font-size:0.9rem; line-height:1.6;">
                        النموذج قرأ <b style="color:#F3C969;">{_plate_canonical or '—'}</b>
                        — اللوحة السعودية تتطلب <b style="color:#F3C969;">3 حروف بالضبط</b>
                        و <b style="color:#F3C969;">1 إلى 4 أرقام</b>.<br>
                        أدخل القراءة الصحيحة أدناه — ستُحفظ في قائمة التدريب لتحسين النموذج.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # ===== تغذية التصحيح من المشغّل =====
            st.markdown("### تصحيح القراءة · Operator Feedback")
            st.markdown(
                '<div style="color:#9FB0C0;font-size:0.88rem;margin-bottom:0.5rem;">'
                'أدخل القراءة الصحيحة للوحة كما تراها بعينك (يمكنك الكتابة عربي أو إنجليزي). '
                'يُستخدم هذا التصحيح لإعادة تدريب النموذج في الدفعة القادمة.'
                '</div>',
                unsafe_allow_html=True
            )

            # اسم مفتاح فريد بحسب توقيع الـ scan
            _corr_key = f"plate_correction_{_scan_signature}"
            _corr_done_key = f"plate_correction_done_{_scan_signature}"

            if st.session_state.get(_corr_done_key):
                st.success(
                    "تم حفظ تصحيحك في قائمة التدريب — شكراً! "
                    "سيُستخدم هذا التصحيح في الدفعة التالية لإعادة التدريب."
                )
            else:
                # ===== الإدخال بالخانات (مثل تسجيل المركبة) =====
                _step_label = '<div style="color:#F3C969;font-weight:600;margin:0.5rem 0 0.4rem 0;">أدخل القراءة الصحيحة بالخانات</div>'
                st.markdown(_step_label, unsafe_allow_html=True)
                _step_desc = '<div style="color:#9FB0C0;font-size:0.85rem;margin-bottom:0.4rem;">كل خانة مستقلّة (4 أرقام يساراً + 3 حروف يميناً). يمكنك الكتابة عربي أو إنجليزي وستُحوّل تلقائياً للصيغة الأخرى.</div>'
                st.markdown(_step_desc, unsafe_allow_html=True)

                # استخدام مكوّن plate_input الخاناتي (نفس تسجيل المركبة)
                _default_for_widget = _plate_canonical if _plate_is_valid else ""
                _corr_canonical = _plate_input_widget(
                    label="",
                    key=_corr_key,
                    default=_default_for_widget,
                    show_preview=False,
                    show_validation=True,
                )
                _corr_ok, _corr_msg = validate_canonical(_corr_canonical) if _corr_canonical else (False, "")

                _notes_corr = st.text_input(
                    "ملاحظات (اختيارية)",
                    key=f"plate_correction_notes_{_scan_signature}",
                    placeholder="مثلاً: إضاءة سيئة، زاوية مائلة، حرف مطموس...",
                )

                _bc_save, _bc_confirm, _bc_reject = st.columns(3)
                with _bc_save:
                    _save_disabled = (not _corr_canonical) or (not _corr_ok)
                    if st.button(
                        "حفظ التصحيح",
                        key=f"btn_save_corr_{_scan_signature}",
                        type="primary",
                        use_container_width=True,
                        disabled=_save_disabled,
                    ):
                        try:
                            _crop = st.session_state.get("plate_crop")
                            tq.add_to_queue(
                                ocr_text=plate_result.get("text", ""),
                                corrected_text=_corr_canonical,
                                plate_crop_img=_crop,
                                avg_confidence=plate_result.get("confidence", 0.0),
                                issues=(validation or {}).get("issues", []) +
                                       ([_plate_invalid_msg] if not _plate_is_valid else []),
                                user_action="corrected",
                                notes=_notes_corr,
                            )
                            st.session_state[_corr_done_key] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ في الحفظ: {e}")

                with _bc_confirm:
                    _confirm_disabled = not _plate_is_valid
                    if st.button(
                        "القراءة صحيحة كما هي",
                        key=f"btn_confirm_corr_{_scan_signature}",
                        use_container_width=True,
                        disabled=_confirm_disabled,
                        help=("القراءة الناقصة لا يمكن تأكيدها — صحّحها أولاً"
                              if _confirm_disabled else None),
                    ):
                        try:
                            _crop = st.session_state.get("plate_crop")
                            tq.add_to_queue(
                                ocr_text=plate_result.get("text", ""),
                                corrected_text=_plate_canonical,
                                plate_crop_img=_crop,
                                avg_confidence=plate_result.get("confidence", 0.0),
                                issues=[],
                                user_action="confirmed",
                                notes="Operator confirmed OCR output",
                            )
                            st.session_state[_corr_done_key] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ في الحفظ: {e}")

                with _bc_reject:
                    if st.button(
                        "صورة سيئة — تجاهل",
                        key=f"btn_reject_corr_{_scan_signature}",
                        use_container_width=True,
                    ):
                        try:
                            _crop = st.session_state.get("plate_crop")
                            tq.add_to_queue(
                                ocr_text=plate_result.get("text", ""),
                                corrected_text="",
                                plate_crop_img=_crop,
                                avg_confidence=plate_result.get("confidence", 0.0),
                                issues=["bad_quality_marked_by_operator"],
                                user_action="rejected",
                                notes=_notes_corr or "Image marked as bad quality",
                            )
                            st.session_state[_corr_done_key] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ في الحفظ: {e}")


    # ====== Face Active Learning ======
    if face_result is not None:
        from backend import face_correction as fc

        with st.expander("Face Active Learning · تحسين التعرّف على الوجه", expanded=False):
            face_conf = face_result.get("confidence", 0)
            identified_person = decision.get("person")
            face_threshold = mode.face_conf_threshold

            if "face_crop" not in st.session_state:
                top, right, bottom, left = face_result["bbox"]
                pad = 30
                fh, fw = face_result["img"].shape[:2]
                top_p = max(0, top - pad)
                left_p = max(0, left - pad)
                bottom_p = min(fh, bottom + pad)
                right_p = min(fw, right + pad)
                st.session_state["face_crop"] = face_result["img"][top_p:bottom_p, left_p:right_p].copy()

            if identified_person and face_conf >= face_threshold:
                st.success(f"تم التعرّف على {identified_person['name']} بثقة {face_conf:.1%}")


render_sidebar_logout()


# ============================================================
# البث الحي المتواصل + أداة تتبّع الجودة — آخر ما يُنفَّذ في السكربت
#
# حلقة مستمرة تحدّث نفس عنصر الصورة في مكانه → فيديو حقيقي سلس.
# أي ضغطة زر (مثل «التقاط») توقف الحلقة تلقائياً وتبدأ المعالجة.
#
# أداة التتبّع: كشف خفيف كل _TRACK_EVERY ثانية (بلا OCR/مطابقة) يقيّم
# الجودة، والإطار يُرسم على كل إطار بث:
#   أخضر  = جاهز للالتقاط (ثقة كافية + حجم كافٍ + صورة حادة)
#   أحمر  = انتظر (مع سبب: اقترب / ثبّت الكاميرا / حسّن الإضاءة)
# ============================================================
_TRACK_EVERY = 0.5      # فاصل الكشف الخفيف (ثوانٍ)
_TRACK_W = 640          # نكشف على نسخة مصغّرة (أسرع ~3×) ونعيد تحجيم الإطار
_PLATE_MIN_W = 90       # أدنى عرض مقبول للوحة (بكسل في الإطار الأصلي)
_FACE_MIN_W = 80        # أدنى عرض مقبول للوجه
_PLATE_MIN_SHARP = 100.0  # أدنى حدة (تباين لابلاس) للوحة
_FACE_MIN_SHARP = 55.0
_PLATE_MIN_CONF = 0.55
_FACE_MIN_CONF = 0.60


def _sharpness(crop) -> float:
    """حدة الصورة بتباين لابلاس — منخفض = ضبابية/اهتزاز."""
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def _clip_box(x1, y1, x2, y2, w, h):
    return max(0, x1), max(0, y1), min(w, x2), min(h, y2)


def _track_plate(frame):
    """كشف لوحة خفيف. يعيد (bbox, ready, note) أو None إن لا لوحة."""
    h, w = frame.shape[:2]
    scale = min(1.0, _TRACK_W / w)
    small = (cv2.resize(frame, (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_AREA) if scale < 1.0 else frame)
    plates = plate_pipeline.detect_plates(small)
    if not plates:
        return None
    best = max(plates, key=lambda p: p["confidence"])
    inv = 1.0 / scale
    x1, y1, x2, y2 = (int(v * inv) for v in best["bbox"])
    x1, y1, x2, y2 = _clip_box(x1, y1, x2, y2, w, h)
    if x2 <= x1 or y2 <= y1:
        return None
    issues = []
    if best["confidence"] < _PLATE_MIN_CONF:
        issues.append("كشف ضعيف — عدّل الزاوية")
    if (x2 - x1) < _PLATE_MIN_W:
        issues.append("اللوحة صغيرة — اقترب")
    if _sharpness(frame[y1:y2, x1:x2]) < _PLATE_MIN_SHARP:
        issues.append("الصورة غير حادة — ثبّت الكاميرا/حسّن الإضاءة")
    ready = not issues
    note = ("✓ اللوحة واضحة — اضغط «التقاط» الآن" if ready
            else "⌛ " + " · ".join(issues))
    return (x1, y1, x2, y2), ready, note


def _track_face(frame):
    """كشف وجه خفيف (SCRFD سريع). يعيد (bbox, ready, note) أو None."""
    h, w = frame.shape[:2]
    if getattr(face_module, "backend", "") == "onnx":
        faces = face_module._engine.detect(frame)
        if not faces:
            return None
        f0 = faces[0]
        x1, y1, x2, y2 = (int(v) for v in f0["bbox"])
        conf = float(f0["score"])
    else:
        locs = face_module.detect_faces(frame)
        if not locs:
            return None
        t, r, b, l = locs[0]
        x1, y1, x2, y2, conf = l, t, r, b, 1.0
    x1, y1, x2, y2 = _clip_box(x1, y1, x2, y2, w, h)
    if x2 <= x1 or y2 <= y1:
        return None
    issues = []
    if conf < _FACE_MIN_CONF:
        issues.append("كشف ضعيف — واجه الكاميرا مباشرة")
    if (x2 - x1) < _FACE_MIN_W:
        issues.append("الوجه بعيد — اقترب")
    if _sharpness(frame[y1:y2, x1:x2]) < _FACE_MIN_SHARP:
        issues.append("الصورة غير حادة — اثبت لحظة")
    ready = not issues
    note = ("✓ الوجه واضح — اضغط «التقاط» الآن" if ready
            else "⌛ " + " · ".join(issues))
    return (x1, y1, x2, y2), ready, note


def _draw_overlay(frame, box, ready):
    """يرسم إطار التتبّع: أخضر = جاهز، أحمر = انتظر (+ زوايا بارزة)."""
    disp = frame.copy()
    color = (80, 200, 16) if ready else (50, 50, 235)   # BGR
    x1, y1, x2, y2 = box
    cv2.rectangle(disp, (x1, y1), (x2, y2), color, 2)
    # زوايا سميكة (أوضح للمشغّل من بعيد)
    cl = max(12, (x2 - x1) // 8)
    for (cx, cy, dx, dy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                             (x1, y2, 1, -1), (x2, y2, -1, -1)):
        cv2.line(disp, (cx, cy), (cx + dx * cl, cy), color, 5)
        cv2.line(disp, (cx, cy), (cx, cy + dy * cl), color, 5)
    cv2.putText(disp, "READY" if ready else "HOLD",
                (x1, max(22, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, color, 2)
    return disp


_stream = None
if _dev_plate and not _plate_captured and _plate_prev_holder is not None:
    _stream = (_plate_prev_holder,
               int(st.session_state.get("lg_plate_port", 1)),
               int(st.session_state.get("lg_face_port", 0)),
               "اللوحة")
elif _dev_face and not _face_captured and _face_prev_holder is not None:
    _stream = (_face_prev_holder,
               int(st.session_state.get("lg_face_port", 0)),
               int(st.session_state.get("lg_plate_port", 1)),
               "الوجه")

if _stream is not None:
    _holder, _port, _other_port, _label = _stream
    _is_plate_cam = (_label == "اللوحة")
    if _other_port != _port:
        lc.release(_other_port)
    _last_track = 0.0
    _overlay = None     # (bbox, ready, note) — يلتصق بالبث بين الكشفات
    while True:
        _ok, _fr = lc.read_frame(_port)
        if not _ok:
            _holder.error(f"تعذّر فتح كاميرا {_label} (منفذ {_port}) — "
                          "جرّب رقم منفذ آخر (0 أو 1 أو 2)")
            break
        _now = time.monotonic()
        if _now - _last_track >= _TRACK_EVERY:
            _last_track = _now
            try:
                _overlay = (_track_plate(_fr) if _is_plate_cam
                            else _track_face(_fr))
            except Exception:
                _overlay = None
        if _overlay:
            _box, _ready, _note = _overlay
            _disp = _draw_overlay(_fr, _box, _ready)
            _caption = f"● بث حي — {_note}"
        else:
            _disp = _fr
            _caption = (f"● بث حي — كاميرا {_label} · "
                        f"وجّه {_label} نحو الكاميرا")
        _show_preview(_holder, _disp, _caption)
        time.sleep(0.04)
