"""
أداة بناء character_map — تحويل class IDs إلى أحرف فعلية
============================================================

كيف تستخدم:
1. بعد تدريب نموذج OCR، ضع `ocr_chars_detector.pt` في مجلد `models/`
2. تأكد من توفر بيانات تدريب OCR في `ocr_training/ocr_dataset/`
3. شغّل: python build_character_map.py
4. السكربت يفتح نافذة لكل فئة ويعرض عينات من الأحرف
5. اكتب الحرف الفعلي الذي تراه واضغط Enter
6. النتيجة تُحفظ في `character_map.json`

النتيجة النهائية تكون مثل:
{
  "0": "ا",
  "1": "ب",
  "2": "0",
  ...
}
"""
import os
import json
import random
import zipfile
from pathlib import Path
from collections import defaultdict

import cv2
import matplotlib.pyplot as plt

# المسارات
PROJECT_ROOT = Path(__file__).parent.parent
DATASET_DIR = PROJECT_ROOT / "ocr_training" / "ocr_dataset"
DATASET_ZIP = PROJECT_ROOT / "ocr_training" / "ocr_dataset.zip"
OUTPUT_MAP = PROJECT_ROOT / "ocr_training" / "character_map.json"

# إذا المجلد غير موجود، نحاول استخراجه من ZIP
if not DATASET_DIR.exists():
    if DATASET_ZIP.exists():
        print(f"📦 استخراج {DATASET_ZIP.name} ...")
        with zipfile.ZipFile(DATASET_ZIP, 'r') as zf:
            zf.extractall(DATASET_ZIP.parent)
        print(f"✅ تم الاستخراج إلى: {DATASET_DIR}")
    else:
        print(f"⚠️ لم يتم العثور على dataset:")
        print(f"   - المجلد: {DATASET_DIR}")
        print(f"   - أو الملف المضغوط: {DATASET_ZIP}")
        exit(1)

# قد يكون الـ ZIP يحتوي على مجلد بنفس الاسم بالداخل
if not (DATASET_DIR / "train").exists():
    # ابحث عن مجلد فرعي يحتوي train
    for sub in DATASET_DIR.iterdir():
        if sub.is_dir() and (sub / "train").exists():
            DATASET_DIR = sub
            break
    if not (DATASET_DIR / "train").exists():
        print(f"⚠️ بنية الـ dataset غير متوقعة - لا يوجد مجلد train")
        exit(1)

print(f"📁 استخدام dataset من: {DATASET_DIR}")


def collect_class_crops(n_per_class=6):
    """يجمع عينات صور مقصوصة لكل فئة من الـ training set."""
    crops_by_class = defaultdict(list)

    labels_dir = DATASET_DIR / "train" / "labels"
    images_dir = DATASET_DIR / "train" / "images"

    label_files = list(labels_dir.glob("*.txt"))
    random.shuffle(label_files)

    for lbl_file in label_files:
        stem = lbl_file.stem
        img_path = None
        for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
            p = images_dir / (stem + ext)
            if p.exists():
                img_path = p
                break
        if img_path is None:
            continue

        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]

        with open(lbl_file) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cls = int(float(parts[0]))
                if len(crops_by_class[cls]) >= n_per_class:
                    continue
                xc, yc, bw, bh = map(float, parts[1:5])
                x1 = max(0, int((xc - bw / 2) * w) - 5)
                y1 = max(0, int((yc - bh / 2) * h) - 5)
                x2 = min(w, int((xc + bw / 2) * w) + 5)
                y2 = min(h, int((yc + bh / 2) * h) + 5)
                crop = img[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                crops_by_class[cls].append(crop)

        # توقف بعد ما نجمع لكل الفئات
        if all(len(crops_by_class[c]) >= n_per_class for c in range(27)):
            break

    return crops_by_class


def show_class_gallery(crops_by_class, output_path):
    """يعرض شبكة من 27 صف، كل صف فئة، فيها 6 عينات بدقة عالية."""
    n_classes = 27
    n_per_class = 6

    # حجم أكبر بكثير + dpi عالٍ لوضوح الأحرف
    fig, axes = plt.subplots(n_classes, n_per_class + 1,
                              figsize=(n_per_class * 3.0 + 3, n_classes * 2.5))

    for cls in range(n_classes):
        # العمود الأول: رقم الفئة بخط كبير
        axes[cls, 0].text(0.5, 0.5, f"class\n{cls}", ha='center', va='center',
                          fontsize=22, fontweight='bold', color='red')
        axes[cls, 0].axis('off')

        # العينات
        crops = crops_by_class.get(cls, [])
        for i in range(n_per_class):
            ax = axes[cls, i + 1]
            if i < len(crops):
                crop_rgb = cv2.cvtColor(crops[i], cv2.COLOR_BGR2RGB)
                ax.imshow(crop_rgb)
            ax.axis('off')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✅ معرض الفئات محفوظ في: {output_path}")

    # أيضاً ننشئ معارض فردية لكل فئة بدقة عالية جداً
    individual_dir = Path(output_path).parent / "class_samples"
    individual_dir.mkdir(exist_ok=True)
    for cls in range(n_classes):
        crops = crops_by_class.get(cls, [])
        if not crops:
            continue
        fig, axes = plt.subplots(1, len(crops), figsize=(len(crops) * 4, 5))
        if len(crops) == 1:
            axes = [axes]
        for ax, crop in zip(axes, crops):
            ax.imshow(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            ax.axis('off')
        fig.suptitle(f"class_{cls:02d}", fontsize=24, fontweight='bold', color='red')
        plt.tight_layout()
        plt.savefig(individual_dir / f"class_{cls:02d}.png", dpi=120, bbox_inches='tight')
        plt.close(fig)
    print(f"✅ معارض فردية لكل فئة في: {individual_dir}")


def interactive_mapping(crops_by_class):
    """يعرض كل فئة على حدة ويسأل المستخدم عن الحرف."""
    char_map = {}

    print("\n" + "=" * 60)
    print("بناء character_map التفاعلي")
    print("=" * 60)
    print("لكل فئة، ستظهر نافذة فيها عينات من الحرف.")
    print("اكتب الحرف الفعلي الذي تراه واضغط Enter.")
    print("لتجاوز فئة (مثلاً ليست واضحة): اضغط Enter مباشرة.")
    print()

    for cls in range(27):
        crops = crops_by_class.get(cls, [])
        if not crops:
            print(f"class_{cls}: لا توجد عينات - تخطّي")
            char_map[str(cls)] = ""
            continue

        # عرض الفئة
        fig, axes = plt.subplots(1, len(crops), figsize=(len(crops) * 2, 2))
        if len(crops) == 1:
            axes = [axes]
        for ax, crop in zip(axes, crops):
            ax.imshow(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            ax.axis('off')
        fig.suptitle(f"class_{cls}")
        plt.show(block=False)
        plt.pause(0.5)

        ans = input(f"  class_{cls} → الحرف؟ ").strip()
        char_map[str(cls)] = ans
        plt.close(fig)

    return char_map


def main():
    print("\n📦 جمع عينات من كل فئة...")
    crops = collect_class_crops(n_per_class=6)

    # معرض بصري شامل
    gallery_path = PROJECT_ROOT / "ocr_training" / "class_gallery.png"
    show_class_gallery(crops, gallery_path)

    print("\n📋 خيارات التشغيل:")
    print("  1. تفاعلي: عرض كل فئة وكتابة الحرف")
    print("  2. صامت: حفظ المعرض فقط واكتب الـ map يدوياً")
    choice = input("اختر (1 أو 2): ").strip()

    if choice == "1":
        char_map = interactive_mapping(crops)
    else:
        print("\nاطّلع على class_gallery.png ثم عدّل character_map.json يدوياً.")
        # قالب فارغ
        char_map = {str(i): "" for i in range(27)}

    # حفظ
    with open(OUTPUT_MAP, "w", encoding="utf-8") as f:
        json.dump(char_map, f, ensure_ascii=False, indent=2)

    print(f"\n✅ character_map.json محفوظ في: {OUTPUT_MAP}")
    print("\nمحتوى الـ map:")
    for k, v in char_map.items():
        print(f"  class_{k}: '{v}'")


if __name__ == "__main__":
    main()
