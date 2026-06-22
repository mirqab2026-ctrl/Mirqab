# خطوات رفع مرقاب على GitHub + ربط ملف Google Drive

## 1) أنشئ المستودع على GitHub
1. ادخل https://github.com/new
2. الاسم: `mirqab` (أو ما تريد) · الرؤية: **Public**
3. **لا** تفعّل «Add a README» (لدينا واحد) · اضغط **Create repository**
4. انسخ رابط المستودع، مثل: `https://github.com/USERNAME/mirqab.git`

## 2) ارفع الكود (شغّل الأوامر في مجلد المشروع)
افتح PowerShell أو Git Bash داخل `C:\Users\PCD\Desktop\Mirqab_Delivery` ونفّذ:

```bash
git init
git add .
git commit -m "Initial commit — Mirqab intelligent security gate"
git branch -M main
git remote add origin https://github.com/USERNAME/mirqab.git
git push -u origin main
```

> النماذج (`*.pt` و `*.onnx`) ومجلد `YOLO_Training_Delivery/` مستبعدة تلقائيًا عبر `.gitignore`،
> فيبقى المستودع خفيفًا (~1–2 ميجا). تأكّد بعد الرفع أنها غير ظاهرة في GitHub.

## 3) ارفع الملف الكامل على Google Drive
1. ارفع `Mirqab_full_runnable.zip` (41 ميجا) إلى Google Drive.
2. زر يمين ← **مشاركة** ← «أي شخص لديه الرابط» ← **نسخ الرابط**.

## 4) ضع رابط Drive في README ثم ادفع التحديث
1. في `README.md` استبدل السطر:
   `ضع رابط Google Drive هنا بعد الرفع`
   برابط Drive الذي نسخته.
2. ثم:
```bash
git add README.md
git commit -m "Add Google Drive download link for models/full package"
git push
```

## تم
- الكود: على GitHub (عام، خفيف).
- المشروع الكامل + النماذج: على Google Drive، ورابطه داخل README.
- نماذج الوجه تُنزَّل أيضًا تلقائيًا عبر `python scripts/setup_face_models.py`.
