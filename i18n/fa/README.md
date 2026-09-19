# academic-research-kernel (fa)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

هسته خنثی برای تحقیقات دانشگاهی و مجموعه هم‌اندیشی چند عاملی. ارائه دهنده ۱۳ مهارت علمی و ابزار راستی‌آزمایی به همراه پلاگین‌های Agent Plugins v1 و سرور MCP با پشتیبانی مستقیم از Hermes Agent، Claude Code و Cursor.

نویسنده: Junfu Shi (SJF, xngg1021)، Hermes Agent. مجوز: [Source Lineage License 1.0](../../LICENSE).

## مجوز

این نسخه از مجوز **Source Lineage License 1.0** برای موارد مشخص شده در [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) استفاده می‌کند. نسخه‌های قبلی تحت مجوز MIT معتبر باقی می‌مانند.

## مهارت‌های پژوهشی

| مهارت | نسخه | شرح |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | راستی‌آزمایی متقابل هویت و شمارش ارجاعات؛ بررسی سیگنال‌های به‌روزرسانی و سلب اعتبار؛ یافتن متن دسترسی آزاد و تأیید هویت PDF |
| `skills/literature-analysis` | 1.3.0 | دوازده جریان کاری: تشابه موضوعی، همپوشانی متن، شواهد متقابل، مشخصات نویسندگان، داوری آزمایشی و ارزیابی مغالطات |
| `skills/academic-writing` | 1.1.1 | ویرایش علمی، راهنمای استناد (ISO 690، APA، MLA، شیکاگو، IEEE، AMA و الگوهای منطقه‌ای) و قوانین مجلات |
| `skills/math-computation` | 1.2.1 | مسیریابی محاسبات ریاضی و آماری با روش‌های عددی معتبر؛ پرونده‌های مرجع پیشرفته |
| `skills/quantitative-paper-audit` | 1.1.0 | محاسبه مجدد آمارهای گزارش‌شده (اندازه اثر، مقادیر p، فواصل اطمینان، OR/RR) و شناسایی مغایرت‌های عددی |
| `skills/research-reproducibility` | 1.0.1 | خط لوله ممیزی تکرارپذیری ۱۴ مرحله‌ای با چک‌لیست‌های ساختاریافته و سوابق ممیزی قابل بازتولید |
| `skills/systematic-review-meta-analysis` | 1.0.1 | گزارش‌های جستجوی PRISMA، غربالگری متون، تبدیل اندازه اثر، ناهمگونی و تجمیع متادیتا |
| `skills/literature-watch` | 1.1.0 | رصد هفتگی: پایش موضوعات، نویسندگان و ارجاعات DOI در OpenAlex و Crossref با حذف موارد تکراری |
| `skills/retraction-watch` | 1.1.0 | رصد هفتگی: بررسی مجدد فهرست DOI در برابر نمایه‌های سلب اعتبار و سوابق به‌روزرسانی OpenAlex و Crossref |
| `skills/research-object-identity` | 1.1.0 | شناسایی قطعی منابع پژوهشی و رهگیری تبار محاسباتی با اعتبارسنجی گراف جهت‌دار غیرمدور علی |
| `skills/claim-evidence-graph` | 1.0.0 | پیوند قطعی میان ادعاهای علمی، سوابق شواهد و تبار محاسباتی |
| `skills/decision-ledger` | 1.0.0 | دفتر ثبت تصمیمات پژوهشی: گزارش قطعی و فقط-افزودنی از تصمیمات پژوهشی، نتایج منفی و وضعیت مسیرهای تحقیق |
| `skills/cross-review-five` | 2.0.0 | هماهنگ‌سازی پویا هیئت چندداوری برای مدل‌های ناهمگون با الگوریتم کوهن-مانکرز و رایزنی تنک نسخه ۲ |

## استانداردهای علمی و مبناهای چندگانه

این مخزن استانداردهای بین‌المللی **ISO 690:2021** (ارجاع‌دهی کتابشناختی)، **ISO 5127:2017** (مفاهیم و اصطلاحات) و **W3C PROV** (مدل ردگیری منشأ) را مبنا قرار می‌دهد. رجوع کنید به [معماری استانداردها](../../docs/standards/README.md) و [راهنمای اصطلاحات](../../docs/terminology/README.md).

## یکپارچه‌سازی و استفاده قابل حمل

```bash
python scripts/mcp_server.py
```

## راستی‌آزمایی و یکپارچه‌سازی مداوم

آزمون‌های مداوم (CI) بر روی پلتفرم‌های لینوکس، ویندوز و مک با ۶۲۵ تست واحد موفق و بررسی لحظه‌ای شاخه اصلی انجام می‌شود.

## اسناد پژوهش و برنامه‌ریزی

- [اطلس چالش‌ها v0 (انگلیسی)](../../docs/pain-atlas-v0.en.md)، [نسخه چینی](../../docs/pain-atlas-v0.zh.md): اصطکاک‌های موجود در چرخه فعالیت‌های علمی.
- [برنامه پژوهشی v0 (انگلیسی)](../../docs/research-plan-v0.en.md)، [نسخه چینی](../../docs/research-plan-v0.zh.md): مدل شیء پژوهشی، حوزه‌های قابلیت اصلی و ماتریس تجزیه عوامل.
