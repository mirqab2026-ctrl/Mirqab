"""
image_enhancer.py
==================
نظام تحسين تلقائي للصور قبل المسح (Smart Auto-Enhancement).

الفلسفة:
- يُطبَّق فوراً وبصمت قبل YOLO/dlib
- يحلّل الصورة بسرعة (5-10ms) ويقرّر هل يحتاج تحسيناً
- إذا الصورة جيّدة → يعيدها كما هي (overhead مهمل)
- إذا فيها مشكلة → يطبّق فقط التحسين المناسب
- لا أزرار، لا تفاعل من المستخدم
- يسجّل قراراته في data/enhancement_log.csv للشفافية

الاستخدام:
    from backend.image_enhancer import maybe_enhance
    img = maybe_enhance(img, mode="plate")  # أو "face"
"""
from __future__ import annotations
import csv
import time
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import numpy as np


LOG_PATH = Path(__file__).parent.parent / "data" / "enhancement_log.csv"


# ============================================================
# عتبات القرار (Tunable)
# ============================================================
_THRESHOLDS = {
    "plate": {
        "min_brightness": 60,
        "max_brightness": 220,
        "min_contrast": 40,
        "min_sharpness": 100,    # Laplacian variance
        "min_width": 600,
        "upscale_factor": 2,
        "clahe_clip": 4.0,
        "clahe_grid": 8,
        "sharpen_amount": 1.5,
    },
    "face": {
        "min_brightness": 70,
        "max_brightness": 210,
        "min_contrast": 35,
        "min_sharpness": 80,
        "min_width": 100,        # نسبي للوجه
        "upscale_factor": 2,
        "clahe_clip": 2.0,       # معتدل لعدم تشويه الملامح
        "clahe_grid": 8,
        "sharpen_amount": 1.0,
    },
}


# ============================================================
# Quick Analysis
# ============================================================

def _analyze(img: np.ndarray) -> dict:
    """تحليل سريع لجودة الصورة (~5-10ms)."""
    if img is None or img.size == 0:
        return {"valid": False}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    brightness = float(gray.mean())
    contrast = float(gray.std())
    # Laplacian variance — مقياس الحدّة (أعلى = أوضح)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    h, w = img.shape[:2]
    return {
        "valid": True,
        "brightness": brightness,
        "contrast": contrast,
        "sharpness": sharpness,
        "width": w,
        "height": h,
    }


def _needs_enhancement(stats: dict, mode: str) -> List[str]:
    """يُرجع قائمة بأنواع التحسين المطلوبة."""
    if not stats.get("valid"):
        return []
    t = _THRESHOLDS.get(mode, _THRESHOLDS["plate"])
    fixes = []
    if stats["brightness"] < t["min_brightness"]:
        fixes.append("brighten")
    elif stats["brightness"] > t["max_brightness"]:
        fixes.append("darken")
    if stats["contrast"] < t["min_contrast"]:
        fixes.append("contrast")
    if stats["sharpness"] < t["min_sharpness"]:
        fixes.append("sharpen")
    if stats["width"] < t["min_width"]:
        fixes.append("upscale")
    return fixes


# ============================================================
# Enhancement Operations
# ============================================================

def _apply_clahe(img: np.ndarray, clip: float, grid: int) -> np.ndarray:
    """Contrast Limited Adaptive Histogram Equalization."""
    if img.ndim == 3:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
        l = clahe.apply(l)
        lab = cv2.merge([l, a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    else:
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
        return clahe.apply(img)


def _apply_gamma(img: np.ndarray, gamma: float) -> np.ndarray:
    """تصحيح gamma لتعديل السطوع."""
    inv = 1.0 / max(gamma, 0.01)
    table = np.array([((i / 255.0) ** inv) * 255 for i in np.arange(256)]).astype("uint8")
    return cv2.LUT(img, table)


def _apply_unsharp_mask(img: np.ndarray, amount: float = 1.5) -> np.ndarray:
    """شحذ الصورة عبر Unsharp Mask."""
    blurred = cv2.GaussianBlur(img, (0, 0), sigmaX=1.5)
    return cv2.addWeighted(img, 1 + amount, blurred, -amount, 0)


def _apply_bilateral(img: np.ndarray) -> np.ndarray:
    """Bilateral filter — يزيل الضوضاء ويحفظ الحدود."""
    return cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)


def _apply_upscale(img: np.ndarray, factor: int = 2) -> np.ndarray:
    """تكبير عالي الجودة عبر Lanczos."""
    h, w = img.shape[:2]
    return cv2.resize(img, (w * factor, h * factor),
                        interpolation=cv2.INTER_LANCZOS4)


# ============================================================
# Main API
# ============================================================

def maybe_enhance(img: np.ndarray,
                  mode: str = "plate",
                  log: bool = True) -> np.ndarray:
    """يحسّن الصورة تلقائياً إذا احتاجت ذلك. سريع وصامت.

    Args:
        img: الصورة (BGR numpy array)
        mode: "plate" أو "face"
        log: تسجيل القرار في CSV (افتراضياً نعم)

    Returns:
        صورة محسّنة (أو الأصلية إذا لم تحتج تحسين)
    """
    t0 = time.time()
    stats = _analyze(img)
    if not stats.get("valid"):
        return img

    fixes = _needs_enhancement(stats, mode)
    if not fixes:
        # الصورة جيدة — لا تحسين
        if log:
            _log_decision(mode, stats, applied=[], elapsed_ms=int((time.time() - t0) * 1000))
        return img

    t = _THRESHOLDS.get(mode, _THRESHOLDS["plate"])
    enhanced = img.copy()
    applied = []

    # ترتيب التطبيق مهم: upscale أولاً، ثم تصحيحات الإضاءة، ثم الشحذ
    if "upscale" in fixes:
        enhanced = _apply_upscale(enhanced, t["upscale_factor"])
        applied.append("upscale_2x")

    if "brighten" in fixes:
        gamma = max(0.6, stats["brightness"] / 100.0)
        enhanced = _apply_gamma(enhanced, gamma)
        applied.append(f"gamma_{gamma:.2f}")

    if "darken" in fixes:
        gamma = min(1.6, stats["brightness"] / 130.0)
        enhanced = _apply_gamma(enhanced, gamma)
        applied.append(f"gamma_{gamma:.2f}")

    if "contrast" in fixes or "brighten" in fixes:
        enhanced = _apply_clahe(enhanced, t["clahe_clip"], t["clahe_grid"])
        applied.append("clahe")

    if "sharpen" in fixes:
        enhanced = _apply_unsharp_mask(enhanced, t["sharpen_amount"])
        applied.append("sharpen")

    elapsed_ms = int((time.time() - t0) * 1000)
    if log:
        _log_decision(mode, stats, applied=applied, elapsed_ms=elapsed_ms)

    return enhanced


# ============================================================
# Logging
# ============================================================

_LOG_INIT = False


def _ensure_log_file():
    global _LOG_INIT
    if _LOG_INIT:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        with open(LOG_PATH, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp", "mode", "brightness", "contrast",
                "sharpness", "width", "height",
                "applied_fixes", "elapsed_ms",
            ])
    _LOG_INIT = True


def _log_decision(mode: str, stats: dict, applied: list, elapsed_ms: int):
    """يسجّل قرار التحسين في CSV (للشفافية والمراجعة)."""
    try:
        _ensure_log_file()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([
                ts, mode,
                f"{stats.get('brightness', 0):.1f}",
                f"{stats.get('contrast', 0):.1f}",
                f"{stats.get('sharpness', 0):.1f}",
                stats.get("width", 0),
                stats.get("height", 0),
                "|".join(applied) if applied else "(none)",
                elapsed_ms,
            ])
    except Exception:
        # Log فاشل لا يجب أن يكسر التطبيق
        pass


def force_enhance_plate(img: np.ndarray, level: int = 2) -> np.ndarray:
    """تحسين قوي وإلزامي للوحة (يستخدمه المشغّل لإعادة محاولة قراءة لوحة غامضة).

    Args:
        img: صورة اللوحة المقصوصة (BGR)
        level: 1 = تحسين معتدل، 2 = قوي، 3 = أقصى

    Returns:
        صورة محسّنة بقوة (دائماً، بصرف النظر عن جودة المصدر)
    """
    if img is None or img.size == 0:
        return img

    enhanced = img.copy()

    # 1) تكبير قوي (3x أو 4x حسب المستوى)
    upscale_factor = {1: 2, 2: 3, 3: 4}.get(level, 3)
    h, w = enhanced.shape[:2]
    if w < 800 or level >= 2:
        enhanced = cv2.resize(enhanced, (w * upscale_factor, h * upscale_factor),
                                interpolation=cv2.INTER_LANCZOS4)

    # 2) Bilateral filter — إزالة ضوضاء مع حفظ الحواف
    if level >= 2:
        enhanced = cv2.bilateralFilter(enhanced, d=9, sigmaColor=80, sigmaSpace=80)

    # 3) تصحيح gamma لمعالجة الإضاءة (ثابت)
    stats = _analyze(enhanced)
    if stats.get("valid"):
        brightness = stats["brightness"]
        if brightness < 100:
            enhanced = _apply_gamma(enhanced, max(0.55, brightness / 100.0))
        elif brightness > 190:
            enhanced = _apply_gamma(enhanced, min(1.7, brightness / 130.0))

    # 4) CLAHE قوي (لرفع التباين)
    clahe_clip = {1: 3.0, 2: 5.0, 3: 7.0}.get(level, 5.0)
    enhanced = _apply_clahe(enhanced, clahe_clip, 8)

    # 5) Unsharp Mask قوي (شحذ)
    sharpen_amount = {1: 1.2, 2: 2.0, 3: 2.8}.get(level, 2.0)
    enhanced = _apply_unsharp_mask(enhanced, sharpen_amount)

    return enhanced


def get_log_stats() -> dict:
    """إحصائيات مجمَّعة من ملف الـ log."""
    if not LOG_PATH.exists():
        return {"total": 0, "enhanced": 0, "skipped": 0,
                "avg_elapsed_ms": 0, "by_mode": {}}
    try:
        total = 0
        enhanced = 0
        elapsed = []
        by_mode = {"plate": 0, "face": 0}
        with open(LOG_PATH, "r", encoding="utf-8-sig") as f:
            r = csv.DictReader(f)
            for row in r:
                total += 1
                if row.get("applied_fixes") and row["applied_fixes"] != "(none)":
                    enhanced += 1
                try:
                    elapsed.append(int(row.get("elapsed_ms", 0)))
                except Exception:
                    pass
                mode = row.get("mode", "")
                if mode in by_mode:
                    by_mode[mode] += 1
        return {
            "total": total,
            "enhanced": enhanced,
            "skipped": total - enhanced,
            "avg_elapsed_ms": int(np.mean(elapsed)) if elapsed else 0,
            "by_mode": by_mode,
        }
    except Exception:
        return {"total": 0, "enhanced": 0, "skipped": 0,
                "avg_elapsed_ms": 0, "by_mode": {}}
