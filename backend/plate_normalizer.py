"""
plate_normalizer.py
====================
مكتبة تحويل لوحات السيارات بين الإنجليزية والعربية (المعيار السعودي).

الفلسفة:
- الـ canonical form هو الإنجليزي (4 أرقام + 3 حروف، بدون مسافات، كبير)
- العربي يُشتقّ تلقائياً من الـ canonical (مصدر واحد للحقيقة)
- المقارنة في القرارات تتمّ دائماً على الـ canonical

الاستخدام:
    from backend.plate_normalizer import (
        to_canonical, to_arabic_display, to_slots,
        validate_canonical, detect_script
    )

    canonical = to_canonical("٢٧٠٢ ق هـ د")  # → "2702QED"
    arabic    = to_arabic_display(canonical)  # → "٢٧٠٢ ق هـ د"
    slots     = to_slots(canonical)           # → {"digits": "2702", "letters": "QED"}
    ok, msg   = validate_canonical(canonical) # → (True, "")
"""
import re
from typing import Tuple


# ============================================================
# Mapping EN ↔ AR (المعيار السعودي للوحات)
# ============================================================
# المرجع: نموذج اللوحة السعودية (3 حروف + 4 أرقام)
# الحروف العربية المسموحة على اللوحات:
# ا ب ح د ر س ص ط ع ق ك ل م ن هـ و ى
# لكل حرف عربي حرف لاتيني مُرادف على نفس اللوحة.

EN_TO_AR_DIGITS = {
    "0": "٠", "1": "١", "2": "٢", "3": "٣", "4": "٤",
    "5": "٥", "6": "٦", "7": "٧", "8": "٨", "9": "٩",
}

# خريطة الحروف الرسمية (المعيار السعودي)
# نخزّن الحرف الأساسي فقط (بدون كاشيدا)
EN_TO_AR_LETTERS = {
    "A": "ا",   # ألف
    "B": "ب",   # باء
    "J": "ح",   # جيم (تقابل ح)
    "D": "د",   # دال
    "R": "ر",   # راء
    "S": "س",   # سين
    "X": "ص",   # صاد (تقابل X)
    "T": "ط",   # طاء
    "E": "ع",   # عين (تقابل E)
    "G": "ق",   # قاف (تقابل G)
    "K": "ك",   # كاف
    "L": "ل",   # لام
    "Z": "م",   # ميم (تقابل Z)
    "N": "ن",   # نون
    "H": "ه",   # هاء
    "U": "و",   # واو
    "V": "ى",   # ياء (مقصورة)
}

# للعرض البصري — بعض الحروف تظهر بكاشيدا (ـ) لتمييزها
AR_DISPLAY_OVERRIDE = {
    "ه": "هـ",  # تُعرض كـ "هـ" مع كاشيدا
}

# الخريطة العكسية
AR_TO_EN_DIGITS = {v: k for k, v in EN_TO_AR_DIGITS.items()}
AR_TO_EN_LETTERS = {v: k for k, v in EN_TO_AR_LETTERS.items()}

# كاراكتر الكاشيدا (يُتجاهل عند الإدخال)
TATWEEL = "ـ"
# ياء بديلة قد يكتبها المستخدم
AR_LETTER_ALIASES = {
    "ي": "ى",  # ياء عادية → ياء مقصورة
    "ة": "ه",  # تاء مربوطة → هاء (أحياناً تكتب خطأ)
}

# مفردات إضافية للأرقام (الفارسي شائع أيضاً)
PERSIAN_DIGITS = {
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
}


# ============================================================
# Detection
# ============================================================

def detect_script(text: str) -> str:
    """يُرجع: 'ar' | 'en' | 'mixed' | 'empty'."""
    if not text or not text.strip():
        return "empty"
    has_ar = any(c in AR_TO_EN_LETTERS or c in AR_TO_EN_DIGITS or c in PERSIAN_DIGITS
                 for c in text)
    has_en = any(c.upper() in EN_TO_AR_LETTERS or c in EN_TO_AR_DIGITS
                 for c in text)
    if has_ar and has_en:
        return "mixed"
    if has_ar:
        return "ar"
    if has_en:
        return "en"
    return "empty"


# ============================================================
# Normalization
# ============================================================

def to_canonical(text: str) -> str:
    """يحوّل أي إدخال (EN/AR/مختلط/بمسافات/كاشيدا) إلى canonical EN.

    Canonical = أحرف وأرقام بدون مسافات أو كاشيدا، **بترتيب LTR البصري**.

    معالجة Bidi:
    - حين تكتب "د هـ ق" بالعربي، أنت تكتب بترتيب القراءة الطبيعي (RTL)
    - في اللوحة السعودية، الموضع البصري للحرف العربي يطابق الإنجليزي
    - لذا نعكس الحروف العربية المتتالية للحصول على ترتيب LTR

    أمثلة:
        "2702 GHD"      → "2702GHD"   (LTR، كما هو)
        "٢٧٠٢ ق هـ د"   → "2702GHD"   (الحروف العربية تُعكس)
        "د هـ ق"        → "GHD"       (RTL → LTR بعكس)
        "ghd 2702"      → "GHD2702"
    """
    if not text:
        return ""
    # تنظيف مسبق: إزالة الكاشيدا واستبدال aliases
    cleaned = text.replace(TATWEEL, "")
    for src, dst in AR_LETTER_ALIASES.items():
        cleaned = cleaned.replace(src, dst)

    # نعالج كل character ونحدّد مصدره (AR/EN/digit)
    # ثم نعكس مجموعات الحروف العربية المتتالية لتحويل RTL→LTR
    items = []  # كل عنصر: (kind, en_char)
    for ch in cleaned:
        if ch.isspace():
            continue
        upper = ch.upper()
        if upper in EN_TO_AR_DIGITS:
            items.append(("digit_en", upper))
        elif upper in EN_TO_AR_LETTERS:
            items.append(("letter_en", upper))
        elif ch in AR_TO_EN_LETTERS:
            items.append(("letter_ar", AR_TO_EN_LETTERS[ch]))
        elif ch in AR_TO_EN_DIGITS:
            items.append(("digit_ar", AR_TO_EN_DIGITS[ch]))
        elif ch in PERSIAN_DIGITS:
            items.append(("digit_ar", PERSIAN_DIGITS[ch]))

    # عكس مجموعات الحروف العربية المتتالية (Bidi correction)
    result = []
    ar_letter_buffer = []
    for kind, val in items:
        if kind == "letter_ar":
            ar_letter_buffer.append(val)
        else:
            if ar_letter_buffer:
                # نعكس ونُخرج المجموعة العربية المتراكمة
                result.extend(reversed(ar_letter_buffer))
                ar_letter_buffer = []
            result.append(val)
    if ar_letter_buffer:
        result.extend(reversed(ar_letter_buffer))

    return "".join(result)


def split_digits_letters(canonical: str) -> Tuple[str, str]:
    """يفصل الأرقام عن الحروف من canonical.

    أمثلة:
        "2702GHD"  → ("2702", "GHD")
        "GHD2702"  → ("2702", "GHD")  (يُعاد بالترتيب القياسي)
        "2A7B0C"   → ("207", "ABC")
    """
    digits = "".join(c for c in canonical if c.isdigit())
    letters = "".join(c for c in canonical if c.isalpha())
    return digits, letters


def normalize_to_standard(text: str) -> str:
    """يحوّل أي إدخال إلى الشكل القياسي المرتّب: DDDDLLL.

    حتى لو كان الترتيب: 'GHD2702' → 'GHD2702' بعد الفرز.
    """
    canonical = to_canonical(text)
    digits, letters = split_digits_letters(canonical)
    return digits + letters


# ============================================================
# Display helpers
# ============================================================

def to_arabic_display(canonical: str) -> str:
    """يحوّل canonical EN → عرض عربي (الترتيب الأصلي محفوظ)."""
    if not canonical:
        return ""
    result = []
    for ch in canonical:
        if ch in EN_TO_AR_DIGITS:
            result.append(EN_TO_AR_DIGITS[ch])
        elif ch in EN_TO_AR_LETTERS:
            ar = EN_TO_AR_LETTERS[ch]
            # تطبيق العرض البصري المحسّن (مثلاً ه → هـ)
            result.append(AR_DISPLAY_OVERRIDE.get(ar, ar))
        else:
            result.append(ch)
    return "".join(result)


def _ar_char_display(ar_char: str) -> str:
    """يُرجع التمثيل البصري للحرف العربي (مع كاشيدا إن لزم)."""
    return AR_DISPLAY_OVERRIDE.get(ar_char, ar_char)


def to_slots(canonical: str):
    """يُرجع dict بالخانات منفصلة (للعرض في widget).

    Returns:
        {
            "en":     ["2", "7", "0", "2", "G", "H", "D"],
            "ar":     ["٢", "٧", "٠", "٢", "ق", "هـ", "د"],
            "digits": "2702",
            "letters": "GHD",
            "canonical": "2702GHD",
        }
    """
    digits, letters = split_digits_letters(canonical)
    canonical_sorted = digits + letters
    en_slots = list(canonical_sorted)
    ar_slots = []
    for c in en_slots:
        if c in EN_TO_AR_DIGITS:
            ar_slots.append(EN_TO_AR_DIGITS[c])
        elif c in EN_TO_AR_LETTERS:
            ar_slots.append(_ar_char_display(EN_TO_AR_LETTERS[c]))
        else:
            ar_slots.append(c)
    return {
        "en": en_slots,
        "ar": ar_slots,
        "digits": digits,
        "letters": letters,
        "canonical": canonical_sorted,
    }


# ============================================================
# Validation
# ============================================================

def validate_canonical(canonical: str) -> Tuple[bool, str]:
    """يتحقّق من أن الـ canonical صالح كلوحة سعودية.

    القواعد:
    - الحروف: **3 حروف بالضبط** (قاعدة صارمة - لا تقبل أقل أو أكثر)
    - الأرقام: **1 إلى 4 أرقام** (اللوحات السعودية قد تحوي 1-4 أرقام)
    - جميع الحروف يجب أن تكون من القائمة المدعومة

    Returns: (is_valid, error_message)
    """
    if not canonical:
        return False, "اللوحة فارغة"

    digits, letters = split_digits_letters(canonical)

    if len(digits) == 0 and len(letters) == 0:
        return False, "لا توجد أحرف أو أرقام صالحة"

    # القاعدة الصارمة: 3 حروف بالضبط
    if len(letters) != 3:
        return False, f"عدد الحروف = {len(letters)} (المطلوب 3 حروف بالضبط)"

    # الأرقام: 1-4 (لا أقل من واحد، لا أكثر من 4)
    if len(digits) < 1:
        return False, "اللوحة تحتاج رقماً واحداً على الأقل"
    if len(digits) > 4:
        return False, f"عدد الأرقام = {len(digits)} (الحد الأقصى 4)"

    # تحقّق أن كل الحروف معروفة
    unknown = [c for c in letters if c not in EN_TO_AR_LETTERS]
    if unknown:
        return False, f"حروف غير مدعومة: {', '.join(unknown)}"

    return True, ""


def get_allowed_letters_en() -> str:
    """يُرجع جميع الحروف الإنجليزية المسموحة كسلسلة (للعرض في UI)."""
    return "".join(sorted(EN_TO_AR_LETTERS.keys()))


def get_allowed_letters_ar() -> str:
    """يُرجع جميع الحروف العربية المسموحة (للعرض في UI)."""
    return " ".join(_ar_char_display(v) for v in EN_TO_AR_LETTERS.values())
