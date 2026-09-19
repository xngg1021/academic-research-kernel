# academic-research-kernel (ar)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

نواة محايدة للبحث الأكاديمي ومجموعة مداولات متعددة الوكلاء. توفر 13 مهارة أكاديمية وأدوات تحقق مع نقاط دخول Agent Plugins v1 و MCP (بروتوكول سياق النموذج)، بالإضافة إلى التكامل الأصلي لـ Hermes Agent و Claude Code و Cursor ووكلاء CLI المخصصين.

المؤلف: Junfu Shi (SJF, xngg1021)، Hermes Agent. الترخيص: [Source Lineage License 1.0](../../LICENSE).

## الترخيص

تعتمد هذه النسخة **Source Lineage License 1.0** للمواد المحددة في [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). تحتفظ النسخ التاريخية السابقة بترخيص MIT الساري.

## المهارات

| المهارة | الإصدار | الوصف |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | التحقق المتبادل من الهوية وإحصاءات الاقتباس؛ فحص إشارات التحديث وسحب الأبحاث؛ تحديد نصوص الوصول المفتوح والتحقق من هوية PDF |
| `skills/literature-analysis` | 1.3.0 | اثنا عشر مسار عمل: تشابه الموضوعات، تداخل النصوص، الأدلة المعاكسة، ملفات المؤلفين، محاكاة مراجعة النظراء، وفحص المغالطات |
| `skills/academic-writing` | 1.1.1 | التحرير الأكاديمي، إرشادات الاقتباس (ISO 690 و APA و MLA و Chicago و IEEE و AMA وملفات التعريف الإقليمية)، وقواعد المجلات العلمية |
| `skills/math-computation` | 1.2.1 | توجيه المسائل الرياضية والإحصائية مع خوارزميات عددية مجربة؛ ملفات مرجعية متقدمة |
| `skills/quantitative-paper-audit` | 1.1.0 | إعادة حساب الإحصاءات المنشورة (حجم الأثر، قيم p، فترات الثقة، نسب الأرجحية/المخاطر) واكتشاف التناقضات الحسابية |
| `skills/research-reproducibility` | 1.0.1 | مسار تدقيق قابلية إعادة الإنتاج في 14 مرحلة مع قوائم فحص منظمة وسجلات تدقيق قابلة للتكرار |
| `skills/systematic-review-meta-analysis` | 1.0.1 | سجلات بحث PRISMA، فرز الدراسات السابقة، تحويل حجم الأثر، تحليل التباين والدمج التلوي |
| `skills/literature-watch` | 1.1.0 | رصد أسبوعي: تتبع الموضوعات والمؤلفين والاستشهادات بمعرفات DOI على OpenAlex و Crossref مع منع التكرار |
| `skills/retraction-watch` | 1.1.0 | رصد أسبوعي: التحقق من قائمة DOI المراقبة مقابل فهارس سحب الأبحاث وسجلات التحديث في OpenAlex و Crossref |
| `skills/research-object-identity` | 1.1.0 | تحديد قطعي لموارد البحث وتتبع النسب مع التحقق من صحة المخطط السببي الموجه (DAG) |
| `skills/claim-evidence-graph` | 1.0.0 | ربط قطعي بين الادعاءات العلمية وسجلات الأدلة وسلسلة النسب الحسابية |
| `skills/decision-ledger` | 1.0.0 | سجل قرارات البحث: سجل قطعي للإلحاق فقط لقرارات البحث، والنتائج السلبية، وحالة المسارات البحثية |
| `skills/cross-review-five` | 2.0.0 | تنسيق ديناميكي للجنة مراجعة متعددة النماذج غير المتجانسة مع خوارزمية كوهن-مانكرس والمداولة المشتتة v2 |

## المعايير الأكاديمية والخطوط الأساسية متعددة الأنماط

يعتمد المستودع **ISO 690:2021** (المراجع الببليوغرافية) و **ISO 5127:2017** (المفاهيم والمصطلحات) و **W3C PROV** (نموذج بيانات التتبع) كخطوط أساسية دولية، إلى جانب المعايير التخصصية (APA 7th، IEEE، PRISMA 2020، ICMJE). انظر [بنية المعايير](../../docs/standards/README.md) و [دليل المصطلحات](../../docs/terminology/README.md).

## التكامل والاستخدام المحمول

```bash
python scripts/mcp_server.py
```

## التحقق والتكامل المستمر (CI)

يعمل التكامل المستمر عبر Linux x86_64 و Linux ARM64 و Ubuntu 26.04 Canary و Windows و macOS مع اجتياز 625 اختبار وحدة بنجاح والتحقق المستمر من canary.

## وثائق البحث والتخطيط

- [أطلس التحديات الأكاديمية v0 (الإنجليزية)](../../docs/pain-atlas-v0.en.md)، [النسخة الصينية](../../docs/pain-atlas-v0.zh.md): نقاط الاحتكاك في دورة حياة العمل الأكاديمي.
- [خطة البحث v0 (الإنجليزية)](../../docs/research-plan-v0.en.md)، [النسخة الصينية](../../docs/research-plan-v0.zh.md): نموذج كائن البحث، مجالات القدرات الأساسية ومصفوفة تحليل العوامل.
