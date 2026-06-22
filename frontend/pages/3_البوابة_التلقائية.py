"""
البوابة التلقائية · Auto Live Gate (تسلسلي — شاشة واحدة)
======================================================
آلة حالات بكاميرا واحدة نشطة في كل مرحلة (يمنع الضغط والتضارب):
  idle → plate (اقرأ اللوحة) → face (اقرأ الوجه) → decision (القرار النهائي)

- fragment واحد بتحديث دوري أثناء مرحلتَي المسح فقط.
- لا st.rerun أثناء المسح (يمنع وميض/اختفاء البثّ). انتقال اللوحة→الوجه
  يحدث في الدورة التالية تلقائياً؛ st.rerun مرة واحدة فقط عند الدخول للقرار.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).parent.parent))

import copy
import html
import cv2
import streamlit as st

from theme import (
    check_auth, apply_tuwaiq_theme, apply_tuwaiq_logo,
    apply_unified_text, render_sidebar_logout, apply_background,
)
import live_capture as lc
from backend import database as db
from backend.plate_pipeline import PlatePipeline
from backend.face_module import get_face_module
from backend.decision import final_verdict, get_active_mode
from backend.plate_normalizer import to_canonical, validate_canonical

st.set_page_config(page_title="Auto Gate", page_icon="", layout="wide")

check_auth()
apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_unified_text()
apply_background("live_gate.jpg", darkness=0.72)

st.markdown("# البوابة التلقائية · Auto Live Gate")
st.caption("شاشة واحدة تسلسلية: تقرأ اللوحة أولاً ثم الوجه ثم تُصدر القرار — "
           "كاميرا واحدة نشطة في كل مرحلة لمنع الضغط والتضارب.")

# tooltip الأشخاص — نفس أسلوب البوابة المباشرة
st.markdown("""
<style>
.person-tip { position: relative; cursor: help;
    border-bottom: 1px dashed rgba(243,201,105,0.4); padding-bottom: 1px; }
.person-tip:hover::after {
    content: attr(data-tip); position: absolute; bottom: calc(100% + 8px);
    left: 50%; transform: translateX(-50%);
    background: linear-gradient(180deg, #171D24 0%, #1f1610 100%);
    color: #E6ECF2; padding: 0.7rem 0.9rem; border-radius: 0.5rem;
    border: 1px solid #E0A43B; font-size: 0.85rem; line-height: 1.7;
    white-space: pre-line; text-align: right; direction: rtl;
    min-width: 240px; max-width: 360px; z-index: 9999;
    box-shadow: 0 4px 18px rgba(0,0,0,0.6);
    font-family: 'Saudi', system-ui, sans-serif; font-weight: 400;
    pointer-events: none; }
.person-tip:hover::before {
    content: ""; position: absolute; bottom: 100%; left: 50%;
    transform: translateX(-50%); border: 6px solid transparent;
    border-top-color: #E0A43B; z-index: 9999; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_models():
    return PlatePipeline.get_instance(), get_face_module()


@st.cache_data(ttl=60, show_spinner=False)
def known_encodings():
    return db.get_all_face_encodings()


with st.spinner("تحميل النماذج..."):
    plate_pipeline, face_module = load_models()

mode = get_active_mode()

ss = st.session_state


def _init_state():
    """تهيئة المفاتيح. تُستدعى في السكربت وداخل الـ fragment (run_every يعزله)."""
    ss.setdefault("auto_stage", "idle")  # idle | plate | face | decision
    ss.setdefault("auto_plate_idx", int(db.get_setting("plate_cam_index", 1) or 1))
    ss.setdefault("auto_face_idx", int(db.get_setting("face_cam_index", 0) or 0))
    ss.setdefault("auto_plate_result", None)
    ss.setdefault("auto_face_result", None)
    ss.setdefault("auto_enable_plate", True)
    ss.setdefault("auto_enable_face", True)
    ss.setdefault("auto_logged_sig", None)


_init_state()


def _first_stage():
    if ss["auto_enable_plate"]:
        return "plate"
    if ss["auto_enable_face"]:
        return "face"
    return "decision"


# ============================================================
# أدوات التحكّم
# ============================================================
ctl = st.columns([1, 1, 1, 1])
with ctl[0]:
    pidx = st.number_input("منفذ كاميرا اللوحة (USB)", 0, 10,
                           ss["auto_plate_idx"], key="auto_plate_idx_in")
with ctl[1]:
    fidx = st.number_input("منفذ كاميرا الوجه (مدمجة)", 0, 10,
                           ss["auto_face_idx"], key="auto_face_idx_in")
with ctl[2]:
    ss["auto_enable_plate"] = st.toggle("تحقّق اللوحة", value=ss["auto_enable_plate"],
                                        key="auto_en_plate")
    ss["auto_enable_face"] = st.toggle("تحقّق الوجه", value=ss["auto_enable_face"],
                                       key="auto_en_face")
with ctl[3]:
    _scanning = ss["auto_stage"] in ("plate", "face")
    if not _scanning:
        if st.button("▶ بدء", type="primary", use_container_width=True):
            db.set_setting("plate_cam_index", int(pidx))
            db.set_setting("face_cam_index", int(fidx))
            ss["auto_plate_idx"] = int(pidx)
            ss["auto_face_idx"] = int(fidx)
            # افتح الكاميرات المطلوبة مرة واحدة مع تحقّق (نُخرج التعطّل المحتمل
            # من حلقة المسح إلى هنا مع مؤشّر تحميل ورسالة واضحة).
            lc.release_all()
            _fail = []
            with st.spinner("جارٍ فتح الكاميرات…"):
                if ss["auto_enable_plate"] and not lc.get_cap(int(pidx)).isOpened():
                    _fail.append(f"اللوحة (منفذ {int(pidx)})")
                if ss["auto_enable_face"] and not lc.get_cap(int(fidx)).isOpened():
                    _fail.append(f"الوجه (منفذ {int(fidx)})")
            if _fail:
                st.error("تعذّر فتح كاميرا: " + "، ".join(_fail)
                         + " — غيّر رقم المنفذ (0 أو 1 أو 2) وأعد المحاولة.")
            else:
                ss["auto_plate_result"] = None
                ss["auto_face_result"] = None
                ss["auto_logged_sig"] = None
                ss["auto_stage"] = _first_stage()
                st.rerun()
    else:
        if st.button("■ إيقاف", use_container_width=True):
            ss["auto_stage"] = "idle"
            lc.release_all()
            st.rerun()
    if st.button("↻ مسح جديد", use_container_width=True,
                 disabled=(ss["auto_stage"] == "idle")):
        ss["auto_plate_result"] = None
        ss["auto_face_result"] = None
        ss["auto_logged_sig"] = None
        ss["auto_stage"] = _first_stage()
        lc.release_all()
        st.rerun()

st.markdown("---")


# ============================================================
# مؤشّر المراحل
# ============================================================
def _progress_html(stage):
    def step(label, status):
        c = {"done": "#10B981", "active": "#F3C969", "pending": "#3A4450"}[status]
        mark = {"done": "✓", "active": "●", "pending": "○"}[status]
        return (f'<div style="display:flex;align-items:center;gap:0.4rem;color:{c};'
                f'font-weight:700;font-size:1.05rem;">{mark} {label}</div>')

    def st_plate():
        if not ss["auto_enable_plate"]:
            return "done"
        if ss["auto_plate_result"] is not None:
            return "done"
        return "active" if stage == "plate" else "pending"

    def st_face():
        if not ss["auto_enable_face"]:
            return "done"
        if ss["auto_face_result"] is not None:
            return "done"
        return "active" if stage == "face" else "pending"

    def st_dec():
        return "active" if stage == "decision" else "pending"

    arrow = '<div style="color:#3A4450;">—</div>'
    return (
        '<div style="display:flex;justify-content:center;align-items:center;'
        'gap:1.2rem;margin:0.3rem 0 1rem 0;">'
        + step("١ اللوحة", st_plate()) + arrow
        + step("٢ الوجه", st_face()) + arrow
        + step("٣ القرار", st_dec())
        + '</div>'
    )


# عرض البث بدقة مخفّضة + JPEG: يقلّص حجم النقل للمتصفح ~10-20× لكل تحديث
# (هذا سبب الوميض الرئيسي: PNG بـ 1280px كان ~1-2MB كل نصف ثانية)
_DISPLAY_W = 640


def _show_bgr(holder, frame, caption=""):
    h, w = frame.shape[:2]
    if w > _DISPLAY_W:
        frame = cv2.resize(frame, (_DISPLAY_W, int(h * _DISPLAY_W / w)),
                           interpolation=cv2.INTER_AREA)
    holder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                 channels="RGB", use_container_width=True, caption=caption,
                 output_format="JPEG")


def _center_crop_to_aspect(img, target_aspect=4/3):
    """قصّ مركزي لنسبة أبعاد ثابتة (نفس البوابة المباشرة)."""
    if img is None or img.size == 0:
        return img
    h, w = img.shape[:2]
    current = w / h
    if abs(current - target_aspect) < 0.01:
        return img
    if current > target_aspect:
        new_w = int(h * target_aspect)
        off = (w - new_w) // 2
        return img[:, off:off + new_w]
    new_h = int(w / target_aspect)
    off = (h - new_h) // 2
    return img[off:off + new_h, :]


def _person_tooltip_attr(person: dict) -> str:
    """نصّ tooltip بمعلومات الشخص (نفس البوابة المباشرة)."""
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
    return html.escape("\n".join(parts))


def _plate_cells_html(text_en, text_ar):
    """شبكة خانات اللوحة (كل حرف إنجليزي فوق ما يناظره بالعربي) — نفس البوابة المباشرة."""
    en_chars = (text_en or "").split()
    ar_chars = (text_ar or "").split()
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
    return (
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


def _scan_plate(holder, do_infer: bool = True) -> bool:
    """يقرأ كاميرا اللوحة ويعرضها. يُرجع True عند رصد لوحة صالحة.

    do_infer=False: عرض الإطار فقط بلا استدلال YOLO (الاستدلال يستغرق
    مئات الميلي ثانية على CPU — تشغيله لكل إطار هو سبب تقطيع الفيديو).
    """
    ok, frame = lc.read_frame(ss["auto_plate_idx"])
    if not ok:
        holder.error(
            f"تعذّر قراءة كاميرا اللوحة (منفذ {ss['auto_plate_idx']}) — "
            "جرّب رقم منفذ آخر (0 أو 1 أو 2) من الأعلى.")
        return False
    if not do_infer:
        _show_bgr(holder, frame, "كاميرا اللوحة — جارٍ المسح…")
        return False
    result = plate_pipeline.process(frame)
    disp = result.get("annotated_image", frame).copy()
    for p in result.get("plates", []):
        x1, y1, x2, y2 = p["bbox"]
        cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 200, 80), 2)
    _show_bgr(holder, disp, "كاميرا اللوحة — جارٍ المسح…")
    if result.get("plates"):
        best = max(result["plates"], key=lambda p: p["confidence"])
        canon = to_canonical(best.get("text", ""))
        valid, _ = validate_canonical(canon) if canon else (False, "")
        if valid and best["confidence"] >= mode.plate_conf_threshold:
            ss["auto_plate_result"] = {
                "text": best.get("text", ""),
                "text_ar": best.get("text_ar", ""),
                "confidence": float(best["confidence"]),
                "frame": disp.copy(),  # الصورة المُعلّمة بالمربّع (مثل البوابة المباشرة)
            }
            return True
    return False


def _scan_face(holder, do_infer: bool = True) -> bool:
    """يقرأ كاميرا الوجه ويعرضها. يُرجع True عند التعرّف على شخص."""
    ok, frame = lc.read_frame(ss["auto_face_idx"])
    if not ok:
        holder.error(
            f"تعذّر قراءة كاميرا الوجه (منفذ {ss['auto_face_idx']}) — "
            "جرّب رقم منفذ آخر (0 أو 1 أو 2) من الأعلى.")
        return False
    if not do_infer:
        _show_bgr(holder, frame, "كاميرا الوجه — جارٍ المسح…")
        return False
    faces = face_module.identify(frame, known_encodings())
    disp = frame.copy()
    for f in faces:
        top, right, bottom, left = f["bbox"]
        cv2.rectangle(disp, (left, top), (right, bottom), (0, 200, 80), 2)
    _show_bgr(holder, disp, "كاميرا الوجه — جارٍ المسح…")
    if faces:
        best = max(faces, key=lambda f: f["confidence"])
        if best["person_id"] and best["confidence"] >= mode.face_conf_threshold:
            ss["auto_face_result"] = {
                "person_id": int(best["person_id"]),
                "confidence": float(best["confidence"]),
                "bbox": best["bbox"],
                "frame": disp.copy(),  # الصورة المُعلّمة بالمربّع
            }
            return True
    return False


def _render_decision():
    """يحسب القرار النهائي ويعرضه مع لقطتي اللوحة والوجه."""
    need_plate = ss["auto_enable_plate"]
    need_face = ss["auto_enable_face"]
    plate_for_decision = ss["auto_plate_result"] if need_plate else None
    face_for_decision = ss["auto_face_result"] if need_face else None

    if not (plate_for_decision or face_for_decision):
        st.info("فعّل نظاماً واحداً على الأقل واضغط «بدء».")
        return

    # القرار من المصدر الموحّد (نفس البوابة المباشرة) — بلا اشتراط ربط
    decision = final_verdict(plate_for_decision, face_for_decision, mode,
                             need_plate=need_plate, need_face=need_face)

    sig = f"{(plate_for_decision or {}).get('text','')}_{(face_for_decision or {}).get('person_id','')}"
    if ss.get("auto_logged_sig") != sig:
        db.add_log(
            plate_text=(plate_for_decision or {}).get("text"),
            plate_confidence=(plate_for_decision or {}).get("confidence"),
            person_id=(face_for_decision or {}).get("person_id"),
            face_confidence=(face_for_decision or {}).get("confidence"),
            decision=decision["decision"],
            reason=decision["reason"],
            mode=mode.name,
            processing_ms=0,
        )
        ss["auto_logged_sig"] = sig

    d = decision["decision"]
    colors = {"GRANTED": ("#10B981", "✓ ACCESS GRANTED", "السماح بالدخول"),
              "PENDING": ("#F59E0B", "⚠ PENDING REVIEW", "مراجعة يدوية مطلوبة"),
              "DENIED":  ("#EF4444", "✗ ACCESS DENIED", "منع الدخول")}
    color, title_txt, sub = colors.get(d, colors["DENIED"])
    person = decision.get("person")
    vehicle = decision.get("vehicle")
    detail = []
    if person:
        detail.append(f"السائق: <b style='color:#F3C969;'>{html.escape(person.get('name','') or '')}</b>")
    if vehicle:
        detail.append(f"المركبة: <b style='color:#F3C969;'>{html.escape((vehicle.get('make','') or ''))} "
                      f"{html.escape((vehicle.get('model','') or ''))}</b>")
    detail.append(f"السبب: {html.escape(decision.get('reason',''))}")
    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.25); border:2px solid {color};
                border-radius:0.7rem; padding:1.3rem; text-align:center;">
      <div style="font-size:2.4rem; color:{color}; font-weight:700;">{title_txt}</div>
      <div style="color:{color}; font-size:1.1rem; font-weight:600; margin:0.2rem 0 0.6rem 0;">{sub}</div>
      <div style="color:#9FB0C0; font-size:0.95rem; line-height:1.8;">{' · '.join(detail)}</div>
    </div>
    """, unsafe_allow_html=True)

    # تفاصيل بنفس أسلوب وأحجام البوابة المباشرة (صورة ثم بيانات تحتها)
    st.markdown("---")
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown("### Plate Recognition")
        if ss["auto_plate_result"]:
            pr = ss["auto_plate_result"]
            _pimg = _center_crop_to_aspect(
                cv2.cvtColor(pr["frame"], cv2.COLOR_BGR2RGB), 4 / 3)
            st.image(_pimg, use_container_width=True)
            st.markdown(_plate_cells_html(pr.get("text", ""), pr.get("text_ar", "")),
                        unsafe_allow_html=True)
            st.markdown(f"**Confidence:** {pr['confidence']:.1%}")
            v = decision.get("vehicle")
            if v:
                st.markdown(f"**Match:** {v.get('make','')} {v.get('model','')} "
                            f"- {v.get('status')}")
        else:
            st.info("لم تُلتقط لوحة")
    with dcol2:
        st.markdown("### Face Recognition")
        if ss["auto_face_result"]:
            fr = ss["auto_face_result"]
            _fimg = _center_crop_to_aspect(
                cv2.cvtColor(fr["frame"], cv2.COLOR_BGR2RGB), 4 / 3)
            st.image(_fimg, use_container_width=True)
            st.markdown(f"**Confidence:** {fr['confidence']:.1%}")
            p = decision.get("person")
            if p:
                tip = _person_tooltip_attr(p)
                st.markdown(
                    f'<div style="margin-top:0.4rem;font-size:0.95rem;">'
                    f'<span style="color:#9FB0C0;">Person:</span> '
                    f'<b class="person-tip" data-tip="{tip}" '
                    f'style="color:#F3C969;">{html.escape(p.get("name","") or "")}</b>'
                    f'</div>',
                    unsafe_allow_html=True)
        else:
            st.info("لم يُلتقط وجه")
    st.caption("اضغط «↻ مسح جديد» لبدء عملية رصد جديدة.")


# ============================================================
# fragment واحد: المرحلة النشطة فقط (كاميرا واحدة في كل مرة)
#
# علاج الوميض: بدل إعادة بناء الواجهة كل 0.5 ثانية (هدم/بناء عنصر
# الصورة = ومضة)، نشغّل حلقة داخلية ~2.5 ثانية تحدّث «نفس» عنصر
# الصورة في مكانه — التحديث في المكان سلس بلا وميض. الـ fragment
# يُعاد تشغيله فوراً بعد انتهاء الحلقة، فإعادة البناء تحدث مرة كل
# 2.5 ثانية بدل مرتين في الثانية (وأزرار الإيقاف تستجيب خلال ≤2.5s).
# ============================================================
import time as _time

_SCAN_LOOP_SECONDS = 2.5
_run_every = "0.1s" if ss.get("auto_stage") in ("plate", "face") else None


@st.fragment(run_every=_run_every)
def gate_scan():
    _init_state()
    stage = ss["auto_stage"]
    st.markdown(_progress_html(stage), unsafe_allow_html=True)

    if stage == "decision":
        _render_decision()
        return

    left, mid, right = st.columns([1, 2, 1])
    with mid:
        holder = st.empty()
        if stage == "idle":
            holder.info("اضغط «▶ بدء» لبدء الرصد التسلسلي: اللوحة أولاً، ثم الوجه.")
            return

        # فصل العرض عن الاستدلال: الفيديو يتحدّث كل ~70ms (سلس)،
        # والاستدلال الثقيل (YOLO/الوجه) يعمل كل _INFER_EVERY فقط —
        # تشغيله لكل إطار كان سبب التقطيع (مئات ms لكل استدلال على CPU).
        _INFER_EVERY = 0.5
        deadline = _time.monotonic() + _SCAN_LOOP_SECONDS
        last_infer = 0.0
        while _time.monotonic() < deadline:
            now = _time.monotonic()
            do_infer = (now - last_infer) >= _INFER_EVERY
            if do_infer:
                last_infer = now
            if stage == "plate":
                if _scan_plate(holder, do_infer):
                    # انتقال للمرحلة التالية (الدورة القادمة تتولاها تلقائياً)
                    nxt = "face" if ss["auto_enable_face"] else "decision"
                    ss["auto_stage"] = nxt
                    if nxt == "decision":
                        st.rerun()  # إيقاف المؤقّت عند الدخول للقرار
                    return
            elif stage == "face":
                if _scan_face(holder, do_infer):
                    ss["auto_stage"] = "decision"
                    st.rerun()
            _time.sleep(0.04)


gate_scan()

render_sidebar_logout()
