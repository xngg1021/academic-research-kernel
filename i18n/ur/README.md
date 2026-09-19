# academic-research-kernel (ur)

[English](../../README.md) · [简体中文](../../README.zh-CN.md) · [繁體中文](../../README.zh-TW.md) · [日本語](../../README.ja.md) · [한국어](../../README.ko.md) · [Deutsch](../../README.de.md) · [Français](../../README.fr.md) · [Español](../../README.es.md) · [Português](../pt/README.md) · [Русский](../ru/README.md) · [Bahasa Indonesia](../id/README.md) · [Italiano](../it/README.md) · [हिन्दी](../hi/README.md) · [العربية](../ar/README.md) · [বাংলা](../bn/README.md) · [اردو](../ur/README.md) · [Tiếng Việt](../vi/README.md) · [Türkçe](../tr/README.md) · [فارسی](../fa/README.md) · [Kiswahili](../sw/README.md) · [Polski](../pl/README.md)

تعلیمی تحقیق اور کثیر ایجنٹ مشاورتی عمل کے لیے غیر جانبدار کور۔ یہ پورٹیبل Agent Plugins v1 اور MCP (ماڈل سیاق و سباق پروٹوکول) کے ساتھ 13 علمی مہارتیں اور تصدیقی آلات مہیا کرتا ہے۔

مصنف: Junfu Shi (SJF, xngg1021)، Hermes Agent. لائسنس: [Source Lineage License 1.0](../../LICENSE).

## لائسنس

یہ دستاویز [LICENSE-APPLICATION.md](../../LICENSE-APPLICATION.md) میں نامزد مواد کے لیے **Source Lineage License 1.0** نافذ کرتی ہے۔ ماضی کے ورژن MIT لائسنس کے تحت محفوظ ہیں۔

## مہارتیں

| مہارت | ورژن | تفصیل |
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

## تعلیمی معیارات اور بین الاقوامی پروفائلز

یہ مخزن بین الاقوامی بنیادی اصول کے طور پر **ISO 690:2021**، **ISO 5127:2017** اور **W3C PROV** قائم کرتا ہے۔ مزید تفصیلات کے لیے [معیارات کا خاکہ](../../docs/standards/README.md) اور [اصطلاحات کی رہنمائی](../../docs/terminology/README.md) ملاحظہ کریں۔

## Integration & Portable Usage

```bash
python scripts/mcp_server.py
```

## توثیق اور سی آئی (CI)

مسلسل انضمام (CI) لینکس x86_64، لینکس ARM64، ونڈوز اور میک او ایس پر 625 کامیاب یونٹ ٹیسٹوں کے ساتھ تمام کوالٹی ٹیسٹ مکمل کرتا ہے۔

## تحقیقی و منصوبہ بندی دستاویزات

- [مسائل کا نقشہ v0 (انگریزی)](../../docs/pain-atlas-v0.en.md)، [چینی ورژن](../../docs/pain-atlas-v0.zh.md): علمی کام کے مراحل میں پیش آنے والی مشکلات۔
- [تحقیقی منصوبہ v0 (انگریزی)](../../docs/research-plan-v0.en.md)، [چینی ورژن](../../docs/research-plan-v0.zh.md): ریسرچ آبجیکٹ ماڈل، بنیادی صلاحیت کے شعبہ جات اور فیکٹر میٹرکس۔
