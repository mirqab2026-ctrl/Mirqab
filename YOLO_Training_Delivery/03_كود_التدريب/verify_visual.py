"""رسم 8 صور عشوائية من كل dataset مع المربعات للتحقق البصري"""
import os
import random
from pathlib import Path
import cv2
import matplotlib.pyplot as plt

random.seed(123)
BASE = Path("/tmp/merge/merged_dataset/train")
images = list((BASE / "images").glob("*"))

# اختر صورتين من كل dataset
samples = []
for prefix in ["ds1", "ds2", "ds3", "ds4"]:
    matching = [im for im in images if im.name.startswith(prefix + "_")]
    samples.extend(random.sample(matching, min(2, len(matching))))

fig, axes = plt.subplots(2, 4, figsize=(20, 10))
axes = axes.flatten()

for ax, img_path in zip(axes, samples):
    img = cv2.imread(str(img_path))
    if img is None:
        ax.axis('off')
        continue
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = img.shape[:2]

    label_path = BASE / "labels" / (img_path.stem + ".txt")
    if label_path.exists():
        with open(label_path) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls, xc, yc, bw, bh = map(float, parts[:5])
                    x1 = int((xc - bw / 2) * w)
                    y1 = int((yc - bh / 2) * h)
                    x2 = int((xc + bw / 2) * w)
                    y2 = int((yc + bh / 2) * h)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 4)

    ax.imshow(img)
    ax.set_title(img_path.name[:40], fontsize=9)
    ax.axis('off')

plt.tight_layout()
out_path = "/tmp/merge/verification.png"
plt.savefig(out_path, dpi=80, bbox_inches='tight')
print(f"حفظ التحقق البصري في: {out_path}")
