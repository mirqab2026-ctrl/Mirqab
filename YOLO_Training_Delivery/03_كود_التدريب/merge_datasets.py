"""
دمج 4 datasets لكشف اللوحات في dataset واحد موحّد
الفئة النهائية: 0 = license_plate (واحدة فقط)
"""
import os
import shutil
import random
from pathlib import Path
import yaml

random.seed(42)

# مسارات الإدخال والإخراج
INPUT_BASE = Path("/tmp/merge/extracted")
OUTPUT_BASE = Path("/tmp/merge/merged_dataset")

# تنظيف وإعداد مجلد الإخراج
if OUTPUT_BASE.exists():
    shutil.rmtree(OUTPUT_BASE)
for split in ["train", "valid", "test"]:
    (OUTPUT_BASE / split / "images").mkdir(parents=True, exist_ok=True)
    (OUTPUT_BASE / split / "labels").mkdir(parents=True, exist_ok=True)


def remap_label_file(src_label_path, keep_class_indices, mode="filter"):
    """
    يقرأ ملف label ويعيد قائمة سطور جديدة بعد الفلترة وإعادة تعيين الفئة لـ 0.

    mode = "filter": احتفظ فقط بالأسطر التي فئتها في keep_class_indices
    mode = "union": احسب bbox مغلّف لكل الأسطر (لـ ds4)
    """
    new_lines = []
    with open(src_label_path) as f:
        lines = f.readlines()

    if mode == "filter":
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls = int(float(parts[0]))
            if cls not in keep_class_indices:
                continue
            # نأخذ 4 قيم بعد الفئة (xc, yc, w, h) فقط - نتجاهل polygons
            bbox = parts[1:5]
            new_lines.append(f"0 {bbox[0]} {bbox[1]} {bbox[2]} {bbox[3]}\n")

    elif mode == "union":
        # احسب bbox يغلّف كل الـ characters → يمثل اللوحة كاملة
        boxes = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            try:
                xc, yc, w, h = map(float, parts[1:5])
                x1, y1 = xc - w / 2, yc - h / 2
                x2, y2 = xc + w / 2, yc + h / 2
                boxes.append((x1, y1, x2, y2))
            except ValueError:
                continue
        if boxes:
            x1 = min(b[0] for b in boxes)
            y1 = min(b[1] for b in boxes)
            x2 = max(b[2] for b in boxes)
            y2 = max(b[3] for b in boxes)
            # توسيع طفيف 3% في كل اتجاه لاحتواء حدود اللوحة
            pad = 0.03
            x1 = max(0.0, x1 - (x2 - x1) * pad)
            y1 = max(0.0, y1 - (y2 - y1) * pad)
            x2 = min(1.0, x2 + (x2 - x1) * pad)
            y2 = min(1.0, y2 + (y2 - y1) * pad)
            xc = (x1 + x2) / 2
            yc = (y1 + y2) / 2
            w = x2 - x1
            h = y2 - y1
            new_lines.append(f"0 {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")

    return new_lines


def find_image_for_label(labels_dir, label_name):
    """يجد الصورة المطابقة لملف label معين"""
    stem = Path(label_name).stem
    images_dir = labels_dir.parent / "images"
    for ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        img_path = images_dir / (stem + ext)
        if img_path.exists():
            return img_path
        img_path = images_dir / (stem + ext.upper())
        if img_path.exists():
            return img_path
    return None


def process_dataset(ds_name, ds_path, keep_classes, mode, prefix):
    """يعالج dataset واحد ويعيد قائمة (split, image_path, new_lines)"""
    items = []
    # ابحث عن splits الموجودة
    for split_name in ["train", "valid", "val", "test"]:
        split_dir = ds_path / split_name
        if not split_dir.exists():
            continue
        labels_dir = split_dir / "labels"
        if not labels_dir.exists():
            continue

        # تطبيع اسم الـ split
        normalized_split = "valid" if split_name in ["valid", "val"] else split_name

        for label_file in sorted(labels_dir.glob("*.txt")):
            new_lines = remap_label_file(label_file, keep_classes, mode)
            if not new_lines:
                continue  # تجاهل الصور التي لا تحتوي على bbox للوحة
            img_path = find_image_for_label(labels_dir, label_file.name)
            if img_path is None:
                continue
            items.append((normalized_split, img_path, label_file.stem, new_lines))

    return items


def split_train_only(items, val_ratio=0.15, test_ratio=0.0):
    """يقسم العناصر التي ليس لها valid/test"""
    train_items = [i for i in items if i[0] == "train"]
    valid_items = [i for i in items if i[0] == "valid"]
    test_items = [i for i in items if i[0] == "test"]

    if not valid_items and train_items:
        # نقسم train إلى train/valid
        random.shuffle(train_items)
        n = len(train_items)
        n_val = int(n * val_ratio)
        n_test = int(n * test_ratio)
        valid_items = [(("valid",) + x[1:]) for x in train_items[:n_val]]
        test_items_new = [(("test",) + x[1:]) for x in train_items[n_val:n_val + n_test]]
        train_items = [(("train",) + x[1:]) for x in train_items[n_val + n_test:]]
        test_items = test_items + test_items_new

    return train_items + valid_items + test_items


# ========== معالجة كل dataset ==========
print("=== ds1: License-plate-recognition (Number-Plate + Plate) ===")
items_ds1 = process_dataset(
    "ds1", INPUT_BASE / "ds1",
    keep_classes={0},  # نأخذ Number-Plate (bbox فقط) ونتجاهل Plate (polygon)
    mode="filter", prefix="ds1"
)
print(f"  {len(items_ds1)} items")

print("\n=== ds2: saudi plate (license-plate = class 5) ===")
items_ds2 = process_dataset(
    "ds2", INPUT_BASE / "ds2",
    keep_classes={5},  # license-plate
    mode="filter", prefix="ds2"
)
items_ds2 = split_train_only(items_ds2, val_ratio=0.15)
print(f"  {len(items_ds2)} items")

print("\n=== ds3: Saudi LPR (Full_Plate = class 2) ===")
items_ds3 = process_dataset(
    "ds3", INPUT_BASE / "ds3",
    keep_classes={2},  # Full_Plate
    mode="filter", prefix="ds3"
)
items_ds3 = split_train_only(items_ds3, val_ratio=0.15)
print(f"  {len(items_ds3)} items")

print("\n=== ds4: Saudi car plates (chars 0-26 → union bbox) ===")
items_ds4 = process_dataset(
    "ds4", INPUT_BASE / "ds4",
    keep_classes=None,  # غير مستخدم في mode=union
    mode="union", prefix="ds4"
)
items_ds4 = split_train_only(items_ds4, val_ratio=0.15)
print(f"  {len(items_ds4)} items")

# ========== الدمج النهائي ==========
all_items = []
for ds_idx, items in enumerate([items_ds1, items_ds2, items_ds3, items_ds4], start=1):
    for split, img_path, stem, lines in items:
        prefixed_stem = f"ds{ds_idx}_{stem}"
        all_items.append((split, img_path, prefixed_stem, lines))

stats = {"train": 0, "valid": 0, "test": 0}
for split, img_path, stem, lines in all_items:
    ext = img_path.suffix.lower()
    dst_img = OUTPUT_BASE / split / "images" / (stem + ext)
    dst_lbl = OUTPUT_BASE / split / "labels" / (stem + ".txt")
    shutil.copy(img_path, dst_img)
    with open(dst_lbl, "w") as f:
        f.writelines(lines)
    stats[split] += 1

# ========== إنشاء data.yaml ==========
data_yaml = {
    "path": str(OUTPUT_BASE.resolve()),
    "train": "train/images",
    "val": "valid/images",
    "test": "test/images",
    "nc": 1,
    "names": ["license_plate"],
}
with open(OUTPUT_BASE / "data.yaml", "w") as f:
    yaml.dump(data_yaml, f, sort_keys=False)

# ========== الإحصائيات النهائية ==========
print("\n" + "=" * 60)
print("النتيجة النهائية:")
print("=" * 60)
for split, count in stats.items():
    print(f"  {split:6s}: {count:5d} صورة")
print(f"  المجموع: {sum(stats.values())} صورة")
print(f"\nالمجلد النهائي: {OUTPUT_BASE}")
print(f"data.yaml: {OUTPUT_BASE / 'data.yaml'}")
