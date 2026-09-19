# academic-research-kernel (ar)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

نواة محايدة للبحث الأكاديمي ومجموعة مداولات متعددة الوكلاء. توفر 13 مهارة أكاديمية وأدوات تحقق مع نقاط دخول Agent Plugins v1 و MCP (بروتوكول سياق النموذج)، بالإضافة إلى التكامل الأصلي لـ Hermes Agent و Claude Code و Cursor ووكلاء CLI المخصصين.

المؤلف: Junfu Shi (SJF, xngg1021)، Hermes Agent. الترخيص: [Source Lineage License 1.0](../../LICENSE).

## الترخيص

تعتمد هذه النسخة **Source Lineage License 1.0** للمواد المحددة في [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md). تحتفظ النسخ التاريخية السابقة بترخيص MIT الساري.

## المهارات

| المهارة | الإصدار | الوصف |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Cross-check identity and citation counts; inspect updates and retractions; locate OA text |
| `skills/literature-analysis` | 1.3.0 | Twelve workflows: similarity, overlap, counter-evidence, author profiles, mock reviews, fallacy checks |
| `skills/academic-writing` | 1.1.1 | Editing, citation guidance (ISO 690, APA, MLA, Chicago, IEEE, AMA and regional profiles), journal rules |
| `skills/math-computation` | 1.2.1 | Domain and task routing with numerical and statistical recipes; advanced reference files |
| `skills/quantitative-paper-audit` | 1.1.0 | Recompute reported statistics (effect size, p values, CIs, OR/RR, power) and detect discrepancies |
| `skills/research-reproducibility` | 1.0.1 | Fourteen-stage reproduction audit pipeline with structured checklists and reproducible records |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA search logs, screening logs, effect-size conversion, heterogeneity, and pooling |
| `skills/literature-watch` | 1.1.0 | Weekly blueprint: watch topics, authors, and DOI citing works on OpenAlex and Crossref |
| `skills/retraction-watch` | 1.1.0 | Weekly blueprint: monitor DOI watchlist against retraction indexes and update signals |
| `skills/research-object-identity` | 1.1.0 | Deterministic research-resource identification and provenance tracking; sub-100ms lineage tracing |
| `skills/claim-evidence-graph` | 1.0.0 | Deterministic scientific claim–evidence linking connecting assertions, evidence records, and provenance |
| `skills/decision-ledger` | 1.0.0 | Research Decision Log: deterministic log of research decisions, failed attempts, and route status |
| `skills/cross-review-five` | 2.0.0 | Dynamic multi-reviewer panel orchestration supporting heterogeneous models with Kuhn-Munkres matching |

## المعايير الأكاديمية والخطوط الأساسية متعددة الأنماط

يعتمد المستودع **ISO 690:2021** (المراجع الببليوغرافية) و **ISO 5127:2017** (المفاهيم والمصطلحات) و **W3C PROV** (نموذج بيانات التتبع) كخطوط أساسية دولية، إلى جانب المعايير التخصصية (APA 7th، IEEE، PRISMA 2020، ICMJE). انظر [بنية المعايير](../../docs/standards/README.md) و [دليل المصطلحات](../../docs/terminology/README.md).

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## التحقق والتكامل المستمر (CI)

يعمل التكامل المستمر عبر Linux x86_64 و Linux ARM64 و Ubuntu 26.04 Canary و Windows و macOS مع اجتياز 625 اختبار وحدة بنجاح والتحقق المستمر من canary.

## وثائق البحث والتخطيط

- [أطلس التحديات الأكاديمية v0 (الإنجليزية)](../../docs/pain-atlas-v0.en.md)، [النسخة الصينية](../../docs/pain-atlas-v0.zh.md): نقاط الاحتكاك في دورة حياة العمل الأكاديمي.
- [خطة البحث v0 (الإنجليزية)](../../docs/research-plan-v0.en.md)، [النسخة الصينية](../../docs/research-plan-v0.zh.md): نموذج كائن البحث، مجالات القدرات الأساسية ومصفوفة تحليل العوامل.
