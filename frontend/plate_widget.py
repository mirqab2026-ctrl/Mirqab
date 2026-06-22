"""
plate_widget.py
================
مكوّن Streamlit لإدخال/عرض لوحات السيارات بطريقة الخانات (المعيار السعودي).

الاستخدام:
    from plate_widget import plate_input, plate_display

    # في صفحة الإدخال:
    canonical = plate_input(key="my_plate", default="2702GHD")
    # canonical = "2702GHD" أو "" إذا فارغ
    # ستظهر شبكة EN/AR متزامنة

    # في صفحة العرض (read-only):
    html = plate_display("2702GHD")
    st.markdown(html, unsafe_allow_html=True)
"""
import streamlit as st
from backend.plate_normalizer import (
    to_canonical, to_arabic_display, to_slots,
    validate_canonical, _ar_char_display,
    EN_TO_AR_DIGITS, EN_TO_AR_LETTERS,
    AR_TO_EN_DIGITS, AR_TO_EN_LETTERS,
    PERSIAN_DIGITS, AR_LETTER_ALIASES, TATWEEL,
)


# ============================================================
# CSS الخانات (تُحقن مرة واحدة لكل صفحة)
# ============================================================
PLATE_WIDGET_CSS = """
<style>
/* شبكة الخانات — grid مضمون 7 أعمدة في صفّ واحد */
.plate-slots-row {
    display: grid !important;
    grid-template-columns: repeat(7, minmax(0, 1fr)) !important;
    gap: 0.35rem !important;
    direction: ltr !important;
    margin: 0.5rem auto !important;
    max-width: 100% !important;
    width: 100% !important;
    box-sizing: border-box;
}
.plate-slot {
    background: linear-gradient(180deg, #171D24 0%, #1f1610 100%) !important;
    border: 1px solid #2C3540 !important;
    border-radius: 0.4rem !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0.4rem 0.1rem !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important;
    min-height: 60px !important;
    min-width: 0 !important;
    overflow: hidden;
}
/* العربي فوق - أكبر وأبرز (المعيار السعودي) */
.plate-slot-ar {
    color: #F3C969 !important;
    font-size: 1.15rem !important;
    font-weight: 700 !important;
    font-family: 'Saudi', system-ui, sans-serif !important;
    line-height: 1 !important;
    margin-bottom: 0.1rem !important;
}
.plate-slot-divider {
    width: 70% !important;
    height: 1px !important;
    background: linear-gradient(90deg,transparent,#E0A43B,transparent) !important;
    margin: 0.15rem 0 !important;
}
/* الإنجليزي تحت - أصغر قليلاً */
.plate-slot-en {
    color: #9FB0C0 !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    font-family: 'Segoe UI', system-ui, sans-serif !important;
    line-height: 1 !important;
    letter-spacing: 0.02em !important;
}
.plate-slot-empty { color: #4A3520 !important; }
.plate-slot.is-digit { border-color: #2C3540 !important; }
.plate-slot.is-letter { border-color: #8B5A2A !important; }
.plate-header {
    text-align: center;
    color: #9FB0C0;
    font-size: 0.78rem;
    font-family: 'Saudi', system-ui, sans-serif;
    margin-bottom: 0.3rem;
    letter-spacing: 0.05em;
}
.plate-validation {
    text-align: center;
    font-size: 0.78rem;
    margin-top: 0.3rem;
    font-family: 'Saudi', system-ui, sans-serif;
}
.plate-validation.valid { color: #10B981; }
.plate-validation.invalid { color: #EF4444; }
.plate-validation.warning { color: #F3C969; }

/* حقل إدخال اللوحة - تنسيق RTL/LTR ذكي */
input[aria-label*="اللوحة"] {
    font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
    font-size: 1.05rem !important;
    letter-spacing: 0.06em !important;
    text-align: center !important;
}

/* تأكّد ألا تورّم Streamlit div محتوى الـ markdown */
.plate-slots-row > div { min-width: 0 !important; }

/* === خانات الإدخال = نفس شكل خانات العرض (خلية موحّدة لكل حرف) === */
/* خانة الحرف = عمود يحوي الحقل ولا يحوي أعمدة متداخلة (نتجنّب العمود الخارجي) */
div[data-testid="stColumn"]:has(input[aria-label*="عربي #"]):not(:has(div[data-testid="stColumn"])) {
    background: linear-gradient(180deg, #171D24 0%, #1f1610 100%) !important;
    border: 1px solid #8B5A2A !important;
    border-radius: 0.4rem !important;
    padding: 0.35rem 0.15rem !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4) !important;
    min-width: 0 !important;
}
/* الحقول شفّافة بلا حدود — يظهر إطار الخلية فقط (كما في العرض) */
input[aria-label*="عربي #"],
input[aria-label*="EN #"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    text-align: center !important;
    padding: 0.05rem !important;
    height: 1.9rem !important;
    min-height: 1.9rem !important;
}
/* العربي (أعلى) — ذهبي بارز (المعيار السعودي) */
input[aria-label*="عربي #"] {
    color: #F3C969 !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    font-family: 'Saudi', system-ui, sans-serif !important;
    line-height: 1 !important;
}
/* الإنجليزي (أسفل) — رمادي فاتح */
input[aria-label*="EN #"] {
    color: #9FB0C0 !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    font-family: 'Segoe UI', system-ui, sans-serif !important;
    text-transform: uppercase !important;
    line-height: 1 !important;
}
/* ضغط الفراغ الداخلي لحقول الخلية */
div[data-testid="stColumn"]:has(input[aria-label*="عربي #"]) div[data-testid="stTextInput"] {
    margin: 0 !important;
}
/* تقليل الفراغ الرأسي داخل الخلية (بين العربي والفاصل والإنجليزي) */
div[data-testid="stColumn"]:has(input[aria-label*="عربي #"]):not(:has(div[data-testid="stColumn"])) div[data-testid="stVerticalBlock"] {
    gap: 0.1rem !important;
}
/* إخفاء أيّ label leftover */
.stTextInput > label[data-testid="stWidgetLabel"]:empty {
    display: none !important;
}
</style>
"""

def _inject_css_once():
    """يحقن CSS — يُستدعى داخل كل widget call.
    Streamlit يُعيد تشغيل السكربت كلياً عند كل تفاعل، فلا بدّ من إعادة الحقن.
    إعادة الإعلان عن نفس الـ rules غير ضارة (آخر تعريف يفوز في CSS)."""
    st.markdown(PLATE_WIDGET_CSS, unsafe_allow_html=True)


# ============================================================
# Display (read-only) — تُعرض في البطاقات
# ============================================================

# ----- styles inline (مستقلّة عن أي CSS خارجي) -----
_GRID_STYLE = (
    "display:grid;"
    "grid-template-columns:repeat(7, minmax(0, 1fr));"
    "gap:0.35rem;"
    "direction:ltr;"
    "margin:0.5rem auto;"
    "max-width:100%;"
    "width:100%;"
)
_SLOT_STYLE = (
    "background:linear-gradient(180deg, #171D24 0%, #1f1610 100%);"
    "border:1px solid #2C3540;"
    "border-radius:0.4rem;"
    "display:flex;"
    "flex-direction:column;"
    "align-items:center;"
    "justify-content:center;"
    "padding:0.4rem 0.1rem;"
    "box-shadow:0 2px 6px rgba(0,0,0,0.4);"
    "min-height:60px;"
    "min-width:0;"
)
_AR_STYLE = (
    "color:#F3C969;"
    "font-size:1.15rem;"
    "font-weight:700;"
    "font-family:'Saudi', system-ui, sans-serif;"
    "line-height:1;"
    "margin-bottom:0.1rem;"
)
_DIVIDER_STYLE = (
    "width:70%;"
    "height:1px;"
    "background:linear-gradient(90deg,transparent,#E0A43B,transparent);"
    "margin:0.15rem 0;"
)
_EN_STYLE = (
    "color:#9FB0C0;"
    "font-size:1rem;"
    "font-weight:700;"
    "font-family:'Segoe UI', system-ui, sans-serif;"
    "line-height:1;"
    "letter-spacing:0.02em;"
)
_HEADER_STYLE = (
    "text-align:center;"
    "color:#9FB0C0;"
    "font-size:0.78rem;"
    "font-family:'Saudi', system-ui, sans-serif;"
    "margin-bottom:0.3rem;"
    "letter-spacing:0.05em;"
)
_EMPTY_STYLE = "color:#4A3520;"


def render_slots_html(canonical: str, with_header: bool = True) -> str:
    """يُرجع HTML شبكة الخانات بستايل inline (يعمل في أي سياق).

    تدعم لوحات بـ 1-4 أرقام + 3 حروف. الخانات الفارغة تُعرض كـ "·".

    Args:
        canonical: مثل "2702GHD" أو "702GHD" أو "70GHD"
        with_header: عرض "لوحة المركبة · PLATE" فوق الشبكة
    Returns:
        HTML string ذاتي الاكتفاء (لا يحتاج CSS مُحقن)
    """
    if not canonical or not canonical.strip():
        return _render_empty_slots(with_header=with_header)

    slots = to_slots(canonical)
    en_digits = list(slots["digits"])
    en_letters = list(slots["letters"])
    ar_digits = [EN_TO_AR_DIGITS.get(d, d) for d in en_digits]
    ar_letters = [_ar_char_display(EN_TO_AR_LETTERS.get(l, l)) for l in en_letters]

    # نُبقي 7 خانات للاتساق البصري: 4 أرقام + 3 حروف
    # الأرقام الناقصة (لو عدد < 4) تُعرض كـ placeholder
    cells = []
    # 4 خانات أرقام (يُملأ من اليسار)
    for i in range(4):
        if i < len(en_digits):
            ar = ar_digits[i]; en = en_digits[i]
            cells.append(
                f'<div style="{_SLOT_STYLE}">'
                f'<div style="{_AR_STYLE}">{ar}</div>'
                f'<div style="{_DIVIDER_STYLE}"></div>'
                f'<div style="{_EN_STYLE}">{en}</div>'
                f'</div>'
            )
        else:
            cells.append(
                f'<div style="{_SLOT_STYLE}">'
                f'<div style="{_AR_STYLE}{_EMPTY_STYLE}">·</div>'
                f'<div style="{_DIVIDER_STYLE}"></div>'
                f'<div style="{_EN_STYLE}{_EMPTY_STYLE}">·</div>'
                f'</div>'
            )
    # 3 خانات حروف
    for i in range(3):
        if i < len(en_letters):
            ar = ar_letters[i]; en = en_letters[i]
            cells.append(
                f'<div style="{_SLOT_STYLE}">'
                f'<div style="{_AR_STYLE}">{ar}</div>'
                f'<div style="{_DIVIDER_STYLE}"></div>'
                f'<div style="{_EN_STYLE}">{en}</div>'
                f'</div>'
            )
        else:
            cells.append(
                f'<div style="{_SLOT_STYLE}">'
                f'<div style="{_AR_STYLE}{_EMPTY_STYLE}">·</div>'
                f'<div style="{_DIVIDER_STYLE}"></div>'
                f'<div style="{_EN_STYLE}{_EMPTY_STYLE}">·</div>'
                f'</div>'
            )

    header = (
        f'<div style="{_HEADER_STYLE}">لوحة المركبة · PLATE</div>'
        if with_header else ""
    )
    return f'{header}<div style="{_GRID_STYLE}">{"".join(cells)}</div>'


def _render_empty_slots(with_header: bool = True) -> str:
    """يعرض شبكة فارغة (placeholder) بستايل inline."""
    cells = []
    for i in range(7):
        cells.append(
            f'<div style="{_SLOT_STYLE}">'
            f'<div style="{_AR_STYLE}{_EMPTY_STYLE}">·</div>'
            f'<div style="{_DIVIDER_STYLE}"></div>'
            f'<div style="{_EN_STYLE}{_EMPTY_STYLE}">·</div>'
            f'</div>'
        )
    header = (
        f'<div style="{_HEADER_STYLE}">لوحة المركبة · PLATE</div>'
        if with_header else ""
    )
    return f'{header}<div style="{_GRID_STYLE}">{"".join(cells)}</div>'


def plate_display(canonical: str, with_header: bool = True):
    """يعرض شبكة اللوحة في الصفحة (يستخدم st.markdown)."""
    st.markdown(render_slots_html(canonical, with_header=with_header),
                unsafe_allow_html=True)


# ============================================================
# Input widget — خانات متزامنة EN/AR
# ============================================================

_PLATE_LEN = 7
_DIGIT_SLOTS = 4
_LETTER_SLOTS = 3


def _en_to_ar_char(en_char: str) -> str:
    if not en_char:
        return ""
    c = en_char.strip().upper()
    if c in EN_TO_AR_DIGITS:
        return EN_TO_AR_DIGITS[c]
    if c in EN_TO_AR_LETTERS:
        return _ar_char_display(EN_TO_AR_LETTERS[c])
    return ""


def _ar_to_en_char(ar_char: str) -> str:
    if not ar_char:
        return ""
    cleaned = ar_char.replace(TATWEEL, "").strip()
    for src, dst in AR_LETTER_ALIASES.items():
        cleaned = cleaned.replace(src, dst)
    if not cleaned:
        return ""
    c = cleaned[0]
    if c in AR_TO_EN_DIGITS:
        return AR_TO_EN_DIGITS[c]
    if c in AR_TO_EN_LETTERS:
        return AR_TO_EN_LETTERS[c]
    if c in PERSIAN_DIGITS:
        return PERSIAN_DIGITS[c]
    cu = c.upper()
    if cu in EN_TO_AR_DIGITS or cu in EN_TO_AR_LETTERS:
        return cu
    return ""


def _make_sync_en_cb(key_prefix: str, idx: int):
    def _cb():
        en_key = f"{key_prefix}__en_{idx}"
        ar_key = f"{key_prefix}__ar_{idx}"
        raw = (st.session_state.get(en_key) or "").strip()
        if not raw:
            st.session_state[ar_key] = ""
            return
        en_norm = ""
        for ch in reversed(raw):
            cu = ch.upper()
            if cu in EN_TO_AR_DIGITS or cu in EN_TO_AR_LETTERS:
                en_norm = cu
                break
            en_eq = _ar_to_en_char(ch)
            if en_eq:
                en_norm = en_eq
                break
        st.session_state[en_key] = en_norm
        st.session_state[ar_key] = _en_to_ar_char(en_norm)
    return _cb


def _make_sync_ar_cb(key_prefix: str, idx: int):
    def _cb():
        en_key = f"{key_prefix}__en_{idx}"
        ar_key = f"{key_prefix}__ar_{idx}"
        raw = st.session_state.get(ar_key) or ""
        raw = raw.replace(TATWEEL, "").strip()
        if not raw:
            st.session_state[en_key] = ""
            return
        en_norm = ""
        for ch in reversed(raw):
            en_eq = _ar_to_en_char(ch)
            if en_eq:
                en_norm = en_eq
                break
            cu = ch.upper()
            if cu in EN_TO_AR_DIGITS or cu in EN_TO_AR_LETTERS:
                en_norm = cu
                break
        st.session_state[en_key] = en_norm
        st.session_state[ar_key] = _en_to_ar_char(en_norm)
    return _cb


def plate_input(label: str = "اللوحة",
                key: str = "plate_input",
                default: str = "",
                show_preview: bool = True,
                show_validation: bool = True,
                help_text: str = None) -> str:
    """مكوّن إدخال لوحة بخانات متزامنة EN/AR."""
    _inject_css_once()  # حقن تنسيق الخانات (خلية موحّدة مطابقة للعرض)
    default_canonical = to_canonical(default) if default else ""
    default_padded = list(default_canonical.ljust(_PLATE_LEN))[:_PLATE_LEN]

    init_flag = f"{key}__initialized"
    if not st.session_state.get(init_flag):
        for i in range(_PLATE_LEN):
            ch = default_padded[i] if i < len(default_padded) else " "
            ch = ch.strip()
            st.session_state[f"{key}__en_{i}"] = ch
            st.session_state[f"{key}__ar_{i}"] = _en_to_ar_char(ch) if ch else ""
        st.session_state[init_flag] = True

    if label:
        st.markdown(
            f'<div style="text-align:center;color:#F3C969;font-size:0.95rem;font-weight:600;margin:0.5rem 0 0.3rem 0;">{label}</div>',
            unsafe_allow_html=True
        )

    cols = st.columns(_PLATE_LEN, gap="small")
    for i in range(_PLATE_LEN):
        is_digit_slot = i < _DIGIT_SLOTS
        slot_label = "رقم" if is_digit_slot else "حرف"
        with cols[i]:
            st.text_input(
                label=f"{slot_label} عربي #{i+1}",
                key=f"{key}__ar_{i}",
                max_chars=3,
                on_change=_make_sync_ar_cb(key, i),
                label_visibility="collapsed",
                placeholder="ع",
            )
            st.markdown(
                '<div style="height:1px;background:linear-gradient(90deg,transparent,#E0A43B,transparent);margin:-0.15rem 0;"></div>',
                unsafe_allow_html=True
            )
            st.text_input(
                label=f"{slot_label} EN #{i+1}",
                key=f"{key}__en_{i}",
                max_chars=1,
                on_change=_make_sync_en_cb(key, i),
                label_visibility="collapsed",
                placeholder="EN",
            )

    en_values = [
        (st.session_state.get(f"{key}__en_{i}") or "").upper().strip()
        for i in range(_PLATE_LEN)
    ]
    canonical = "".join(en_values)

    if show_validation:
        if not canonical:
            st.markdown(
                '<div style="text-align:center;color:#F3C969;font-size:0.78rem;margin-top:0.3rem;">اكتب اللوحة بالعربي أو الإنجليزي في الخانات</div>',
                unsafe_allow_html=True
            )
        else:
            ok, msg = validate_canonical(canonical)
            if ok:
                st.markdown(
                    f'<div style="text-align:center;color:#10B981;font-size:0.78rem;margin-top:0.3rem;">✓ صالحة · ستُحفظ كـ: <b>{canonical}</b></div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div style="text-align:center;color:#EF4444;font-size:0.78rem;margin-top:0.3rem;">⚠ {msg}</div>',
                    unsafe_allow_html=True
                )

    return canonical
