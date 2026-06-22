"""
Validation Module
=================
يتحقق من سلامة قراءة اللوحة عبر عدة طبقات:
1. ثقة كل حرف (low confidence flag)
2. صيغة اللوحة السعودية (XYZ NNNN: 3 حروف + 3-4 أرقام)
3. الأحرف المسموحة (17 حرف فقط)
4. التطابق مع قاعدة البيانات

يعيد نتيجة validation مع flags ودرجة جودة.
"""
from typing import Dict, List, Optional
import re

# الـ 17 حرف الرسمي للوحات السعودية
SAUDI_LETTERS = set("ABDEGHJKLNRSTUVXZ")
SAUDI_DIGITS = set("0123456789")

MIN_CHAR_CONFIDENCE = 0.70 # عتبة الثقة لكل حرف
MIN_AVG_CONFIDENCE = 0.80 # عتبة الثقة الكلية


def validate_plate_format(text: str) -> Dict:
    """
    يتحقق من صيغة اللوحة السعودية.
    الصيغة القياسية: 3-4 أرقام + 3 حروف (مثل "6240 VKJ")
    أو "VKJ 6240" بترتيب عكسي.
    """
    chars = text.replace(" ", "").upper()
    letters = [c for c in chars if c.isalpha()]
    digits = [c for c in chars if c.isdigit()]

    issues = []
    # عدد الحروف
    if len(letters) < 2 or len(letters) > 4:
        issues.append(f"عدد الحروف غير اعتيادي: {len(letters)} (المتوقع 3)")
    # عدد الأرقام
    if len(digits) < 3 or len(digits) > 5:
        issues.append(f"عدد الأرقام غير اعتيادي: {len(digits)} (المتوقع 3-4)")
    # الأحرف المسموحة
    invalid_letters = [c for c in letters if c not in SAUDI_LETTERS]
    if invalid_letters:
        issues.append(f"حروف غير سعودية: {','.join(invalid_letters)}")

    return {
        "format_valid": len(issues) == 0,
        "format_issues": issues,
        "letters_count": len(letters),
        "digits_count": len(digits),
    }


def validate_confidences(characters: List[Dict]) -> Dict:
    """يفحص ثقة كل حرف على حدة."""
    if not characters:
        return {
            "conf_valid": False,
            "low_conf_chars": [],
            "avg_confidence": 0.0,
            "min_confidence": 0.0,
        }

    confs = [c.get("confidence", 0.0) for c in characters]
    avg_conf = sum(confs) / len(confs)
    min_conf = min(confs)

    low_conf = [
        {"char": c.get("char", ""), "confidence": c.get("confidence", 0.0), "index": i}
        for i, c in enumerate(characters)
        if c.get("confidence", 0.0) < MIN_CHAR_CONFIDENCE
    ]

    return {
        "conf_valid": len(low_conf) == 0 and avg_conf >= MIN_AVG_CONFIDENCE,
        "low_conf_chars": low_conf,
        "avg_confidence": round(avg_conf, 3),
        "min_confidence": round(min_conf, 3),
    }


def validate_database_match(plate_text: str, db_module) -> Dict:
    """يتحقق إذا كانت اللوحة مسجّلة في قاعدة البيانات."""
    vehicle = db_module.find_vehicle_by_plate(plate_text)

    # حتى لو لم تطابق تماماً، نبحث عن أقرب لوحة
    similar_plates = []
    if not vehicle:
        all_vehicles = db_module.get_vehicles_with_owners()
        target = plate_text.replace(" ", "").upper()
        for v in all_vehicles:
            stored = v["plate_text"].replace(" ", "").upper()
            sim = _string_similarity(target, stored)
            if sim >= 0.7: # 70% تشابه
                similar_plates.append({
                    "plate": v["plate_text"],
                    "similarity": round(sim, 2),
                    "owner": v.get("owner_name", ""),
                    "make_model": f"{v.get('make','')} {v.get('model','')}".strip(),
                })
        similar_plates.sort(key=lambda x: -x["similarity"])

    return {
        "db_match": vehicle is not None,
        "vehicle": vehicle,
        "similar_plates": similar_plates[:3], # أعلى 3
    }


def _string_similarity(a: str, b: str) -> float:
    """تشابه String بـ Levenshtein distance المُطبَّع."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Levenshtein distance
    m, n = len(a), len(b)
    dp = [[0]*(n+1) for _ in range(m+1)]
    for i in range(m+1):
        dp[i][0] = i
    for j in range(n+1):
        dp[0][j] = j
    for i in range(1, m+1):
        for j in range(1, n+1):
            cost = 0 if a[i-1] == b[j-1] else 1
            dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+cost)
    distance = dp[m][n]
    return 1.0 - (distance / max(m, n))


def full_validate(plate_result: Dict, db_module) -> Dict:
    """
    التحقق الكامل من قراءة اللوحة.

    Returns:
        {
          "status": "ok" | "warning" | "needs_review",
          "score": 0-100,
          "format": {...},
          "confidence": {...},
          "db_match": {...},
          "recommendation": str,
          "needs_user_input": bool
        }
    """
    text = plate_result.get("text", "")
    chars = plate_result.get("characters", [])

    fmt = validate_plate_format(text)
    conf = validate_confidences(chars)
    db_check = validate_database_match(text, db_module)

    # حساب الـ score
    score = 100
    issues = []
    needs_input = False

    if not fmt["format_valid"]:
        score -= 25
        issues.extend(fmt["format_issues"])
        needs_input = True

    if not conf["conf_valid"]:
        n_low = len(conf["low_conf_chars"])
        score -= min(40, n_low * 15)
        if n_low > 0:
            issues.append(f"{n_low} حرف بثقة منخفضة")
        if conf["avg_confidence"] < 0.7:
            score -= 20
            issues.append(f"متوسط الثقة منخفض: {conf['avg_confidence']:.1%}")
        needs_input = True

    if not db_check["db_match"]:
        if db_check["similar_plates"]:
            score -= 10
            issues.append("لوحة غير مسجّلة لكن توجد لوحات مشابهة")
            needs_input = True
        else:
            score -= 5
            issues.append("لوحة غير مسجّلة في النظام")

    score = max(0, score)

    # تحديد الحالة النهائية
    if score >= 90:
        status = "ok"
        recommendation = "القراءة موثوقة - يمكن الاعتماد عليها"
        needs_input = False
    elif score >= 70:
        status = "warning"
        recommendation = "القراءة مقبولة لكن يُفضّل التحقق"
    else:
        status = "needs_review"
        recommendation = "القراءة تحتاج مراجعة بشرية فورية"
        needs_input = True

    return {
        "status": status,
        "score": score,
        "issues": issues,
        "format": fmt,
        "confidence": conf,
        "db_match": db_check,
        "recommendation": recommendation,
        "needs_user_input": needs_input,
    }
