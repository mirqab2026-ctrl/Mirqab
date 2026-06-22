# دليل خطوة بخطوة

## المرحلة 1: إعداد كاشف اللوحة (مكتمل ✅)

كاشف اللوحة `license_plate_detector.pt` جاهز.

**اطلب الآن:** انسخ الملف الذي نزّلته من Colab إلى:
```
license_plate_ocr_project/models/license_plate_detector.pt
```

---

## المرحلة 2: تدريب نموذج OCR

### 2.1 تجهيز Dataset

الـ dataset جاهز ومُقسَّم بالفعل:
- 473 صورة تدريب
- 88 صورة validation
- 31 صورة اختبار
- 27 فئة حرفية

موجود في `ocr_training/ocr_dataset/` وموزّع كأجزاء `ocr_dataset_part_*` (مثل ما فعلنا في كاشف اللوحة).

### 2.2 التدريب في Colab

1. افتح `ocr_training/train_ocr_yolo.ipynb` في Colab
2. فعّل GPU (Runtime → Change runtime type → T4 GPU)
3. شغّل الخلايا بالترتيب
4. عند خلية الرفع، اختر الأجزاء `ocr_dataset_part_aa, ab, ac` معاً
5. التدريب يأخذ ~30 دقيقة على T4
6. نزّل الملفات:
   - `ocr_chars_detector.pt`
   - `ocr_training_results.zip`

7. ضع `ocr_chars_detector.pt` في:
```
license_plate_ocr_project/models/ocr_chars_detector.pt
```

### 2.3 الأداء المتوقع

- mAP@0.5 المتوقع: 85-92% (مع 27 فئة على ~470 صورة)
- ملاحظة: قد تكون الفئات النادرة (مثل class 16, 13) أصعب

---

## المرحلة 3: بناء خريطة الأحرف

هذه أهم خطوة! النموذج يعطي class IDs من 0 إلى 26، ونحتاج معرفة أي حرف يقابل كل ID.

### 3.1 توليد معرض الفئات

```bash
cd license_plate_ocr_project/ocr_training/
python build_character_map.py
```

السكربت:
1. يجمع 6 عينات من كل فئة من بيانات التدريب
2. يحفظ صورة `class_gallery.png` فيها 27 صف، كل صف عينات حرف واحد
3. يسألك: تفاعلي أم صامت؟

### 3.2 ملء الخريطة

**الطريقة 1: تفاعلية**
- اختر "1" عند التشغيل
- لكل فئة، تظهر نافذة فيها عينات
- اكتب الحرف الذي تراه واضغط Enter
- مثال: لو ظهرت لك صور لحرف "ج" اكتب: `ج` ثم Enter
- لو ظهرت أرقام "5" اكتب: `5` ثم Enter

**الطريقة 2: يدوياً**
- اختر "2" عند التشغيل
- افتح `class_gallery.png` في عارض الصور
- افتح `character_map.json` في محرر نصوص
- لكل صف في الصورة، اكتب الحرف المقابل في JSON

### 3.3 ملاحظات على لوحات السعودية

لوحات السعودية تحتوي عادةً:
- **سطر علوي:** 3 أحرف إنجليزية + 3 أرقام إنجليزية
- **سطر سفلي:** 3 أحرف عربية + 4 أرقام عربية (٠-٩)

الـ 27 فئة محتمل أنها:
- 17 حرف (الأحرف المستخدمة في لوحات السعودية فقط)
- 10 أرقام

**الأحرف الشائعة في لوحات السعودية:**

| إنجليزي | عربي |
|---------|------|
| A | ا |
| B | ب |
| J | ج |
| D | د |
| R | ر |
| S | س |
| T | ط |
| E | ع |
| G | ق |
| K | ك |
| L | ل |
| M | م |
| N | ن |
| H | هـ |
| U | و |
| V | ى |
| X | ص |

---

## المرحلة 4: تشغيل الـ Pipeline

بعد إكمال:
- `models/license_plate_detector.pt` ✅
- `models/ocr_chars_detector.pt` ✅
- `ocr_training/character_map.json` ✅

شغّل:
```bash
cd license_plate_ocr_project/
pip install ultralytics opencv-python numpy

# اختبار سريع
python inference/plate_ocr.py path/to/car_image.jpg
```

أو في كود:
```python
from inference.plate_ocr import PlateOCR

ocr = PlateOCR(
    detector_path='models/license_plate_detector.pt',
    ocr_path='models/ocr_chars_detector.pt',
    char_map_path='ocr_training/character_map.json'
)

result = ocr.read('car.jpg')
for plate in result['plates']:
    print(plate['text'])
```

---

## استكشاف الأخطاء

### النص فارغ
- تحقق من تعبئة `character_map.json` بشكل صحيح
- جرّب تقليل `ocr_conf=0.20`

### بعض الأحرف خاطئة
- راجع `class_gallery.png` وتأكد من ملء الخريطة بدقة
- بعض الفئات النادرة قد تحتاج بيانات أكثر

### الترتيب خاطئ (السطر السفلي قبل العلوي)
- تعديل في `plate_ocr.py` في دالة `_sort_characters`
- جرّب تعديل عتبة `y_range > avg_height * 0.7`

### دقة منخفضة
- زد عدد epochs في التدريب (100 بدل 80)
- استخدم `yolov8s.pt` بدل `yolov8n.pt`
- اجمع بيانات إضافية للفئات النادرة
