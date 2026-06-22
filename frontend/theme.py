"""
ثيم طويق الموحّد + نظام خلفيات احترافي + خط كوفي مستوحى
==========================================================
يستورد في كل صفحة لتطبيق ثيم مستوحى من جبال طويق وخطها الكوفي.
"""
import streamlit as st
import base64
import html
from pathlib import Path


ASSETS_DIR = Path(__file__).parent.parent / "assets" / "backgrounds"
FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"


# ============================================================
# Saudi Font Loader · محمّل الخط السعودي الرسمي
# ============================================================
# أسماء الملفات المحتملة لكل وزن (الترتيب = الأولوية)
_SAUDI_FONT_WEIGHTS = {
    300: ["Saudi-Light.ttf", "Saudi-Light.otf"],
    400: ["Saudi-Regular.ttf", "Saudi-Regular.otf",
          "Saudi.ttf", "Saudi.otf"],
    500: ["Saudi-Medium.ttf", "Saudi-Medium.otf"],
    700: ["Saudi-Bold.ttf", "Saudi-Bold.otf"],
}


@st.cache_resource(show_spinner=False)
def _build_saudi_font_face_css() -> str:
    """
    يبني @font-face CSS للخط السعودي الرسمي بصيغة base64.

    ✨ Cached via @st.cache_resource: يُحسب مرة واحدة فقط لكل عملية Python.
       هذا يضمن أن السلسلة الناتجة متطابقة عبر كل تنقّلات الصفحات،
       ممّا يسمح للمتصفّح بـ cache الـ CSS وعدم إعادة تحميل الخط = لا ومضة.

    يبحث في assets/fonts/ ويُنشئ face لكل وزن متوفّر.
    لو لم يجد أي ملف، يُرجع نصاً فارغاً (والنظام يستخدم fallbacks).
    """
    if not FONTS_DIR.exists():
        return ""

    faces = []
    found_regular = None

    for weight, names in _SAUDI_FONT_WEIGHTS.items():
        for fname in names:
            fpath = FONTS_DIR / fname
            if fpath.exists():
                try:
                    data = base64.b64encode(fpath.read_bytes()).decode("ascii")
                    fmt = "opentype" if fpath.suffix.lower() == ".otf" else "truetype"
                    faces.append(
                        f"@font-face {{"
                        f"font-family:'Saudi';"
                        f"font-style:normal;"
                        f"font-weight:{weight};"
                        # block = يُخفي النص لجزء من الثانية ثم يضمن استخدام Saudi دائماً
                        # (مع base64 inline يستغرق ≤100ms، لذا غير محسوس)
                        f"font-display:block;"
                        # تم حذف unicode-range ليعمل Saudi على كل الرموز (عربي/أرقام/علامات)
                        # هذا يحلّ مشكلة الأجهزة بدون Segoe UI Arabic كامل
                        f"src:url(data:font/{fmt};base64,{data}) format('{fmt}');"
                        f"}}"
                    )
                    if weight == 400:
                        found_regular = fname
                    break # found this weight, move on
                except Exception:
                    continue

    # لو وُجد ملف واحد فقط (Regular) ولكن لم تُوجد بقية الأوزان،
    # نضيف font-synthesis ليُحاكي المتصفح Bold/Italic تلقائياً.
    if faces and found_regular and len(faces) == 1:
        faces.append(
            "* { font-synthesis: weight style !important; "
            "-webkit-font-synthesis: weight style !important; }"
        )

    if not faces:
        return ""

    return "<style>\n" + "\n".join(faces) + "\n</style>"


def apply_saudi_font() -> bool:
    """
    يحقن الخط السعودي في الصفحة الحالية (إذا توفّر الملف).

    ✨ ضمان الثبات:
    - font-display:block في @font-face → المتصفّح ينتظر الخط قبل عرض النص
    - Font Loading API يجبر المتصفّح على تحميل الخط فوراً بأعلى أولوية
    - النتيجة: Saudi يظهر دائماً، لا تذبذب بين الخطوط

    Returns: True لو تم تحميل الخط، False لو لم يتوفّر.
    """
    css = _build_saudi_font_face_css()
    if css:
        st.markdown(css, unsafe_allow_html=True)
        # ✨ Font preload + Font Loading API لضمان ظهور Saudi فوراً
        st.markdown(
            """
            <script>
            (function(){
              try {
                // إجبار المتصفّح على تحميل الخط فوراً بأعلى أولوية
                if (document.fonts && document.fonts.load) {
                  Promise.all([
                    document.fonts.load("400 1rem 'Saudi'"),
                    document.fonts.load("500 1rem 'Saudi'"),
                    document.fonts.load("700 1rem 'Saudi'"),
                  ]).then(function(){
                    // علامة على body تشير إلى أن الخط جاهز (للاستخدام في CSS لو احتجناه)
                    document.body.classList.add('saudi-font-ready');
                  }).catch(function(){});
                }
              } catch(e) {}
            })();
            </script>
            """,
            unsafe_allow_html=True
        )
        return True
    return False


# ملاحظة: تمّ توحيد الخط على Saudi فقط — الخطوط Kaman/InkBrush/Khadash حُذفت
# لتقليل حجم المشروع وتسريع التحميل.


TUWAIQ_COLORS = {
    "primary": "#E0A43B",
    "primary_dark": "#9A6A1E",
    "primary_light": "#F3C969",
    "amber": "#F0B450",
    "cream": "#E6ECF2",
    "muted": "#9FB0C0",
    "dark": "#0E1217",
    "surface": "#171D24",
    "elevated": "#222A33",
    "border": "#2C3540",
}

# ============================================================
# هوية مرقاب · شعار نصي ثلاثي الأبعاد + عمق احترافي
# ============================================================
def mirqab_wordmark(size_rem: float = 5.0, sub: bool = True, sub_text: str = "MIRQAB") -> str:
    """يبني شعار «مرقاب» النصي ثلاثي الأبعاد (ذهبي على فحمي) كـ HTML."""
    sub_html = (
        f'<div style="margin-top:0.45rem;font-family:\'Segoe UI\',system-ui,sans-serif;'
        f'font-weight:700;font-size:{max(0.8, size_rem*0.2):.2f}rem;letter-spacing:0.62em;'
        f'text-indent:0.62em;color:#9FB0C0;text-shadow:0 1px 2px rgba(0,0,0,0.6);">{sub_text}</div>'
    ) if sub else ""
    return (
        '<div style="text-align:center;line-height:1;user-select:none;">'
        f'<div style="display:inline-block;font-family:\'Saudi\',system-ui,sans-serif;'
        f'font-weight:800;font-size:{size_rem:.2f}rem;letter-spacing:0.015em;'
        'background:linear-gradient(168deg,#FFEFC8 0%,#F3C969 40%,#E0A43B 68%,#B5781F 100%);'
        '-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;'
        'text-shadow:0 1px 0 rgba(255,255,255,0.18),0 2px 0 #B5781F,0 3px 0 #93631a,'
        '0 4px 0 #7c5316,0 5px 1px rgba(0,0,0,0.35),0 7px 10px rgba(0,0,0,0.6),'
        '0 12px 30px rgba(224,164,59,0.30);">مرقاب</div>'
        f'{sub_html}'
        '</div>'
    )


MIRQAB_3D_CSS = """
<style>
    /* ===== عمق ثلاثي الأبعاد للعناوين الرئيسية ===== */
    [data-testid="stMain"] h1 {
        background: linear-gradient(168deg,#FFEFC8 0%,#F3C969 42%,#E0A43B 70%,#B5781F 100%) !important;
        -webkit-background-clip: text !important; background-clip: text !important;
        -webkit-text-fill-color: transparent !important; color: transparent !important;
        text-shadow: 0 1px 0 rgba(255,255,255,0.10), 0 2px 6px rgba(0,0,0,0.55),
                     0 8px 22px rgba(224,164,59,0.20) !important;
        font-weight: 800 !important; letter-spacing: 0.01em !important;
    }
    [data-testid="stMain"] h2, [data-testid="stMain"] h3 {
        text-shadow: 0 1px 2px rgba(0,0,0,0.6), 0 2px 10px rgba(224,164,59,0.12) !important;
    }
    /* ===== بطاقات زجاجية بعمق ===== */
    .info-card, .lg-result-card, div[data-testid="stMetric"],
    [data-testid="stExpander"] details {
        background: linear-gradient(158deg, rgba(34,42,51,0.72) 0%, rgba(23,29,36,0.78) 100%) !important;
        border: 1px solid rgba(224,164,59,0.18) !important;
        border-radius: 0.85rem !important;
        box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset,
                    0 10px 28px rgba(0,0,0,0.45),
                    0 2px 6px rgba(0,0,0,0.35) !important;
        -webkit-backdrop-filter: blur(9px) !important; backdrop-filter: blur(9px) !important;
    }
    div[data-testid="stMetric"] { padding: 1rem 0.6rem !important; }
    [data-testid="stMetricValue"] {
        background: linear-gradient(168deg,#FFEFC8,#F3C969 55%,#E0A43B) !important;
        -webkit-background-clip: text !important; background-clip: text !important;
        -webkit-text-fill-color: transparent !important; color: transparent !important;
        font-weight: 800 !important; text-shadow: 0 2px 6px rgba(0,0,0,0.4);
    }
    /* ===== أزرار بعمق + ارتفاع عند المرور ===== */
    .stButton > button {
        box-shadow: 0 1px 0 rgba(255,255,255,0.10) inset,
                    0 6px 16px rgba(0,0,0,0.40),
                    0 2px 4px rgba(224,164,59,0.18) !important;
        transition: transform .14s ease, box-shadow .14s ease !important;
        border: 1px solid rgba(224,164,59,0.30) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 1px 0 rgba(255,255,255,0.14) inset,
                    0 12px 26px rgba(0,0,0,0.48),
                    0 4px 12px rgba(224,164,59,0.30) !important;
    }
    .stButton > button:active { transform: translateY(0) !important; }
</style>
"""



# شعار جبل طويق المستوحى من الرسم الخطي - SVG
TUWAIQ_LOGO_SVG = """<svg viewBox="0 0 300 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;background:transparent;"><defs><linearGradient id="cliffMain" x1="0%" y1="0%" x2="0%" y2="100%"><stop offset="0%" stop-color="#FFD68A"/><stop offset="20%" stop-color="#E0A43B"/><stop offset="50%" stop-color="#A87A28"/><stop offset="80%" stop-color="#8B4513"/><stop offset="100%" stop-color="#10161C"/></linearGradient><linearGradient id="cliffShade" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#E0A43B"/><stop offset="100%" stop-color="#1A2129"/></linearGradient><linearGradient id="cliffLight" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#FFE0A0"/><stop offset="100%" stop-color="#A87A28"/></linearGradient></defs><path d="M 35 210 L 35 38 L 42 35 L 50 32 L 60 30 L 70 30 L 78 33 L 85 36 L 90 40 L 95 42 L 100 45 L 105 50 L 108 60 L 112 75 L 115 90 L 120 100 L 130 110 L 145 118 L 160 125 L 175 132 L 190 138 L 205 145 L 220 155 L 235 165 L 250 175 L 265 188 L 280 200 L 285 210 Z" fill="url(#cliffMain)" stroke="#1A2129" stroke-width="1.5" stroke-linejoin="round"/><path d="M 35 38 L 42 35 L 50 32 L 60 30 L 70 30 L 78 33 L 85 36 L 90 40 L 95 42 L 100 45 L 105 50 L 100 48 L 90 44 L 80 38 L 70 34 L 58 33 L 48 35 L 40 38 Z" fill="url(#cliffLight)" opacity="0.7"/><path d="M 105 50 L 108 60 L 112 75 L 115 90 L 120 100 L 115 95 L 110 80 L 107 65 Z" fill="url(#cliffShade)" opacity="0.55"/><path d="M 120 100 L 130 110 L 145 118 L 142 124 L 130 118 L 122 108 Z" fill="url(#cliffShade)" opacity="0.5"/><path d="M 145 118 L 160 125 L 175 132 L 172 138 L 160 132 L 150 124 Z" fill="url(#cliffShade)" opacity="0.45"/><path d="M 175 132 L 190 138 L 205 145 L 202 150 L 188 144 L 180 138 Z" fill="url(#cliffShade)" opacity="0.4"/><path d="M 205 145 L 220 155 L 235 165 L 232 170 L 218 162 L 210 152 Z" fill="url(#cliffShade)" opacity="0.35"/><path d="M 235 165 L 250 175 L 265 188 L 262 192 L 248 182 L 238 172 Z" fill="url(#cliffShade)" opacity="0.3"/><path d="M 40 55 L 105 55" stroke="#1A2129" stroke-width="0.6" opacity="0.55"/><path d="M 38 75 L 110 75" stroke="#1A2129" stroke-width="0.6" opacity="0.5"/><path d="M 38 95 L 115 95" stroke="#1A2129" stroke-width="0.6" opacity="0.5"/><path d="M 36 118 L 130 118" stroke="#1A2129" stroke-width="0.6" opacity="0.45"/><path d="M 36 140 L 160 140" stroke="#1A2129" stroke-width="0.6" opacity="0.4"/><path d="M 35 162 L 200 162" stroke="#1A2129" stroke-width="0.6" opacity="0.35"/><path d="M 35 185 L 240 185" stroke="#1A2129" stroke-width="0.6" opacity="0.3"/><path d="M 0 205 Q 80 195 160 200 T 300 198 L 300 215 L 0 215 Z" fill="#8B4513" opacity="0.55"/><path d="M 0 213 Q 100 207 200 213 T 300 211 L 300 220 L 0 220 Z" fill="#10161C"/></svg>"""


TUWAIQ_CSS = """
<style>
    /* ============================================
       نظام تصميم مرقاب · Design System
       ============================================ */

    /* ============================================
       FOUC Fix · حل بسيط بدون animation
       - font-display: optional يضمن استخدام fallback فوراً
       - Segoe UI fallback يبدو شبيهاً بـ Saudi على Windows
       ============================================ */

    /* النظام air-gapped بالكامل — لا استيراد خارجي من Google Fonts
       Streamlit يستخدم SVG inline لأيقوناته، والخط السعودي مُضمَّن base64 محلياً */

    /* ============================================================
       Material Icons · أي عنصر يحمل أيقونة Streamlit يستخدم Material Symbols
       (وليس Saudi) — يمنع ظهور أسماء الأيقونات كنص: upload, arrow_right, ...
       يستخدم specificity عالٍ ليتغلب على [data-testid="stMain"] * = (0,1,0)
       ============================================================ */
    .stApp [data-testid="stHeader"] button span,
    .stApp [data-testid="collapsedControl"] span,
    .stApp [data-testid="stSidebarCollapseButton"] span,
    .stApp button[kind="headerNoPadding"] span,
    .stApp button[kind="header"] span,
    /* أيقونات داخل المحتوى - specificity مزدوج */
    .stApp [data-testid="stIcon"],
    .stApp [data-testid="stIcon"] *,
    .stApp [data-testid="stIconMaterial"],
    .stApp [data-testid="stIconMaterial"] *,
    .stApp [data-testid="stMarkdownContainer"] [data-testid*="Icon"],
    .stApp span[data-testid*="Icon"],
    .stApp span[data-testid*="Icon"] *,
    .stApp [data-baseweb="icon"],
    .stApp [data-baseweb="icon"] *,
    /* فئات Material القياسية */
    .stApp .material-icons,
    .stApp .material-icons-outlined,
    .stApp .material-symbols-outlined,
    .stApp .material-symbols-rounded,
    .stApp .material-symbols-sharp,
    /* بعض إصدارات Streamlit تضيف هذه الفئات */
    .stApp [class*="iconStyle"],
    .stApp [class*="MaterialIcon"],
    .stApp [class*="material-symbol"],
    .stApp [class*="emotion-cache"] [class*="icon"] {
        font-family: 'Material Symbols Outlined', 'Material Symbols Rounded', 'Material Icons' !important;
        font-style: normal !important;
        font-weight: normal !important;
        font-size: 1.25rem !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        display: inline-block !important;
        white-space: nowrap !important;
        text-transform: none !important;
        word-wrap: normal !important;
        direction: ltr !important;
        font-feature-settings: 'liga' !important;
        -webkit-font-feature-settings: 'liga' !important;
        -webkit-font-smoothing: antialiased !important;
        text-rendering: optimizeLegibility !important;
    }
    /* أيقونات الـ header buttons أكبر قليلاً */
    [data-testid="stHeader"] button span,
    [data-testid="collapsedControl"] span,
    [data-testid="stSidebarCollapseButton"] span,
    button[kind="headerNoPadding"] span,
    button[kind="header"] span {
        font-size: 24px !important;
    }
    [data-testid="stHeader"] button { color: #F3C969 !important; }
    [data-testid="stHeader"] button:hover { color: #FFE0A0 !important; }

    /* === الخلفية === */
    .stApp {
        background: linear-gradient(180deg, #0E1217 0%, #141A21 50%, #0E1217 100%);
    }

    /* ============================================
       TYPOGRAPHY · نظام الطباعة السعودية الفنّي
       ============================================
       يستخدم الخط السعودي الرسمي عبر النظام بأكمله،
       مع تفعيل kerning والـ ligatures العربية لمنح
       طابع راقٍ يحاكي الوثائق الرسمية السعودية. */

    /* الأساس: الخط السعودي على معظم العناصر — مع استثناء عناصر الأيقونات
       (حتى لا تظهر أسماء أيقونات Material كنص: upload, arrow_right, ...) */
    html, body, .stApp,
    .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp a, .stApp button, .stApp label, .stApp input, .stApp textarea, .stApp select,
    [data-testid="stMain"] p,
    [data-testid="stMain"] h1, [data-testid="stMain"] h2,
    [data-testid="stMain"] h3, [data-testid="stMain"] h4,
    [data-testid="stMain"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] a,
    [data-testid="stSidebar"] button,
    [data-testid="stHeader"] {
        font-family: 'Saudi', 'Segoe UI', 'Tahoma', system-ui, sans-serif;
        font-feature-settings: 'kern' 1, 'liga' 1, 'calt' 1, 'rlig' 1;
        -webkit-font-feature-settings: 'kern' 1, 'liga' 1, 'calt' 1, 'rlig' 1;
        text-rendering: optimizeLegibility;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        font-variant-ligatures: common-ligatures contextual;
    }


    /* Display (العنوان الفنّي الكبير) — خط Saudi موحَّد */
    .tuwaiq-header {
        font-family: 'Saudi', 'Segoe UI', system-ui, sans-serif;
        font-size: 4rem;
        font-weight: 900;
        line-height: 1.3;
        letter-spacing: 0.005em;
        font-synthesis: weight style;
        -webkit-font-synthesis: weight style;
        -webkit-text-stroke: 0.5px currentColor;
        background: linear-gradient(135deg, #FFE0A0 0%, #F3C969 35%, #E0A43B 70%, #9A6A1E 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        filter: drop-shadow(0 4px 14px rgba(0,0,0,0.85));
        margin: 0 0 0.5rem 0;
    }

    .tuwaiq-subtitle {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif;
        font-size: 1.2rem;
        font-weight: 400;
        color: #E6ECF2;
        line-height: 1.7;
        letter-spacing: 0.01em;
        text-shadow: 0 2px 6px rgba(0,0,0,0.7);
        margin-bottom: 1.5rem;
    }

    /* H1-H4 · هرمية العناوين السعودية */
    [data-testid="stMain"] h1 {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 2.25rem !important;
        font-weight: 700 !important;
        color: #F3C969 !important;
        line-height: 1.4 !important;
        letter-spacing: 0 !important;
        text-shadow: 0 2px 8px rgba(0,0,0,0.6);
        margin: 1.25rem 0 0.85rem 0 !important;
    }
    [data-testid="stMain"] h2 {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        color: #F3C969 !important;
        line-height: 1.4 !important;
        letter-spacing: 0 !important;
        text-shadow: 0 2px 6px rgba(0,0,0,0.5);
        margin: 1rem 0 0.6rem 0 !important;
    }
    [data-testid="stMain"] h3 {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        color: #F3C969 !important;
        line-height: 1.5 !important;
        letter-spacing: 0.005em !important;
        text-shadow: 0 1px 4px rgba(0,0,0,0.5);
        margin: 0.9rem 0 0.5rem 0 !important;
    }
    [data-testid="stMain"] h4 {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        color: #FFE0A0 !important;
        line-height: 1.55 !important;
        letter-spacing: 0.01em !important;
        margin: 0.75rem 0 0.4rem 0 !important;
    }

    /* Body Text · نص المحتوى (تباعد سطور أوسع للقراءة العربية المريحة)
       اتجاه النص يُحدَّد تلقائياً (RTL للعربي، LTR للإنجليزي) */
    [data-testid="stMain"] p,
    [data-testid="stMain"] li,
    [data-testid="stMain"] .stMarkdown p,
    [data-testid="stMain"] .stMarkdown li,
    [data-testid="stMain"] label {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1rem !important;
        font-weight: 400 !important;
        color: #E6ECF2 !important;
        line-height: 1.85 !important;
        letter-spacing: 0.005em !important;
        unicode-bidi: plaintext !important;
    }

    /* اتجاه تلقائي للعناوين أيضاً */
    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3,
    [data-testid="stMain"] h4 {
        unicode-bidi: plaintext !important;
    }

    /* Strong/Bold — وزن متوسط (500) أرشق من Bold كامل في الخط السعودي */
    [data-testid="stMain"] strong,
    [data-testid="stMain"] b {
        color: #FFE0A0 !important;
        font-weight: 700 !important;
    }

    /* Caption · النصوص الصغيرة (تباعد حروف أوسع لتُقرأ بوضوح في الحجم الصغير) */
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p,
    [data-testid="stCaptionContainer"] * {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 0.85rem !important;
        color: #9FB0C0 !important;
        font-weight: 400 !important;
        line-height: 1.65 !important;
        letter-spacing: 0.015em !important;
    }

    /* Code */
    [data-testid="stMain"] code {
        font-family: 'Consolas', 'Courier New', monospace !important;
        color: #F3C969 !important;
        background: rgba(23,29,36,0.7) !important;
        padding: 0.15rem 0.4rem;
        border-radius: 0.25rem;
        font-size: 0.9em;
    }

    /* ============================================
       COMPONENTS · المكونات
       ============================================ */

    /* === Metric Cards · مؤشرات KPI (ارتفاع ثابت موحّد + delta مُثبَّت بالأسفل) === */
    div[data-testid="stMetric"] {
        background: rgba(23,29,36,0.92);
        backdrop-filter: blur(10px);
        border: 1px solid #2C3540;
        border-radius: 0.75rem;
        border-top: 3px solid #E0A43B;
        box-shadow: 0 4px 24px rgba(0,0,0,0.5);
        text-align: center !important;
        transition: transform 0.2s, box-shadow 0.2s;
        /* ارتفاع ثابت + padding سفلي يحجز مكاناً للـ delta حتى لو غاب */
        height: 11.5rem !important;
        min-height: 11.5rem !important;
        max-height: 11.5rem !important;
        padding: 1.25rem 1rem 2.6rem !important;
        position: relative !important;
        overflow: hidden !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(224,164,59,0.25);
    }
    div[data-testid="stMetric"] > div {
        text-align: center !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
    }
    /* delta مُثبَّت دائماً بنفس الموضع السفلي — لا يدفع البطاقة لتكبر */
    [data-testid="stMetricDelta"] {
        position: absolute !important;
        bottom: 0.8rem !important;
        left: 0 !important;
        right: 0 !important;
        margin: 0 !important;
        text-align: center !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }

    /* Metric Label · التسمية (gradient ذهبي بارز - وزن متوسط ليتنفّس) */
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] *,
    [data-testid="stMetricLabel"] p {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1.35rem !important;
        font-weight: 600 !important;
        background: linear-gradient(135deg, #FFE0A0 0%, #F3C969 50%, #E0A43B 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        color: transparent !important;
        filter: drop-shadow(0 2px 6px rgba(0,0,0,0.6));
        letter-spacing: 0.01em !important;
        line-height: 1.45 !important;
        margin-bottom: 0.5rem !important;
        text-align: center !important;
    }

    /* Metric Value · القيمة (رقم كبير - أرقام جدولية محاذاة عمودياً) */
    [data-testid="stMetricValue"],
    [data-testid="stMetricValue"] *,
    [data-testid="stMetricValue"] div {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 2.6rem !important;
        font-weight: 700 !important;
        color: #FFEAC4 !important;
        -webkit-text-fill-color: #FFEAC4 !important;
        background: none !important;
        line-height: 1.15 !important;
        letter-spacing: -0.005em !important;
        font-feature-settings: 'tnum' 1, 'lnum' 1, 'kern' 1 !important;
        -webkit-font-feature-settings: 'tnum' 1, 'lnum' 1, 'kern' 1 !important;
        font-variant-numeric: tabular-nums lining-nums;
        text-shadow: 0 3px 10px rgba(0,0,0,0.7);
        text-align: center !important;
    }

    /* === Buttons === */
    .stButton > button {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        background: linear-gradient(135deg, #E0A43B 0%, #9A6A1E 100%);
        color: #E6ECF2 !important;
        border: 1px solid #2C3540;
        border-radius: 0.4rem;
        padding: 0.55rem 1.1rem;
        letter-spacing: 0.025em !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #F3C969 0%, #E0A43B 100%);
        border-color: #F3C969;
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(224,164,59,0.4);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #F3C969 0%, #E0A43B 100%);
        border: 2px solid #F3C969;
        font-weight: 700 !important;
    }

    /* === Sidebar === */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(23,29,36,0.97) 0%, rgba(14,18,23,0.98) 100%);
        backdrop-filter: blur(12px);
        border-right: 2px solid #2C3540;
    }
    [data-testid="stSidebar"] * {
        font-family: 'Saudi', 'Segoe UI', system-ui, sans-serif;
        color: #E6ECF2;
        letter-spacing: 0.005em;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        font-family: 'Saudi', 'Segoe UI', system-ui, sans-serif !important;
        color: #F3C969 !important;
        font-weight: 600 !important;
        letter-spacing: 0 !important;
    }

    /* ============================================
       Sidebar Nav · توحيد قائمة الصفحات
       ============================================
       كل العناصر بنفس الحجم والوزن والخط واللون والـ padding. */
    [data-testid="stSidebarNav"] {
        padding-top: 0.5rem !important;
    }
    [data-testid="stSidebarNav"] ul {
        gap: 0.2rem !important;
    }
    [data-testid="stSidebarNav"] ul li a,
    [data-testid="stSidebarNav"] ul li a *,
    [data-testid="stSidebarNav"] ul li a span,
    [data-testid="stSidebarNav"] ul li a p,
    [data-testid="stSidebarNav"] ul li a div {
        font-family: 'Saudi', 'Segoe UI', system-ui, sans-serif !important;
        font-size: 1rem !important;
        font-weight: 500 !important;
        line-height: 1.5 !important;
        letter-spacing: 0.005em !important;
        color: #E6ECF2 !important;
        text-decoration: none !important;
    }
    [data-testid="stSidebarNav"] ul li a {
        padding: 0.55rem 0.85rem !important;
        border-radius: 0.4rem !important;
        transition: background 0.15s, color 0.15s !important;
    }
    [data-testid="stSidebarNav"] ul li a:hover,
    [data-testid="stSidebarNav"] ul li a:hover * {
        background: rgba(224,164,59,0.12) !important;
        color: #FFE0A0 !important;
    }
    /* الصفحة النشطة (active) */
    [data-testid="stSidebarNav"] ul li a[aria-current="page"],
    [data-testid="stSidebarNav"] ul li a[aria-current="page"] *,
    [data-testid="stSidebarNav"] ul li a.active,
    [data-testid="stSidebarNav"] ul li a.active * {
        background: rgba(224,164,59,0.22) !important;
        color: #F3C969 !important;
        font-weight: 600 !important;
    }

    /* ====================================================
       استبدال "app" في أول رابط بـ "واجهة النظام"
       يستخدم تقنية text-indent + ::before على الـ <a> مباشرة
       — يعمل بغض النظر عن تركيب DOM الداخلي لـ Streamlit
       ==================================================== */
    nav[data-testid="stSidebarNav"] > ul > li:first-child > a,
    nav[data-testid="stSidebarNav"] > ul > li:first-child > a *,
    [data-testid="stSidebarNav"] > ul > li:first-child > a,
    [data-testid="stSidebarNav"] > ul > li:first-child > a *,
    [data-testid="stSidebarNav"] ul li:first-child a,
    [data-testid="stSidebarNav"] ul li:first-child a span,
    [data-testid="stSidebarNav"] ul li:first-child a p,
    [data-testid="stSidebarNav"] ul li:first-child a div {
        font-size: 0 !important;
        color: transparent !important;
        text-indent: -9999em !important;
        line-height: 0 !important;
    }
    nav[data-testid="stSidebarNav"] > ul > li:first-child > a::before,
    [data-testid="stSidebarNav"] > ul > li:first-child > a::before,
    [data-testid="stSidebarNav"] ul li:first-child a::before {
        content: "واجهة النظام" !important;
        display: inline-block !important;
        text-indent: 0 !important;
        font-size: 1rem !important;
        line-height: 1.5 !important;
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-weight: 500 !important;
        letter-spacing: 0.005em !important;
        color: #E6ECF2 !important;
    }
    /* عند تفعيل الصفحة الرئيسية: لون ذهبي للنص المستبدَل */
    [data-testid="stSidebarNav"] ul li:first-child a[aria-current="page"]::before {
        color: #F3C969 !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebarNav"] ul li:first-child a:hover::before {
        color: #FFE0A0 !important;
    }

    /* === Cards === */
    .info-card {
        background: rgba(23,29,36,0.95);
        backdrop-filter: blur(10px);
        padding: 1.5rem;
        border-radius: 0.75rem;
        border: 1px solid #2C3540;
        border-left: 4px solid #E0A43B;
        box-shadow: 0 8px 24px rgba(0,0,0,0.5);
        transition: transform 0.2s;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }
    .info-card:hover {
        transform: translateY(-2px);
    }
    .info-card h4,
    .info-card p,
    .info-card div,
    .info-card span {
        color: #F3C969 !important;
        margin-top: 0;
        text-align: center !important;
        width: 100% !important;
        unicode-bidi: plaintext !important;
        direction: ltr;
    }
    .info-card h4 { color: #F3C969 !important; margin-top: 0 !important; margin-bottom: 0.5rem !important; }
    .info-card p { color: #9FB0C0 !important; }

    /* === Divider === مركّز افتراضياً مع احترام width inline === */
    hr {
        border: 0 !important;
        background: linear-gradient(90deg, transparent, #E0A43B 30%, #F3C969 50%, #E0A43B 70%, transparent) !important;
        height: 2px !important;
        margin-top: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        margin-left: auto !important;
        margin-right: auto !important;
        display: block !important;
    }

    /* === Tabs === */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(23,29,36,0.85);
        backdrop-filter: blur(8px);
        border-bottom: 2px solid #2C3540;
        border-radius: 0.5rem 0.5rem 0 0;
        gap: 0.25rem;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1rem !important;
        font-weight: 600;
        color: #9FB0C0;
        letter-spacing: 0.015em;
        padding: 0.75rem 1.25rem;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #F3C969 !important;
        background: rgba(58,42,30,0.95);
        border-bottom: 2px solid #F3C969;
    }

    /* === Alerts === */
    [data-testid="stAlert"] {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-weight: 500;
        line-height: 1.7;
        letter-spacing: 0.005em;
        background: rgba(23,29,36,0.95) !important;
        backdrop-filter: blur(10px);
        border-left-color: #E0A43B;
        border-radius: 0.5rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    }

    /* === DataFrame · جداول البيانات === */
    [data-testid="stDataFrame"] {
        background: rgba(23,29,36,0.92);
        backdrop-filter: blur(8px);
        border: 1px solid #2C3540;
        border-radius: 0.5rem;
    }
    [data-testid="stDataFrame"] * {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        color: #E6ECF2 !important;
        font-size: 0.95rem !important;
        font-variant-numeric: tabular-nums lining-nums;
        font-feature-settings: 'tnum' 1, 'lnum' 1, 'kern' 1;
    }
    [data-testid="stDataFrame"] thead th {
        color: #F3C969 !important;
        background: rgba(14,18,23,0.85) !important;
        font-weight: 600 !important;
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1rem !important;
        letter-spacing: 0.01em;
    }

    /* === Inputs === */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-size: 1rem !important;
        font-weight: 400;
        letter-spacing: 0.005em;
        background: rgba(14,18,23,0.85) !important;
        color: #E6ECF2 !important;
        border: 1px solid #2C3540 !important;
        border-radius: 0.4rem;
        padding: 0.55rem 0.75rem !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
        border-color: #E0A43B !important;
        box-shadow: 0 0 0 2px rgba(224,164,59,0.18) !important;
    }
    .stSelectbox > div > div {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        background: rgba(14,18,23,0.85) !important;
        border-color: #2C3540 !important;
        color: #E6ECF2 !important;
    }

    /* === Expander === */
    .streamlit-expanderHeader {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        letter-spacing: 0.005em !important;
        background: rgba(23,29,36,0.92);
        border: 1px solid #2C3540;
        color: #F3C969 !important;
        font-weight: 700;
    }

    /* === Background container === */
    .main .block-container,
    [data-testid="stMain"] .block-container {
        background: transparent !important;
        backdrop-filter: none !important;
        box-shadow: none !important;
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }

</style>
"""


def apply_tuwaiq_theme():
    """يطبّق ثيم طويق على الصفحة الحالية + تحميل الخط الموحَّد Saudi.

    تم توحيد كل النصوص العربية على خط Saudi فقط.
    الخطوط الثلاثة (Kaman/InkBrush/Khadash) لم تعد تُحمَّل لتسريع التحميل.
    """
    saudi_css = _build_saudi_font_face_css()

    def _inner(css: str) -> str:
        return css.replace("<style>", "").replace("</style>", "") if css else ""

    fonts_inner = _inner(saudi_css)
    combined = (
        ("<style>" + fonts_inner + "</style>" if fonts_inner.strip() else "")
        + TUWAIQ_CSS
        + MIRQAB_3D_CSS
    )
    st.markdown(combined, unsafe_allow_html=True)


def apply_background(image_name: str = "", darkness: float = 0.70):
    """خلفية عصرية بتدرّجات CSS وأشكال زجاجية ثلاثية الأبعاد (بدون صور).

    image_name يُستخدم فقط لتوليد تنويعة لونية خفيفة لكل صفحة (تماسك + تمايز).
    """
    import hashlib
    h = int(hashlib.md5((image_name or "mirqab").encode("utf-8")).hexdigest(), 16)
    gx = 70 + (h % 22)          # موضع الوهج الذهبي الأفقي
    gy = 8 + (h // 7 % 18)      # وموضعه العمودي
    cx = 8 + (h // 13 % 22)     # موضع الوهج البارد
    cy = 78 + (h // 17 % 16)
    rot = (h % 18) - 9          # ميل خفيف للوحات الزجاجية

    bg_css = f"""
    <style>
        [data-testid="stApp"] {{
            background:
                radial-gradient(60% 50% at {gx}% {gy}%, rgba(224,164,59,0.16) 0%, transparent 60%),
                radial-gradient(55% 55% at {cx}% {cy}%, rgba(58,84,110,0.20) 0%, transparent 62%),
                radial-gradient(120% 90% at 50% 0%, #11161C 0%, #0C1015 55%, #090C10 100%) !important;
            background-attachment: fixed !important;
        }}
        /* شبكة دقيقة خافتة لإحساس تقني */
        [data-testid="stApp"]::before {{
            content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
            background:
                repeating-linear-gradient(0deg, transparent 0 39px, rgba(224,164,59,0.030) 39px 40px),
                repeating-linear-gradient(90deg, transparent 0 39px, rgba(224,164,59,0.030) 39px 40px);
            -webkit-mask-image: radial-gradient(circle at 50% 35%, #000 0%, transparent 78%);
            mask-image: radial-gradient(circle at 50% 35%, #000 0%, transparent 78%);
        }}
        /* أشكال زجاجية ثلاثية الأبعاد عائمة */
        [data-testid="stApp"]::after {{
            content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
            background:
                radial-gradient(circle at {gx}% {gy+6}%, rgba(243,201,105,0.10) 0 14px, transparent 15px),
                radial-gradient(closest-side at 82% 70%, rgba(224,164,59,0.10), transparent),
                radial-gradient(closest-side at 16% 26%, rgba(80,120,150,0.10), transparent);
            filter: blur(2px);
        }}
        [data-testid="stMain"], section.main {{ background: transparent !important; }}
        [data-testid="stMain"] .block-container {{
            position: relative; z-index: 1;
            background: transparent !important; backdrop-filter: none !important; box-shadow: none !important;
        }}
        /* لوح زجاجي مائل خلف المحتوى الرئيسي يمنح عمقاً ثلاثي الأبعاد */
        [data-testid="stMain"] .block-container::before {{
            content: ""; position: absolute; inset: -1.2rem 0 0 0; z-index: -1;
            transform: perspective(1200px) rotateX({rot/9:.2f}deg);
            background: linear-gradient(158deg, rgba(34,42,51,0.30) 0%, rgba(14,18,23,0.10) 60%, transparent 100%);
            border-top: 1px solid rgba(224,164,59,0.10);
            border-radius: 1.2rem; box-shadow: 0 30px 80px rgba(0,0,0,0.35);
            pointer-events: none;
        }}
    </style>
    """
    st.markdown(bg_css, unsafe_allow_html=True)


def render_tuwaiq_logo():
    """يعرض شعار «مرقاب» النصي ثلاثي الأبعاد - يُستخدم في السايدبار."""
    html = (
        '<div class="tuwaiq-logo-container" style="text-align:center;padding:0.4rem 0 0.6rem 0;">'
        + mirqab_wordmark(size_rem=2.6, sub=True) +
        '<div style="margin-top:0.35rem;color:#6B7A8A;font-size:0.72rem;'
        'font-family:\'Segoe UI\',system-ui,sans-serif;letter-spacing:0.04em;">v1.0</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _get_logo_path():
    """يُرجع مسار الشعار المُفضَّل (PNG ثم SVG كـ fallback)."""
    base = Path(__file__).parent.parent / "assets"
    for name in ("logo.png", "tuwaiq_logo.png", "tuwaiq_logo.svg"):
        f = base / name
        if f.exists():
            return f
    return None


def _get_sidebar_logo_path():
    """يُرجع مسار شعار السايدبار المخصّص (logo1.png) مع fallback للشعار الرئيسي."""
    base = Path(__file__).parent.parent / "assets"
    for name in ("logo1.png", "logo1.PNG"):
        f = base / name
        if f.exists():
            return f
    return _get_logo_path()


def _logo_data_uri() -> str:
    """يُرجع الشعار كـ data URI (base64) لاستخدامه inline في HTML."""
    p = _get_logo_path()
    if not p:
        return ""
    mime = "image/png" if p.suffix.lower() == ".png" else "image/svg+xml"
    data_b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data_b64}"


def _logo1_data_uri() -> str:
    """يُرجع شعار logo1.png كـ data URI لاستخدامه في شاشات الترحيب/الدخول."""
    p = _get_sidebar_logo_path()
    if not p:
        return ""
    mime = "image/png" if p.suffix.lower() == ".png" else "image/svg+xml"
    data_b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data_b64}"


def apply_tuwaiq_logo():
    """يضع شعار «مرقاب» النصي ثلاثي الأبعاد أعلى الشريط الجانبي (بدون صورة)."""
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:0.7rem 0 0.5rem 0;">'
            + mirqab_wordmark(size_rem=2.5, sub=True) +
            '<div style="margin-top:0.3rem;height:2px;width:62%;margin-inline:auto;'
            'background:linear-gradient(90deg,transparent,#E0A43B,transparent);"></div>'
            '</div>',
            unsafe_allow_html=True,
        )


def check_auth():
    """يتحقق من تسجيل دخول المستخدم.

    إذا لم يكن مسجّلاً → يحوّله مباشرةً إلى صفحة تسجيل الدخول (app.py)
    بدل عرض رسالة خطأ.
    """
    if not st.session_state.get("authenticated", False):
        # Streamlit 1.30+ يدعم switch_page بمسار نسبي للملف الرئيسي
        try:
            st.switch_page("app.py")
        except Exception:
            # fallback لإصدارات أقدم
            st.error("يجب تسجيل الدخول أولاً للوصول لهذه الصفحة")
            st.info("ارجع إلى الصفحة الرئيسية وسجّل الدخول")
            st.stop()



# ملاحظة: تعريف render_sidebar_logout الفعلي موجود أدناه (نسخة واحدة فقط).


# CSS لتوحيد الخط واللون - يُطبّق على الصفحات ما عدا app.py
_UNIFIED_TEXT_CSS = """
<style>
    /* توسيط عناوين الصفحات (H1 الرئيسي) في جميع الصفحات */
    [data-testid="stMain"] .stMarkdown h1,
    [data-testid="stMain"] h1 {
        text-align: center !important;
        margin-left: auto !important;
        margin-right: auto !important;
        width: 100% !important;
    }

    [data-testid="stMain"] p,
    [data-testid="stMain"] div:not([data-testid*="Icon"]):not([data-baseweb="icon"]),
    [data-testid="stMain"] span:not([data-testid*="Icon"]):not([class*="material-symbol"]):not([class*="material-icon"]),
    [data-testid="stMain"] label,
    [data-testid="stMain"] li,
    [data-testid="stMain"] strong,
    [data-testid="stMain"] em,
    [data-testid="stMain"] td,
    [data-testid="stMain"] th,
    [data-testid="stMain"] a,
    .stMarkdown p,
    .stMarkdown span:not([class*="material-symbol"]):not([class*="material-icon"]),
    .stMarkdown div:not([data-testid*="Icon"]),
    .stMarkdown li,
    .stCaption,
    [data-testid="stCaptionContainer"] p {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        font-feature-settings: 'kern' 1, 'liga' 1, 'calt' 1, 'rlig' 1;
        -webkit-font-smoothing: antialiased;
    }

    [data-testid="stMain"] p,
    [data-testid="stMain"] li,
    [data-testid="stMain"] label {
        color: #E6ECF2 !important;
        line-height: 1.85 !important;
        letter-spacing: 0.005em;
        unicode-bidi: plaintext !important;
    }

    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3,
    [data-testid="stMain"] h4,
    [data-testid="stMain"] h5,
    [data-testid="stMain"] h6 {
        color: #F3C969 !important;
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        line-height: 1.45 !important;
        unicode-bidi: plaintext !important;
    }

    [data-testid="stMain"] strong,
    [data-testid="stMain"] b {
        color: #FFE0A0 !important;
    }

    [data-testid="stMain"] code {
        color: #F3C969 !important;
        background: rgba(23,29,36,0.7) !important;
        font-family: 'Consolas', 'Courier New', monospace !important;
        padding: 0.1rem 0.3rem;
        border-radius: 0.2rem;
    }

    [data-testid="stDataFrame"] *:not([data-testid*="Icon"]):not([class*="material"]) {
        font-family: 'Segoe UI', 'Saudi', system-ui, sans-serif !important;
        color: #E6ECF2 !important;
        font-variant-numeric: tabular-nums lining-nums;
    }
    [data-testid="stDataFrame"] thead th {
        color: #F3C969 !important;
        background: rgba(23,29,36,0.85) !important;
        font-weight: 600 !important;
    }

    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        color: #9FB0C0 !important;
    }
</style>
"""


def apply_unified_text():
    """يطبّق توحيد الخط السعودي واللون - لا يُستدعى من app.py لإبقاء تنسيقاته المخصصة."""
    st.markdown(_UNIFIED_TEXT_CSS, unsafe_allow_html=True)


def tuwaiq_header(title: str, subtitle: str = ""):
    """يعرض عنوان بنمط طويق مع شعار جانبي صغير (المستوى السفلي للشعار مع النص)."""
    logo_uri = _logo_data_uri()
    if logo_uri:
        logo_html = (
            f'<img src="{logo_uri}" alt="logo" '
            'style="width:80px;height:80px;object-fit:contain;display:block;'
            'transform:translateY(-0.3cm);">'
        )
    else:
        logo_html = TUWAIQ_LOGO_SVG

    html = (
        '<div style="display:flex;align-items:flex-end;gap:0cm;margin-bottom:0.5rem;direction:rtl;">'
        '<div style="width:80px;flex-shrink:0;">'
        f'{logo_html}'
        '</div>'
        f'<div class="tuwaiq-header" style="margin:0;line-height:1;">{title}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="tuwaiq-subtitle">{subtitle}</div>',
                    unsafe_allow_html=True)


def render_sidebar_logout():
    """يعرض زر تسجيل الخروج في الشريط الجانبي عند المصادقة."""
    if not st.session_state.get("authenticated"):
        return
    with st.sidebar:
        st.markdown(
            '<div style="height:1px;background:linear-gradient(90deg,transparent,#E0A43B,transparent);'
            'margin:1rem 0;"></div>',
            unsafe_allow_html=True,
        )
        user = st.session_state.get("username", "")
        if user:
            st.markdown(
                f'<div style="text-align:center;color:#9FB0C0;font-size:0.9rem;'
                f'font-family:\'Saudi\',system-ui,sans-serif;margin-bottom:0.5rem;">'
                f'مرحباً، <span style="color:#F3C969;font-weight:600;">{html.escape(str(user))}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        if st.button("تسجيل الخروج", type="secondary", use_container_width=True, key="sidebar_logout_btn"):
            for k in ("authenticated", "username", "login_attempts", "locked"):
                st.session_state.pop(k, None)
            st.rerun()
