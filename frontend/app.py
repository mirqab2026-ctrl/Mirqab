"""
مرقاب · الواجهة الرئيسية (تسجيل الدخول)
"""
import sys
import os
import hmac
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "frontend"))

import streamlit as st
from theme import apply_tuwaiq_theme, apply_background, apply_tuwaiq_logo, render_sidebar_logout, mirqab_wordmark

st.set_page_config(
    page_title="مرقاب · تسجيل الدخول",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed" if not st.session_state.get("authenticated") else "expanded",
)

apply_tuwaiq_logo()
apply_tuwaiq_theme()
apply_background("dashboard.jpg", darkness=0.75)

# بيانات الدخول تُقرأ من متغيّرات البيئة (GATE_USERNAME / GATE_PASSWORD).
# عند غياب المتغيّرات نستخدم admin/admin كقيمة افتراضية للعرض المحلي فقط،
# ونعرض تحذيراً واضحاً. لا توجد أي كلمة مرور فعلية مكتوبة داخل الكود.
USING_DEFAULT_CREDENTIALS = "GATE_PASSWORD" not in os.environ
VALID_USERNAME = os.environ.get("GATE_USERNAME", "admin")
VALID_PASSWORD = os.environ.get("GATE_PASSWORD", "admin")
MAX_ATTEMPTS = 5

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "login_attempts" not in st.session_state:
    st.session_state["login_attempts"] = 0
if "locked" not in st.session_state:
    st.session_state["locked"] = False


if st.session_state.get("authenticated"):
    # ===== الترحيب: شعار logo1 (بدلاً من الشعار + النص) =====
    welcome_logo_img = mirqab_wordmark(size_rem=5.4, sub=True)

    st.markdown(
        '<div style="display:flex;justify-content:center;align-items:center;'
        'margin:0.5rem auto 0.1rem auto;">'
        + welcome_logo_img +
        '</div>'
        '<div style="text-align:center;color:#9FB0C0;font-size:2rem;'
        'margin-bottom:0.1rem;font-family:\'Saudi\',system-ui;font-weight:500;'
        'letter-spacing:0.01em;line-height:1.1;">'
        'مرحبا بكم'
        '</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<hr style="border:0;height:2px;background:linear-gradient(90deg,transparent,#E0A43B 30%,#F3C969 50%,#E0A43B 70%,transparent);margin:0.4rem auto 0.4rem auto;width:60%;">',
        unsafe_allow_html=True
    )

    # ===== الاقتباس الفني =====
    quote_html = (
        '<div style="text-align:center; padding:0.4rem 1rem; max-width:100%; margin:-0.4cm auto 0 auto;">'

        # نص الاقتباس - سطر واحد مميّز ومتوسّط
        '<div style="display:flex; justify-content:center; align-items:center; margin:1cm auto 0.5cm auto;">'
        '<div style="font-family:\'Saudi\',system-ui,sans-serif; '
        'font-size:1.65rem; line-height:1.35; color:#FFEAC4; '
        'font-weight:700; padding:0.5rem 2rem; '
        'background:linear-gradient(135deg,#FFE0A0 0%,#F3C969 50%,#E0A43B 100%); '
        '-webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;'
        'filter:drop-shadow(0 3px 10px rgba(0,0,0,0.8));'
        'white-space:nowrap; '
        'border-top:1px solid rgba(243,201,105,0.4); border-bottom:1px solid rgba(243,201,105,0.4);'
        'letter-spacing:-0.005em; text-align:center;">'
        'همّة السعوديين مثل جبل طويق، ولن تنكسر إلا إذا انهد هذا الجبل وتساوى بالأرض'
        '</div>'
        '</div>'

        # خط فاصل زخرفي
        '<div style="margin:0.5rem auto; width:120px; height:2px;'
        'background:linear-gradient(90deg,transparent,#F3C969,transparent);"></div>'

        # نسبة القول - سطر واحد ذهبي
        '<div style="font-family:\'Saudi\',system-ui,sans-serif; color:#F3C969; '
        'font-size:1.2rem; font-weight:600; letter-spacing:0.015em; line-height:1.25; '
        'text-shadow:0 2px 6px rgba(0,0,0,0.5); white-space:nowrap;">'
        'صاحب السمو الملكي الأمير محمد بن سلمان بن عبد العزيز آل سعود'
        '</div>'
        '<div style="font-family:\'Saudi\',system-ui,sans-serif; color:#6B7A8A; '
        'font-size:0.9rem; font-weight:400; letter-spacing:0.02em; margin-top:0.1rem;line-height:1.2;">'
        'ولي عهد المملكة العربية السعودية'
        '</div>'

        '</div>'
    )
    st.markdown(quote_html, unsafe_allow_html=True)

    # زر تسجيل الخروج موجود في السايدبار فقط
    render_sidebar_logout()

else:
    login_logo_img = mirqab_wordmark(size_rem=5.4, sub=True)

    st.markdown(
        '<div style="display:flex;justify-content:center;align-items:center;'
        'margin:0 auto 0.1rem auto;">'
        + login_logo_img +
        '</div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="tuwaiq-subtitle" style="text-align:center;margin-bottom:0.2rem;">سجّل الدخول للوصول إلى النظام</div>',
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        if USING_DEFAULT_CREDENTIALS:
            st.warning(
                "⚠️ يتم استخدام بيانات الدخول الافتراضية (admin/admin). "
                "للأمان، اضبط GATE_USERNAME و GATE_PASSWORD — "
                "انسخ credentials.example.bat إلى credentials.local.bat وغيّر القيم."
            )
        if st.session_state.get("locked"):
            st.error(f"تم قفل الحساب بسبب {MAX_ATTEMPTS} محاولات فاشلة. يرجى إعادة التشغيل.")
        else:
            with st.form("login_form", clear_on_submit=False):
                fc1, fc2 = st.columns(2)
                with fc1:
                    username = st.text_input("اسم المستخدم", placeholder="admin")
                with fc2:
                    password = st.text_input("كلمة المرور", type="password", placeholder="••••••••")
                rc1, rc2, rc3 = st.columns([1, 3, 1.2])
                with rc1:
                    remember = st.checkbox("تذكّرني")
                with rc3:
                    submit = st.form_submit_button("دخول", type="primary", use_container_width=True)

                if submit:
                    if not username or not password:
                        st.warning("يرجى إدخال اسم المستخدم وكلمة المرور")
                    elif (hmac.compare_digest(username, VALID_USERNAME)
                          and hmac.compare_digest(password, VALID_PASSWORD)):
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = username
                        st.session_state["login_attempts"] = 0
                        st.success("تم تسجيل الدخول بنجاح! جاري التحويل...")
                        st.balloons()
                        st.rerun()
                    else:
                        st.session_state["login_attempts"] += 1
                        remaining = MAX_ATTEMPTS - st.session_state["login_attempts"]
                        if remaining <= 0:
                            st.session_state["locked"] = True
                            st.error("تم قفل الحساب! تجاوزت الحد المسموح من المحاولات.")
                        else:
                            st.error(f"بيانات الدخول غير صحيحة · المحاولات المتبقية: {remaining}")
        st.markdown("""
        <div style="text-align:center; color:#9FB0C0; font-size:0.85rem;
                    padding:0.25rem; font-family:'Saudi',system-ui,sans-serif; font-weight:400; letter-spacing:0.015em; line-height:1.4;">
            "همّة السعوديين مثل جبل طويق"
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#6B7A8A; padding:0.5rem 1rem; font-size:1.25rem;
            font-family:'Saudi',system-ui,sans-serif; line-height:1.4; letter-spacing:0.015em; font-weight:400;
            display:flex; flex-direction:column; align-items:center; justify-content:center;">
    <div style="text-align:center;">Presidency of State Security - GID</div>
    <div style="text-align:center;">AI Diploma with Tuwaiq Academy - Graduation Project 2026</div>
    <div style="text-align:center;">E. Kasnawi &amp; M. Alnemari</div>
</div>
""", unsafe_allow_html=True)
