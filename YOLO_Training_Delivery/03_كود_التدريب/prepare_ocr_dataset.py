"""
تجهيز dataset OCR من ds4
- 592 صورة، 27 فئة حرفية
- تقسيم 80% train / 15% valid / 5% test
- إعادة تسمية الفئات بأسماء واضحة (char_00, char_01, ...)
"""
import os
import shutil
import random
import yaml
from pathlib import Path

random.seed(42)

SRC = Path("/tmp/merge/extracted/ds4")
DST = Path("/tmp/merge/license_plate_ocr_project/ocr_training/ocr_dataset")

if DST.exists():
    shutil.rmtree(DST)
for split in ["train", "valid", "test"]:
    (DST / split / "images").mkdir(parents=True, exist_ok=True)
    (DST / split / "labels").mkdir(parents=True, exist_ok=True)

# جمع كل ملفات الـ labels
label_files = sorted((SRC / "train" / "labels").glob("*.txt"))
print(f"إجمالي الصور: {len(label_files)}")

# خلط وتقسيم
random.shuffle(label_files)
n = len(label_files)
n_train = int(n * 0.80)
n_valid = int(n * 0.15)
splits = {
    "train": label_files[:n_train],
    "valid": label_files[n_train:n_train + n_valid],
    "test": label_files[n_train + n_valid:],
}

# نسخ الملفات
for split_name, files in splits.items():
    for lbl_file in files:
        stem = lbl_file.stem
        # ابحث عن الصورة
        img_path = None
        for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
            p = SRC / "train" / "images" / (stem + ext)
            if p.exists():
                img_path = p
                break
        if img_path is None:
            continue
        shutil.copy(img_path, DST / split_name / "images" / img_path.name)
        shutil.copy(lbl_file, DST / split_name / "labels" / lbl_file.name)
    print(f"  {split_name}: {len(files)} صورة")

# إنشاء data.yaml
# نحتفظ بأسماء الفئات الأصلية 0-26 لأنها class IDs (سيتم بناء المعجم لاحقاً)
class_names = ['char_00', 'char_01', 'char_02', 'char_03', 'char_04', 'char_05',
               'char_06', 'char_07', 'char_08', 'char_09', 'char_10', 'char_11',
               'char_12', 'char_13', 'char_14', 'char_15', 'char_16', 'char_17',
               'char_18', 'char_19', 'char_20', 'char_21', 'char_22', 'char_23',
               'char_24', 'char_25', 'char_26']

# يجب تطابق ترتيب الأسماء مع class IDs الأصلية في ds4
# ds4 الأسماء كانت ['0', '1', '10', '11', ... '9'] (مرتبة أبجدياً)
# نحتاج إلى تطابق فعلي بالـ class IDs
original_names = ['0', '1', '10', '11', '12', '13', '14', '15', '16', '17', '18',
                  '19', '2', '20', '21', '22', '23', '24', '25', '26', '3', '4',
                  '5', '6', '7', '8', '9']

# إنشاء mapping من class_id إلى class_name (للوضوح)
# class_id i يأخذ الاسم char_{i:02d}
data_yaml = {
    "path": str(DST.resolve()),
    "train": "train/images",
    "val": "valid/images",
    "test": "test/images",
    "nc": 27,
    "names": [f"char_{i:02d}" for i in range(27)],
}
with open(DST / "data.yaml", "w") as f:
    yaml.dump(data_yaml, f, sort_keys=False, default_flow_style=False)

print(f"\n✅ dataset جاهز في: {DST}")
print(f"data.yaml: {DST / 'data.yaml'}")
