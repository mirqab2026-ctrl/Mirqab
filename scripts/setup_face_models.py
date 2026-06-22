# -*- coding: utf-8 -*-
"""
تنزيل نماذج الوجه buffalo_s (مرة واحدة، يحتاج إنترنت)
=======================================================
ينزّل حزمة InsightFace buffalo_s ويستخرج الملفين المطلوبين فقط إلى
models/face/ — بعدها يعمل النظام دون إنترنت (Air-gapped):

    det_500m.onnx   (~2.5 MB)  — كشف الوجه SCRFD-500MF
    w600k_mbf.onnx  (~13 MB)   — تشفير MobileFaceNet 512-d

الاستخدام:
    python scripts/setup_face_models.py
"""
import ssl
import sys
import zipfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEST = ROOT / "models" / "face"
NEEDED = ["det_500m.onnx", "w600k_mbf.onnx"]

URLS = [
    "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_s.zip",
    "https://sourceforge.net/projects/insightface.mirror/files/v0.7/buffalo_s.zip/download",
]


def already_done() -> bool:
    return all((DEST / n).exists() for n in NEEDED)


def _ssl_context():
    """سياق SSL بشهادات certifi (يحل CERTIFICATE_VERIFY_FAILED على ويندوز)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def download(url: str, dest: Path) -> bool:
    print(f"تنزيل: {url}")

    # المحاولة 1: مكتبة requests (تستخدم شهادات certifi تلقائياً)
    try:
        import requests
        with requests.get(url, stream=True, timeout=120,
                          headers={"User-Agent": "Mozilla/5.0"}) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done * 100 // total}% ({done // 1024} KB)",
                              end="", flush=True)
        print()
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"  فشل (requests): {e}")

    # المحاولة 2: urllib بسياق certifi، ثم بلا تحقق كحل أخير
    for ctx, label in [(_ssl_context(), "certifi"),
                       (ssl._create_unverified_context(), "بدون تحقق SSL")]:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120, context=ctx) as r, \
                    open(dest, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = r.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done * 100 // total}% ({done // 1024} KB)",
                              end="", flush=True)
            print()
            return True
        except Exception as e:
            print(f"  فشل ({label}): {e}")
    return False


def main():
    if already_done():
        print("النماذج موجودة مسبقاً في models/face — لا حاجة للتنزيل.")
        return 0

    DEST.mkdir(parents=True, exist_ok=True)
    zip_path = DEST / "buffalo_s.zip"

    ok = False
    for url in URLS:
        if download(url, zip_path):
            ok = True
            break
    if not ok:
        print("\nتعذّر التنزيل من كل المصادر. بدائل يدوية:")
        print("  1) نزّل buffalo_s.zip يدوياً من صفحة إصدارات InsightFace v0.7")
        print(f"  2) استخرج الملفين {NEEDED} إلى {DEST}")
        return 1

    print("استخراج الملفات المطلوبة فقط...")
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            base = Path(member).name
            if base in NEEDED:
                with z.open(member) as src, open(DEST / base, "wb") as dst:
                    dst.write(src.read())
                print(f"  ✓ {base}")

    zip_path.unlink(missing_ok=True)

    if already_done():
        print(f"\nتم بنجاح — النماذج في: {DEST}")
        return 0
    print("\nخطأ: الحزمة لا تحتوي الملفات المتوقعة.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
