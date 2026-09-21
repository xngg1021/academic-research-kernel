# academic-research-kernel (fa)

[English](../../README.md) · [简体中文](../../README.zh-Hans.md) · [繁體中文](../../README.zh-Hant.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

هسته پژوهشی دانشگاهی مستقل و مجموعه رایزنی چندعاملی. ۱۳ مهارت دانشگاهی و ابزار راستی‌آزمایی را با نقاط ورود سازگار با Agent Plugins v1 و MCP (Model Context Protocol)، به همراه یکپارچه‌سازی بومی برای Hermes Agent، Claude Code، Cursor و زیرعامل‌های سفارشی CLI فراهم می‌کند. شامل راستی‌آزمایی منابع، تحلیل ادبیات، نگارش و ویرایش علمی، محاسبات عددی، ممیزی مقالات کمی، ممیزی بازتولیدپذیری، مرور سیستماتیک و فراتحلیل، شناسایی هویت و تبار اشیاء پژوهشی، هماهنگ‌سازی داوری متقابل پویا میان مدل‌های ناهمگون و دو سیستم پایش هفتگی خودکار است. مخزن شامل بررسی‌های نمونه قابل اجرا است؛ دامنه اعتبارسنجی و محدودیت‌های سرویس‌های خارجی در [گزارش ممیزی](../../docs/project-lineage-audit-20260920.md) ثبت شده است.

نویسنده: Junfu Shi (SJF, xngg1021)، Hermes Agent. مجوز فعلی: [Source Lineage License 1.0](../../LICENSE).

## مجوز

تصویر حاوی این اعلان، مجوز **Source Lineage License 1.0** را برای مواد تحت پوشش و حقوق مشخص‌شده در [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) می‌پذیرد. اولین کامیت و ساختار SLL و کامیت ثبت مرز بعدی در [LICENSE-HISTORY.md](../../LICENSE-HISTORY.md) و [SOURCE-LINEAGE.md](../../SOURCE-LINEAGE.md) تفکیک شده‌اند. تصاویر بعدی که این اعلان را حفظ کنند، دارای همان شرایط هستند.

تصاویر تاریخی تا `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` تحت مجوز MIT بودند. دریافت‌کنندگان مجوزهای معتبر MIT خود را حفظ می‌کنند و نیازی به مهاجرت به SLL ندارند. [متن قبلی مجوز MIT پروژه](../../LICENSES/MIT-pre-SLL.txt) حفظ شده است؛ [tests/upstream/LICENSE](../../tests/upstream/LICENSE) و تبار شخص ثالث بدون تغییر باقی می‌مانند. مجوز جدید حقوق قبلی را لغو نمی‌کند.

مجوز SLL به طور گسترده استفاده، مطالعه، اصلاح، استفاده تجاری، توزیع و افزوده‌های مالکیتی را با رعایت شرایط مجوز، اعلان و تبار منبع مجاز می‌داند. این مجوز کپی‌لفت نیست و افشای کد منبع را الزام نمی‌کند. متن دقیق انگلیسی [LICENSE](../../LICENSE) حاکم بر این خلاصه است؛ `LicenseRef-Source-Lineage-1.0` یک ارجاع محلی است نه تخصیص SPDX. [پذیرش مشارکت‌ها](../../CONTRIBUTING.md) از مجوزهای بعدی مستقل است.

## مهارت‌ها

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

۲۱ پرونده مرجع Markdown در سیزده مهارت وجود دارد. مراجع تنها در صورت نیاز بارگذاری می‌شوند.

## استانداردهای علمی و خط پایه چندالگویی

سبک‌های استناد، معیارهای گزارش‌دهی و فراداده‌ها به مجله هدف، نهاد، تامین‌کننده مالی، رشته و حوزه قضایی بستگی دارند. این مخزن **ISO 690:2021** (ارجاعات کتابشناختی)، **ISO 5127:2017** (واژگان اطلاعات و مستندسازی) و **W3C PROV** (مدل داده‌های تبار) را به عنوان خطوط پایه بین‌المللی تعیین می‌کند. به [معماری استانداردهای علمی](../../docs/standards/README.md) و [راهنمای اصطلاحات طبیعی](../../docs/terminology/README.md) مراجعه کنید.

## یکپارچه‌سازی و استفاده قابل حمل

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
این مخزن مطابق با مشخصات مستقل **Agent Plugins v1** (`../../plugin.json`) است و ابزارهای اصلی اعتبارسنجی دانشگاهی و محاسبه مجدد آماری را از طریق **سرور MCP** بر پایه stdio (`../../mcp.json` / `python scripts/mcp_server.py`) ارائه می‌دهد. سازگار با Claude Code، Cursor، Gemini CLI و فریم‌ورک‌های مدرن عامل‌ها.

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
```

### 2. نصب بومی در هرمس (Hermes)
از محیط نصب Hermes دستور زیر را اجرا کنید:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

با جایگزین کردن نام دایرکتوری در شناسه کامل، سایر مهارت‌ها را نصب کنید. دستور tap معمولی شاخه پیش‌فرض را می‌خواند. مهارت‌های بسته‌بندی‌شده بررسی‌شده در کامیت `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video.

## دسترسی به منابع داده

- پرس‌وجوهای پایه OpenAlex به صورت ناشناس با سقف بودجه روزانه ($0.10/روز ناشناس و $1/روز با کلید رایگان، سقف ۱۰۰ درخواست/ثانیه) قابل اجرا هستند. کلید اختیاری را در `OPENALEX_API_KEY` ذخیره کنید.
- سامانه Crossref دسترسی عمومی به فراداده‌ها را همراه با محدودیت نرخ فراهم می‌کند. بررسی DOI برای به‌روزرسانی‌ها الزامی است.
- سامانه Unpaywall به ایمیل معتبر در `UNPAYWALL_EMAIL` نیاز دارد.
- پایگاه‌های arXiv، Europe PMC، PubMed و DOAJ منابع تکمیلی با سیاست‌های خاص خود هستند. سرویس‌های Scite، Dimensions، Scopus و Web of Science اختیاری می‌باشند.

## اعتبارسنجی و CI

از محیط اختصاصی Python استفاده کنید. پیش‌نیازهای QA اجرای کامل اعتبارسنجی‌ها را تضمین می‌کنند:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

سامانه QA فراداده‌ها، مراجع، الگوهای مسیرهای شخصی/کلیدهای محرمانه، نحو Python و بلوک‌های نشانه‌گذاری‌شده را بررسی می‌کند. خروجی ۰ نشانه موفقیت، ۱ خطای کد/اسکیما/هویت و ۲ نشانه عدم دسترسی به شبکه یا سهمیه است.

سیستم CI کل آزمون‌ها را در Linux x86_64 (Python 3.10-3.14)، Linux ARM64، Ubuntu 26.04 Preview، Windows x86_64، Windows ARM64، macOS ARM64 و macOS Intel با ۶۲۹ آزمون واحد موفق و ۴۰ بلوک اجرایی تاییدشده اجرا می‌کند.

بخش tools/longtail/ شامل تولیدکننده سناریوهای قطعی دنباله بلند است: ۴۰۹6 ترکیب نامزد با سید SHA256 بر روی محورهای فاکتور مجزا و گزارش پوشش در generated-scenarios.json.

بخش scripts/scfabric/ زیرساخت محاسبات علمی است: پروب سخت‌افزار، کاتالوگ بک‌اند با فیلتر انواع داده، پنج نمایه بار کاری و ComputeReceipt. اندازه‌گیری‌ها در [docs/scientific-compute-fabric.md](../../docs/scientific-compute-fabric.md) ثبت شده‌اند.

## اسناد پژوهشی و برنامه‌ریزی

این اسناد مراجع برنامه‌ریزی اکتشافی هستند نه نقشه راه الزام‌آور.

- [اطلس چالش‌ها نسخه ۰ (انگلیسی)](../../docs/pain-atlas-v0.en.md)، [نسخه چینی](../../docs/pain-atlas-v0.zh.md): نقاط اصطکاک در چرخه کار علمی همراه با وضعیت راستی‌آزمایی ادعاها.
- [برنامه پژوهشی نسخه ۰ (انگلیسی)](../../docs/research-plan-v0.en.md)، [نسخه چینی](../../docs/research-plan-v0.zh.md): مدل Research Object، حوزه‌های توانمندی اصلی و ماتریس تجزیه عوامل.
